"""Normalize file inputs and decode text without locale-dependent guessing."""
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname


def normalize_input(value):
    value = str(value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    if value.lower().startswith('file:'):
        parsed = urlsplit(value)
        value = url2pathname(parsed.path)
        if parsed.netloc and parsed.netloc.lower() != 'localhost':
            value = '//' + parsed.netloc + value
        # Preserve Windows drive paths when reading settings on other platforms.
        if re.match(r'^/[a-zA-Z]:/', value):
            value = value[1:]
    return os.path.expanduser(value)


def is_remote_input(value):
    return urlsplit(value).scheme.lower() in ('http', 'https')


def read_subtitle_text(path):
    data = Path(path).read_bytes()
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        # Older Windows subtitle tools commonly produce GBK/GB18030.
        return data.decode('gb18030')


def native_model_path(path):
    """Use Windows' existing short alias for native runtimes with narrow paths."""
    path = str(Path(path).resolve())
    if os.name != 'nt' or path.isascii():
        return path
    import ctypes
    from ctypes import wintypes
    get_short_path = ctypes.windll.kernel32.GetShortPathNameW
    get_short_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    get_short_path.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    size = get_short_path(path, buffer, len(buffer))
    if 0 < size < len(buffer) and buffer.value.isascii():
        return buffer.value
    parent = Path(path).parent
    if not Path(path).exists() and parent.exists() and Path(path).name.isascii():
        short_parent = native_model_path(parent)
        return str(Path(short_parent) / Path(path).name)
    raise ValueError(
        f'CrispASR cannot use this non-ASCII path without a Windows short alias: {path}. '
        'Move the application/models to an ASCII directory (for example C:/VoiceTransl).'
    )
