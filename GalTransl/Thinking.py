"""Provider-specific, opt-in controls for disabling model reasoning."""


def thinking_body(mode):
    if mode == 'enable_thinking':
        return {'enable_thinking': False}
    if mode == 'thinking':
        return {'thinking': {'type': 'disabled'}}
    if mode == 'chat_template':
        return {'chat_template_kwargs': {'enable_thinking': False}}
    return {}
