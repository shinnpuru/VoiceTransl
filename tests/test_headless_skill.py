"""Behavioral checks for the portable, GUI-free subtitle adapters."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import yaml


HELPER = Path(__file__).resolve().parents[1] / 'scripts' / 'voicetransl_headless.py'
spec = importlib.util.spec_from_file_location('headless_skill', HELPER)
headless = importlib.util.module_from_spec(spec)
spec.loader.exec_module(headless)


class HeadlessSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, *args, success=True, env=None):
        # All CLI paths must work without site-packages or user Python settings.
        result = subprocess.run([sys.executable, '-I', '-S', str(HELPER), *map(str, args)],
                                capture_output=True, env=env)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_multiline_unicode_roundtrip_and_encodings(self):
        source = self.root / '原文.srt'
        output = self.root / 'source.json'
        text = '1\r\n00:00:00,999 --> 00:00:02,345\r\n你好♪\r\n第二行\r\n\r\n'
        for encoding in ('utf-8-sig', 'utf-16', 'gb18030'):
            source.write_bytes(text.encode(encoding))
            self.run_cli('srt-to-json', '-i', source, '-o', output)
            rows = headless.load_rows(output)
            self.assertEqual(rows, [dict(start=.999, end=2.345, message='你好♪\n第二行')])
            exported = self.root / 'nested' / 'roundtrip.srt'
            self.run_cli('export', '-i', output, '-o', exported)
            self.run_cli('srt-to-json', '-i', exported, '-o', output)
            self.assertEqual(headless.load_rows(output), rows)

    def test_merge_keeps_silence_in_segment_offsets(self):
        a, b, target = [self.root / name for name in ('a.json', 'b.json', 'merged.json')]
        headless.write_json(a, [dict(start=1, end=2, message='first')])
        headless.write_json(b, [dict(start=.5, end=3, message='second')])
        self.run_cli('merge', '-i', a, b, '--offsets', 0, 1800, '-o', target)
        self.assertEqual(headless.load_rows(target)[1]['start'], 1800.5)
        self.run_cli('merge', '-i', a, b, '--offsets', 0, '-o', target, success=False)

    def test_bilingual_timeline_mismatch_fails(self):
        original, translated = self.root / 'src.json', self.root / 'tg.json'
        headless.write_json(original, [dict(start=0, end=2, message='原文')])
        headless.write_json(translated, [dict(start=0, end=2, message='translation')])
        output = self.root / 'combined.srt'
        self.run_cli('export', '-i', translated, '--original', original, '-o', output)
        self.assertEqual(output.read_text('utf-8').count('00:00:00,000 --> 00:00:02,000'), 2)
        headless.write_json(translated, [dict(start=0, end=3, message='translation')])
        self.run_cli('export', '-i', translated, '--original', original,
                     '-o', self.root / 'bad.srt', success=False)
        self.assertFalse((self.root / 'bad.srt').exists())

    def test_timestamp_rounding_and_long_lrc(self):
        self.assertEqual(headless.timestamp(59.9996), '00:01:00,000')
        self.assertEqual(headless.timestamp(6001.001, True), '100:01.001')

    @unittest.skipUnless(os.name == 'nt', 'Windows runtime resolver')
    def test_runtime_is_cached_and_reused_without_creating_environment(self):
        shell = shutil.which('pwsh') or shutil.which('powershell')
        if not shell:
            self.skipTest('PowerShell unavailable')
        install = self.root / 'portable app'
        script = HELPER.with_name('resolve_voicetransl_python.ps1')
        args = [shell, '-NoProfile', '-File', str(script), '-Install', str(install)]
        env = dict(os.environ)
        env.pop('VOICETRANSL_PYTHON', None)
        first = subprocess.run([*args, '-Python', sys.executable], capture_output=True,
                               text=True, check=True, env=env)
        cache = install / 'agent-runtime' / 'python.json'
        modified = cache.stat().st_mtime_ns
        second = subprocess.run(args, capture_output=True, text=True, check=True, env=env)
        self.assertEqual(Path(first.stdout.strip()), Path(sys.executable))
        self.assertEqual(first.stdout.strip(), second.stdout.strip())
        self.assertEqual(cache.stat().st_mtime_ns, modified)
        self.assertFalse((install / 'agent-runtime' / 'venv').exists())

    def test_invalid_data_cannot_be_exported(self):
        for rows in ([], [dict(start=2, end=1, message='bad')],
                     [dict(start=float('nan'), end=4, message='bad')]):
            with self.assertRaises(ValueError):
                headless.validate(rows)

    def test_init_preserves_template_and_creates_isolated_project(self):
        template_dir = self.root / 'template'
        template_dir.mkdir()
        template = template_dir / 'config.yaml'
        template.write_text(yaml.safe_dump({
            'common': {'start_time': '23:59', 'splitFileNum': 2048},
            'plugin': {'filePlugin': 'file_plaintext_txt', 'textPlugins': ['custom']},
            'dictionary': {'preDict': ['(project_dir)dict_pre.txt']},
            'proxy': {'enableProxy': False}, 'custom': {'keep': 123},
        }), encoding='utf-8')
        before = template.read_bytes()
        (template_dir / 'dict_pre.txt').write_text('原\t目标', encoding='utf-8')
        project = self.root / 'job'
        env = dict(os.environ, SKILL_TEST_TOKEN='unit-test-placeholder')
        args = ('init-project', '--template', template, '--project', project,
                '--endpoint', 'http://127.0.0.1:8989/v1', '--model', 'test-model',
                '--token-env', 'SKILL_TEST_TOKEN')
        result = self.run_cli(*args, env=env)
        cfg = yaml.safe_load((project / 'config.yaml').read_text('utf-8'))
        self.assertEqual(template.read_bytes(), before)
        self.assertEqual(cfg['custom'], {'keep': 123})
        self.assertEqual(cfg['common']['start_time'], '')
        self.assertEqual(cfg['plugin']['filePlugin'], 'file_galtransl_json')
        self.assertEqual(cfg['plugin']['textPlugins'], ['custom'])
        self.assertEqual(cfg['dictionary']['preDict'], [project.as_posix() + '/dict_pre.txt'])
        self.assertEqual((project / 'dict_pre.txt').read_text('utf-8'), '原\t目标')
        entry = cfg['backendSpecific']['OpenAI-Compatible']['tokens'][0]
        self.assertEqual(entry['endpoint'], 'http://127.0.0.1:8989')
        self.assertNotIn(b'unit-test-placeholder', result.stdout + result.stderr)
        self.run_cli(*args, env=env, success=False)

    def test_summary_adapts_sdk_url_and_rejects_empty_response(self):
        config, source, output = [self.root / name for name in
                                  ('config.yaml', 'source.srt', 'summary.txt')]
        config.write_text(yaml.safe_dump({'backendSpecific': {'OpenAI-Compatible': {
            'tokens': [dict(endpoint='http://127.0.0.1:8989', token='local', modelName='model')]
        }}}), encoding='utf-8')
        source.write_text('00:00:01 原文', encoding='utf-8')
        client = MagicMock()
        client.__enter__.return_value = client
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='00:01 摘要'))])
        factory = MagicMock(return_value=client)
        args = SimpleNamespace(config=config, input=source, output=output, prompt_file=None)
        with patch.dict(sys.modules, {'openai': SimpleNamespace(OpenAI=factory)}), patch.dict(os.environ):
            headless.summarize(args)
            self.assertEqual(factory.call_args.kwargs['base_url'], 'http://127.0.0.1:8989/v1')
            self.assertEqual(output.read_text('utf-8'), '00:01 摘要')
            client.chat.completions.create.return_value.choices[0].message.content = ''
            with self.assertRaises(ValueError):
                headless.summarize(args)


if __name__ == '__main__':
    unittest.main()
