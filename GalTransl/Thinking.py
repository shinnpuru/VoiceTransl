"""Translate the reasoning switch to the provider's request format."""

from urllib.parse import urlsplit

from network_utils import is_loopback_endpoint

# Translation-only fine-tunes answer directly and never emit a reasoning block.
# llama.cpp implements "thinking off" by pre-filling an empty `thinking` block
# (see the enable_thinking branch of the Qwen3 chat template), which makes these
# models stop on the very first token and return an empty translation. Leave the
# request untouched for them so the server renders its native prompt.
NON_REASONING_MODEL_HINTS = ('sakura', 'galtransl', 'honyaku', 'translate-gemma')


def is_non_reasoning_finetune(model):
    name = str(model or '').lower()
    return any(hint in name for hint in NON_REASONING_MODEL_HINTS)


def thinking_body(mode=False, endpoint='', model=''):
    # Keep explicit protocols in existing project configurations working.
    if mode == 'enable_thinking':
        return {'enable_thinking': False}
    if mode == 'thinking':
        return {'thinking': {'type': 'disabled'}}
    if mode == 'chat_template':
        return {'chat_template_kwargs': {'enable_thinking': False}}
    if mode == 'default':
        return {}

    enabled = mode is True
    parsed = urlsplit(str(endpoint))
    host = (parsed.hostname or '').lower()

    def matches(domain):
        return host == domain or host.endswith('.' + domain)

    if matches('ollama.com') or parsed.port == 11434:
        return {'reasoning_effort': 'medium' if enabled else 'none'}
    if is_loopback_endpoint(endpoint):
        if not enabled and is_non_reasoning_finetune(model):
            return {}
        return {'chat_template_kwargs': {'enable_thinking': enabled}}
    if any(matches(domain) for domain in (
        'deepseek.com', 'moonshot.cn', 'moonshot.ai', 'bigmodel.cn', 'z.ai',
        'volces.com',
    )):
        return {'thinking': {'type': 'enabled' if enabled else 'disabled'}}
    if any(matches(domain) for domain in (
        'siliconflow.cn', 'siliconflow.com', 'aliyuncs.com',
    )):
        return {'enable_thinking': enabled}
    # Custom gateways commonly expose the Qwen or DeepSeek/GLM protocols.
    model = str(model).lower()
    if any(name in model for name in ('deepseek', 'kimi', 'glm')):
        return {'thinking': {'type': 'enabled' if enabled else 'disabled'}}
    if 'qwen' in model:
        return {'enable_thinking': enabled}
    return {}
