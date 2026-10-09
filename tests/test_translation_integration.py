"""Run the real translator subprocess against a local, deterministic model API."""
import json
import os
import re
import sys
import tempfile
import threading
import time
import subprocess
from types import SimpleNamespace
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import yaml
streams = sys.stdout, sys.stderr
from app import ConcurrentTranslationPool, UIMessageQueue
sys.stdout, sys.stderr = streams
from GalTransl.DefaultProjectConfig import DEFAULT_PROJECT_CONFIG_YAML
from GalTransl.TerminalOutput import DesktopProgressBar
from prompt2srt import make_lrc


class TranslationIntegrationTests(unittest.TestCase):
    def test_real_child_failure_and_cancellation_preserve_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'input.json'
            source.write_text('[{"start":0,"end":1,"message":"source"}]', encoding='utf-8')
            original = root / 'input.srt'
            original.write_text('original subtitle', encoding='utf-8')
            config = root / 'config.yaml'
            config.write_text('{}', encoding='utf-8')
            messages = UIMessageQueue(str(root / 'test.log'))
            task = dict(base_path=str(root / 'input'), json_src=str(source), output_dir=str(root), output_format='目标SRT', orig_srt_path=str(original))
            with patch('app._TRANSLATE_CMD', [sys.executable, '-c', 'import sys; sys.exit(7)']):
                with self.assertRaises(subprocess.CalledProcessError):
                    ConcurrentTranslationPool._translate_one_impl(task, 0, str(root), str(config), 'ForGal-json', messages, threading.Event(), [], threading.Lock())
            self.assertEqual(original.read_text(encoding='utf-8'), 'original subtitle')
            self.assertFalse((root / 'input.zh.srt').exists())
            pool = ConcurrentTranslationPool(str(root), str(config), 1, threading.Event(), messages)
            with patch('app._TRANSLATE_CMD', [sys.executable, '-c', 'import time; time.sleep(60)']):
                pool.start('ForGal-json')
                try:
                    pool.submit(SimpleNamespace(**task))
                    deadline = time.monotonic() + 5
                    while not pool._active_translate_procs and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(pool._active_translate_procs)
                    proc = pool._active_translate_procs[0]
                    pool.request_stop()
                    proc.wait(timeout=3)
                    self.assertIsNotNone(proc.returncode)
                finally:
                    pool.stop()
                self.assertTrue(all(not thread.is_alive() for thread in pool._active_threads))
            self.assertEqual(original.read_text(encoding='utf-8'), 'original subtitle')
            self.assertTrue(source.exists())

    def test_real_subprocess_progress_repair_bilingual_lrc_and_reasoning(self):
        self._run_pipeline(stream=False)

    def test_streaming_subprocess_progress_repair_and_bilingual_lrc(self):
        self._run_pipeline(stream=True)

    def _run_pipeline(self, stream):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append(request)
                content = request['messages'][-1]['content']
                lines = []
                for sig, raw in re.findall(r'(?m)^([a-z0-9]{3})\|(\{[^\n]+\})', content):
                    row = json.loads(raw)
                    if 'src' in row:
                        text = json.dumps({'id': row['id'], 'dst': f"译文{row['id']} / 文件夹"}, ensure_ascii=False)
                        # Exercise both reported malformed endings through the real parser.
                        text = text[:-1] if row['id'] == 1 else text[:-2] + '”}'
                        lines.append(sig + '|' + text)
                response_text = '```jsonline\n' + '\n'.join(lines) + '\n```' if lines else 'OK'
                body = json.dumps({'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'test', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': response_text}, 'finish_reason': 'stop'}]}).encode()
                if request.get('stream'):
                    chunks = []
                    for start in range(0, len(response_text), 7):
                        chunk = {'id': 'test', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'test', 'choices': [{'index': 0, 'delta': {'content': response_text[start:start + 7]}, 'finish_reason': None}]}
                        chunks.append('data: ' + json.dumps(chunk) + '\n\n')
                    body = (''.join(chunks) + 'data: [DONE]\n\n').encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream' if request.get('stream') else 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        active, lock, stop = [], threading.Lock(), threading.Event()
        def timeout():
            stop.set()
            with lock:
                for proc in active:
                    if proc.poll() is None:
                        proc.terminate()
        timer = threading.Timer(45, timeout)
        timer.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source = root / 'input.json'
                source.write_text(json.dumps([{'start': 1, 'end': 2, 'message': '原文一'}, {'start': 3, 'end': 4, 'message': '原文二'}]), encoding='utf-8')
                make_lrc(str(source), str(root / 'input.orig.lrc'))
                config = yaml.safe_load(DEFAULT_PROJECT_CONFIG_YAML)
                config['backendSpecific']['OpenAI-Compatible'].update(tokens=[{'token': 'test', 'endpoint': f'http://127.0.0.1:{server.server_port}', 'modelName': 'test'}], stream=stream, thinkingMode='enable_thinking', apiErrorWait=0)
                config['common'].update(language='ja2zh-cn', workersPerProject=1, splitFile='no', **{'gpt.restoreContextMode': False})
                config['dictionary'].update(preDict=[], postDict=[], **{'gpt.dict': []})
                (root / 'config.yaml').write_text(yaml.safe_dump(config, allow_unicode=True), encoding='utf-8')
                messages = UIMessageQueue(str(root / 'test.log'))
                with patch.dict(os.environ, {'HTTP_PROXY': 'http://127.0.0.1:1', 'HTTPS_PROXY': 'http://127.0.0.1:1'}):
                    ConcurrentTranslationPool._translate_one_impl(dict(base_path=str(root / 'input'), json_src=str(source), output_dir=str(root), output_format='双语LRC', orig_srt_path=''), 0, str(root), str(root / 'config.yaml'), 'ForGal-json', messages, stop, active, lock)
                log = (root / 'test.log').read_text(encoding='utf-8')
                self.assertFalse(stop.is_set(), log[-4000:])
                self.assertIn('0/2', log)
                self.assertIn('2/2', log)
                combined = (root / 'input.combine.lrc').read_text(encoding='utf-8')
                for expected in ('原文一', '原文二', '译文1 / 文件夹', '译文2 / 文件夹'):
                    self.assertIn(expected, combined)
                self.assertTrue(received)
                self.assertTrue(all(payload.get('enable_thinking') is False for payload in received))
                self.assertTrue(source.exists())
                self.assertEqual(active, [])
        finally:
            timer.cancel()
            timeout()
            server.shutdown()
            server.server_close()
            thread.join()

    def test_partial_progress_is_not_reported_as_complete_on_close(self):
        with patch('builtins.print') as output:
            bar = DesktopProgressBar(10)
            bar(3)
            bar.close()
        payload = json.loads(output.call_args.args[0].split(' ', 1)[1])
        self.assertEqual(payload['done'], 3)
        self.assertEqual(payload['total'], 10)
        self.assertFalse(bar.thread.is_alive())
