import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_stdout, _stderr = sys.stdout, sys.stderr
from app import ConcurrentTranslationPool, MainWorker, UIMessageQueue
sys.stdout, sys.stderr = _stdout, _stderr
from prompt2srt import make_lrc
from srt2prompt import make_prompt
from input_utils import normalize_input, is_remote_input, native_model_path
from network_utils import is_loopback_endpoint, model_request
from GalTransl.ConfigHelper import build_httpx_proxy_kwargs, build_httpx_sync_proxy_kwargs


class ProxyTests(unittest.TestCase):
    def test_loopback_bypasses_explicit_proxy(self):
        for url in ('http://localhost:8989', 'http://127.0.0.2:8989', 'http://[::1]:8989', 'http://[::ffff:127.0.0.1]:8989'):
            self.assertTrue(is_loopback_endpoint(url))
            self.assertEqual(build_httpx_proxy_kwargs('http://broken:1', url), {})
            self.assertEqual(build_httpx_sync_proxy_kwargs('http://broken:1', url), {})
        self.assertFalse(is_loopback_endpoint('https://localhost.example.org'))
        self.assertTrue(build_httpx_proxy_kwargs('http://proxy:7890', 'https://api.example.org'))

    def test_model_test_does_not_inherit_or_mutate_environment_proxy(self):
        with patch.dict(os.environ, {'HTTP_PROXY': 'http://broken:1'}), patch('network_utils.requests.Session') as factory:
            session = factory.return_value.__enter__.return_value
            model_request('POST', 'http://127.0.0.1:8989/v1/chat/completions', proxy='http://broken:1')
            self.assertFalse(session.trust_env)
            session.proxies.update.assert_not_called()
            self.assertEqual(os.environ['HTTP_PROXY'], 'http://broken:1')


class InputTests(unittest.TestCase):
    def test_copied_paths_file_urls_and_web_urls(self):
        self.assertEqual(normalize_input('  "C:/视频/test.mp4"  '), 'C:/视频/test.mp4')
        self.assertEqual(normalize_input('file:///C:/videos/a%20b.mp4').replace('\\', '/'), 'C:/videos/a b.mp4')
        self.assertTrue(is_remote_input('https://example.org/a.mp4'))
        self.assertFalse(is_remote_input('C:/missing.mp4'))
        self.assertFalse(is_remote_input('file:///C:/a.mp4'))

    def test_subtitle_encodings_preserve_content(self):
        text = '1\n00:00:01,000 --> 00:00:02,000\n中文字幕\n\n'
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / '字幕.srt'
            for encoding in ('utf-8', 'utf-8-sig', 'utf-16', 'gb18030'):
                source.write_bytes(text.encode(encoding))
                self.assertEqual(make_prompt(str(source))[0]['message'], '中文字幕')

    @unittest.skipUnless(os.name == 'nt', 'Windows runtime path compatibility')
    def test_native_path_uses_existing_alias_or_clear_error(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / '中文目录'
            folder.mkdir()
            path = folder / 'input.wav'
            path.write_bytes(b'audio')
            try:
                result = native_model_path(path)
            except ValueError as exc:
                self.assertIn('ASCII directory', str(exc))
            else:
                self.assertTrue(result.isascii())
                self.assertEqual(Path(result).read_bytes(), b'audio')


class SubtitleOutputTests(unittest.TestCase):
    def test_asr_preserves_segment_srt_until_merge(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            previous = Path.cwd()
            os.chdir(root)
            try:
                segment = root / 'segment_0000.16k.wav'
                segment.write_bytes(b'fake audio')
                source = root / 'segment.json'
                def build(_input, output, *args, **kwargs):
                    Path(output).with_suffix('.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nhello\n\n', encoding='utf-8')
                    return ['mock-asr']
                worker = SimpleNamespace(msg_queue=SimpleNamespace(put=lambda *a: None))
                with patch('app._build_crispasr_command', side_effect=build):
                    MainWorker._process_single_audio(worker, str(segment), '', '', '', '', '', str(source), lambda *a: (SimpleNamespace(wait=lambda: 0), False), lambda *a: None)
                self.assertTrue(segment.with_suffix('.srt').is_file())
                MainWorker._merge_segment_translations(worker, [str(segment)], [], 'final', '', str(root), '原文SRT', 600)
                self.assertEqual(make_prompt(str(root / 'final.srt'))[0]['message'], 'hello')
            finally:
                os.chdir(previous)

    def test_missing_segment_fails_instead_of_shifting_or_empty_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'second.srt').write_text('1\n00:00:01,000 --> 00:00:02,000\nhello\n\n', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'Missing or empty'):
                MainWorker._merge_segment_translations(None, [str(root / 'first.wav'), str(root / 'second.wav')], [], 'final', '', str(root), '原文SRT', 600)
            self.assertFalse((root / 'final.srt').exists())

    def test_segment_batch_barrier_keeps_workers_for_second_file(self):
        pool = ConcurrentTranslationPool('.', '', 1, threading.Event(), SimpleNamespace(put=lambda *a: None, drain_all=lambda **k: None))
        task = SimpleNamespace(base_path='', json_src='', output_dir='', output_format='', orig_srt_path='')
        with patch.object(ConcurrentTranslationPool, '_translate_one_impl') as translate:
            pool.start('ForGal-json')
            try:
                for _ in range(2):
                    pool.submit(task)
                    pool.wait_pending()
                    self.assertTrue(pool._active_threads[0].is_alive())
                self.assertEqual(translate.call_count, 2)
                pool.done()
                pool.wait_all()
            finally:
                pool.stop()

    def test_bilingual_lrc_single_and_segmented(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / 'workspace'
            (workspace / 'gt_output').mkdir(parents=True)
            segments = []
            for i in range(2):
                base = root / f'segment_{i:04d}.16k'
                segments.append(str(base) + '.wav')
                source = root / f'{base.name}.json'
                source.write_text(json.dumps([{'start': 1, 'end': 2, 'message': f'source{i}'}]), encoding='utf-8')
                (workspace / 'gt_output' / source.name).write_text(json.dumps([{'start': 1, 'end': 2, 'message': f'target{i}'}]), encoding='utf-8')
                make_lrc(str(source), str(base) + '.orig.lrc')
                ConcurrentTranslationPool._generate_output_impl(str(source), str(base), str(root), '双语LRC', str(workspace))
                combined = Path(str(base) + '.combine.lrc').read_text(encoding='utf-8')
                self.assertIn(f'source{i}', combined)
                self.assertIn(f'target{i}', combined)
            MainWorker._merge_segment_translations(None, segments, [], 'final', '', str(root), '双语LRC', 600)
            combined = (root / 'final.combine.lrc').read_text(encoding='utf-8')
            self.assertEqual(combined.count('source'), 2)
            self.assertEqual(combined.count('target'), 2)
            self.assertIn('[10:01.000] target1', combined)


if __name__ == '__main__':
    unittest.main()
