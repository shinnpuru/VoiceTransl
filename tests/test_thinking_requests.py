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
    def test_switch_selects_provider_protocol_and_defaults_to_off(self):
        providers = (
            ('https://api.deepseek.com', 'deepseek-chat', 'thinking'),
            ('https://api.moonshot.cn', 'kimi-k2.5', 'thinking'),
            ('https://api.siliconflow.cn', 'DeepSeek-V3.2', 'enable_thinking'),
            ('https://dashscope.aliyuncs.com/compatible-mode', 'qwen3', 'enable_thinking'),
            ('http://localhost:8989', 'qwen3.gguf', 'chat_template_kwargs'),
            ('http://[::1]:8000', 'qwen3', 'chat_template_kwargs'),
            ('https://gateway.example/v1', 'qwen3', 'enable_thinking'),
            ('https://gateway.example/v1', 'deepseek-chat', 'thinking'),
            ('http://localhost:11434', 'qwen3', 'reasoning_effort'),
        )
        for endpoint, model, key in providers:
            for enabled in (False, True):
                expected = {
                    'thinking': {'type': 'enabled' if enabled else 'disabled'},
                    'enable_thinking': enabled,
                    'chat_template_kwargs': {'enable_thinking': enabled},
                    'reasoning_effort': 'medium' if enabled else 'none',
                }
                with self.subTest(endpoint=endpoint, enabled=enabled):
                    self.assertEqual(thinking_body(enabled, endpoint, model), {key: expected[key]})
        self.assertEqual(thinking_body(endpoint='http://localhost:8989'),
                         {'chat_template_kwargs': {'enable_thinking': False}})
        self.assertEqual(thinking_body(False, 'https://api.example.org', 'unrecognized'), {})

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
            if mode is None:
                del translator.thinking_mode
            try:
                result, _ = await asyncio.wait_for(translator.ask_chatbot(prompt='test'), 8)
                self.assertEqual(result, 'OK')
            finally:
                await client.close()
        try:
            with patch.dict(os.environ, {'HTTP_PROXY': 'http://127.0.0.1:1', 'HTTPS_PROXY': 'http://127.0.0.1:1'}):
                for mode in ('default', 'enable_thinking', 'thinking', 'chat_template', False, True, None):
                    asyncio.run(exercise(mode))
                    pool = COpenAITokenPool.__new__(COpenAITokenPool)
                    pool.pj_config = SimpleNamespace(stop_event=threading.Event())
                    pool.timeout = 3
                    pool.thinking_mode = mode
                    if mode is None:
                        del pool.thinking_mode
                    self.assertTrue(pool._isTokenAvailable_sync(token)[0])
                    expected = thinking_body(mode, token.domain, token.model_name)
                    for payload in received[-2:]:
                        for key in ('enable_thinking', 'thinking', 'chat_template_kwargs'):
                            if key in expected:
                                self.assertEqual(payload[key], expected[key])
                            else:
                                self.assertNotIn(key, payload)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
