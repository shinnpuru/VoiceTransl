"""Exercise the real SDK over loopback, including proxy isolation and JSON payloads."""
import asyncio
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from openai import AsyncOpenAI
from GalTransl.Backend.BaseTranslate import BaseTranslate
from GalTransl.COpenAI import COpenAIToken, COpenAITokenPool
from GalTransl.Thinking import thinking_body


class ThinkingRequestTests(unittest.TestCase):
    def test_translation_and_availability_send_provider_controls_over_http(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                body = json.dumps({'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'test', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'OK'}, 'finish_reason': 'stop'}]}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f'http://127.0.0.1:{server.server_port}/v1'
        token = COpenAIToken('test', domain=endpoint, model_name='test', stream=False, isAvailable=True)
        async def exercise(mode):
            client = AsyncOpenAI(api_key='test', base_url=endpoint, http_client=httpx.AsyncClient(trust_env=False))
            translator = BaseTranslate.__new__(BaseTranslate)
            translator.client_list = [(client, token)]
            translator.pj_config = SimpleNamespace(stop_event=threading.Event())
            translator.tokenStrategy = 'random'
            translator.global_request_rpm = 0
            translator.api_timeout = 3
            translator.apiErrorWait = 0
            translator.thinking_mode = mode
            try:
                result, _ = await asyncio.wait_for(translator.ask_chatbot(prompt='test'), 8)
                self.assertEqual(result, 'OK')
            finally:
                await client.close()
        try:
            with patch.dict(os.environ, {'HTTP_PROXY': 'http://127.0.0.1:1', 'HTTPS_PROXY': 'http://127.0.0.1:1'}):
                for mode in ('default', 'enable_thinking', 'thinking', 'chat_template'):
                    asyncio.run(exercise(mode))
                    pool = COpenAITokenPool.__new__(COpenAITokenPool)
                    pool.pj_config = SimpleNamespace(stop_event=threading.Event())
                    pool.timeout = 3
                    pool.thinking_mode = mode
                    self.assertTrue(pool._isTokenAvailable_sync(token)[0])
                    for payload in received[-2:]:
                        for key in ('enable_thinking', 'thinking', 'chat_template_kwargs'):
                            if key in thinking_body(mode):
                                self.assertEqual(payload[key], thinking_body(mode)[key])
                            else:
                                self.assertNotIn(key, payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
