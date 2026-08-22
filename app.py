import sys, os
import shutil
from pathlib import Path


_FROZEN = hasattr(sys, '_MEIPASS')


def _ensure_resource_link(source: Path, target: Path) -> None:
    """Create or refresh a link to a read-only bundled resource."""
    if target.is_symlink():
        try:
            if target.resolve(strict=False) == source.resolve(strict=False):
                return
        except OSError:
            pass
        target.unlink()
    elif target.exists():
        # Preserve user-created files and directories in the data directory.
        return

    target.symlink_to(source, target_is_directory=source.is_dir())


def _copy_missing_tree(source: Path, target: Path) -> None:
    """Copy bundled defaults without overwriting user data."""
    if not source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        return

    for source_item in source.rglob('*'):
        relative = source_item.relative_to(source)
        target_item = target / relative
        if source_item.is_dir():
            target_item.mkdir(parents=True, exist_ok=True)
        elif not target_item.exists() and not target_item.is_symlink():
            target_item.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_item, target_item)


def _prepare_mutable_resource_dir(
        resource_root: Path, data_root: Path, directory: str,
        mutable_files: set[str]) -> None:
    """Overlay writable files on top of a bundled resource directory."""
    source_dir = resource_root / directory
    target_dir = data_root / directory
    target_dir.mkdir(parents=True, exist_ok=True)
    if not source_dir.is_dir():
        return

    for source_item in source_dir.iterdir():
        target_item = target_dir / source_item.name
        if source_item.name in mutable_files:
            if target_item.is_symlink():
                # Migrate an older linked parameter file to writable storage.
                content = target_item.read_bytes() if target_item.exists() else source_item.read_bytes()
                target_item.unlink()
                target_item.write_bytes(content)
            elif not target_item.exists():
                shutil.copy2(source_item, target_item)
        else:
            _ensure_resource_link(source_item, target_item)


def _configure_working_directory() -> tuple[Path, Path]:
    """Select resource and writable runtime roots without changing Windows."""
    source_root = Path(__file__).resolve().parent
    if not _FROZEN:
        os.chdir(source_root)
        return source_root, source_root

    resource_root = Path(sys._MEIPASS).resolve()
    if sys.platform != 'darwin':
        # Keep the existing Windows/Linux frozen-app behavior unchanged.
        os.chdir(resource_root)
        return resource_root, resource_root

    configured_data_root = os.environ.get('VOICETRANSL_DATA_DIR')
    data_root = (
        Path(configured_data_root).expanduser()
        if configured_data_root
        else Path.home() / 'Library' / 'Application Support' / 'VoiceTransl'
    )
    data_root.mkdir(parents=True, exist_ok=True)

    for name in (
            'assets', 'separate', 'plugins', 'ffmpeg', 'translate',
            'translation_guidelines', 'icon.png', 'avatar.png'):
        source = resource_root / name
        if source.exists():
            _ensure_resource_link(source, data_root / name)

    _prepare_mutable_resource_dir(
        resource_root, data_root, 'llama', {'param.txt'})
    _prepare_mutable_resource_dir(
        resource_root, data_root, 'crispasr', {'param.txt'})
    _copy_missing_tree(resource_root / 'project', data_root / 'project')

    os.chdir(data_root)
    return resource_root, data_root


_RESOURCE_ROOT, _RUNTIME_ROOT = _configure_working_directory()
# PyInstaller 打包后使用独立 exe，源码运行时使用 python 脚本
_TRANSLATE_CMD = ['translate/translate'] if _FROZEN else [sys.executable, 'translate.py']
_SEPARATE_CMD = ['separate/separate'] if _FROZEN else [sys.executable, 'separate.py']
import shlex
import socket
import tempfile

def _resolve_ffmpeg() -> tuple[str, str]:
    """解析 ffmpeg/ffprobe 路径"""
    if os.name == 'nt':
        _ffmpeg = 'ffmpeg/ffmpeg.exe'
        _ffprobe = 'ffmpeg/ffprobe.exe'
    else:
        _ffmpeg = 'ffmpeg/ffmpeg'
        _ffprobe = 'ffmpeg/ffprobe'

    # 优先使用本地 ffmpeg 目录
    if not os.path.exists(_ffmpeg):
        # 回退检查系统 PATH
        _ffmpeg = shutil.which('ffmpeg') or _ffmpeg
        _ffprobe = shutil.which('ffprobe') or _ffprobe

    if not os.path.exists(_ffmpeg):
        raise RuntimeError(
            '未找到 ffmpeg，请将 ffmpeg.exe 放置在 ffmpeg 目录中，'
            '或安装 ffmpeg 并添加到系统 PATH 环境变量'
        )

    return _ffmpeg, _ffprobe

_FFMPEG, _FFPROBE = _resolve_ffmpeg()
from i18n import _, set_language, get_language
from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer, QDateTime, QSize
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QFileDialog, QFrame, QSystemTrayIcon, QMenu,
    QAction, QHBoxLayout, QCheckBox, QDialog, QLabel, QWidget, QLayout,
    QStackedWidget,
)
from qfluentwidgets import PushButton as QPushButton, TextEdit as QTextEdit, LineEdit as QLineEdit, ComboBox as QComboBox, Slider as QSlider, PlainTextEdit as QPlainTextEdit, SplashScreen, SpinBox as QSpinBox
from qfluentwidgets import (
    FluentIcon, NavigationItemPosition, SubtitleLabel, TitleLabel, BodyLabel,
    FluentWindow as QMainWindow, TabBar, ScrollArea,
    SimpleCardWidget,
)

import re
import asyncio
import json
import yaml
import threading
import queue

from dataclasses import dataclass
import requests
import httpx
from openai import OpenAI
import subprocess
from time import sleep, time
from yt_dlp import YoutubeDL
from bilibili_dl.bilibili_dl.Video import Video
from bilibili_dl.bilibili_dl.downloader import download
from bilibili_dl.bilibili_dl.utils import send_request
from bilibili_dl.bilibili_dl.constants import URL_VIDEO_INFO
NO_TRANSCRIPTION = '不进行听写'
NO_TRANSLATION = '不进行翻译'


def _list_crispasr_models():
    model_dir = Path('crispasr')
    if not model_dir.is_dir():
        return []
    return sorted(
        path.name for path in model_dir.glob('*.gguf')
        if 'aligner' not in path.name.lower() and 'alignment' not in path.name.lower()
    )


def _list_crispasr_aligners():
    model_dir = Path('crispasr')
    if not model_dir.is_dir():
        return []
    return sorted(
        path.name for path in model_dir.glob('*.gguf')
        if 'aligner' in path.name.lower() or 'alignment' in path.name.lower()
    )


def _list_crispasr_backends():
    """Return speech-recognition backends advertised by the local binary."""
    fallback = [
        'whisper', 'parakeet', 'canary', 'cohere', 'qwen3', 'qwen3-1.7b',
        'mega-asr', 'voxtral', 'voxtral4b', 'granite',
    ]
    crispasr_dir = Path('crispasr').resolve()
    executable_name = 'crispasr.exe' if os.name == 'nt' else 'crispasr'
    executable = crispasr_dir / executable_name
    if not executable.is_file():
        return fallback

    try:
        result = subprocess.run(
            [str(executable), '--list-backends-json'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=10,
            creationflags=0x08000000 if os.name == 'nt' else 0,
            check=False,
        )
        payload = json.loads(result.stdout)
        non_asr_caps = {'tts', 's2s', 'separate', 'pitch', 'chords', 'beats', 'tab', 'piano'}
        asr_caps = {
            'timestamps-native', 'timestamps-ctc', 'word-timestamps',
            'token-confidence', 'language-detect', 'diarize',
        }
        backends = []
        for entry in payload.get('backends', []):
            name = str(entry.get('name', '')).strip()
            caps = set(entry.get('caps') or [])
            if name and caps.intersection(asr_caps) and not (
                caps.intersection(non_asr_caps) and not caps.intersection({'timestamps-ctc', 'word-timestamps'})
            ):
                backends.append(name)
        if backends:
            return list(dict.fromkeys(backends))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        pass
    return fallback


def _split_command_template(value):
    if os.name != 'nt':
        return shlex.split(value)
    tokens = shlex.split(value, posix=False)
    return [
        token[1:-1] if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'" else token
        for token in tokens
    ]


def _set_command_option(command, option_names, preferred_option, value):
    """Set an option in a split command, appending it when the template omits it."""
    for index, token in enumerate(command):
        if token in option_names:
            if index + 1 < len(command):
                command[index + 1] = value
            else:
                command.append(value)
            return
        for option_name in option_names:
            if token.startswith(option_name + '='):
                command[index] = f'{preferred_option}={value}'
                return
    command.extend([preferred_option, value])


def _build_crispasr_command(
    input_file, output_file, model_file, language, param_crispasr,
    aligner_file=None, backend=None,
):
    """按 param.txt 模板替换占位符，生成与旧 Whisper 相同风格的启动参数。"""
    crispasr_dir = Path('crispasr').resolve()
    executable_name = 'crispasr.exe' if os.name == 'nt' else 'crispasr'
    executable = crispasr_dir / executable_name
    if not executable.is_file():
        raise FileNotFoundError(f'CrispASR executable not found: {executable}')

    model_path = Path(model_file)
    if not model_path.is_absolute():
        model_path = crispasr_dir / model_path

    if aligner_file:
        aligner_path = Path(aligner_file)
        if not aligner_path.is_absolute():
            aligner_path = crispasr_dir / aligner_path
    else:
        aligners = _list_crispasr_aligners()
        if not aligners:
            raise FileNotFoundError(f'CrispASR aligner model not found in: {crispasr_dir}')
        aligner_path = crispasr_dir / aligners[0]
    if not aligner_path.is_file():
        raise FileNotFoundError(f'CrispASR aligner model not found: {aligner_path}')

    selected_backend = str(backend or 'qwen3-1.7b').strip() or 'qwen3-1.7b'
    replacements = {
        '$crispasr_executable': str(executable),
        '$model_file': str(model_path.resolve()),
        '$aligner_file': str(aligner_path.resolve()),
        '$backend': selected_backend,
        '$language': language or 'auto',
        '$output_file': str(Path(output_file).resolve()),
        '$input_file': str(Path(input_file).resolve()),
    }
    command = _split_command_template(param_crispasr)
    for index, token in enumerate(command):
        for placeholder, replacement in replacements.items():
            token = token.replace(placeholder, replacement)
        command[index] = token
    if not command:
        raise ValueError('CrispASR param.txt is empty')
    _set_command_option(command, ('--backend',), '--backend', selected_backend)
    _set_command_option(command, ('--aligner-model', '-am'), '--aligner-model', str(aligner_path.resolve()))
    return command


def _format_command(command):
    return subprocess.list2cmdline(command) if os.name == 'nt' else shlex.join(command)


def _build_llama_server_command(model_file, gpu_layers, param_llama, port):
    """Build the llama-server command used by both normal runs and self-tests."""
    llama_dir = Path('llama').resolve()
    model_path = Path(model_file)
    if not model_path.is_absolute():
        model_path = llama_dir / model_path
    model_path = model_path.resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f'Offline translation model not found: {model_path}')

    command = _split_command_template(param_llama)
    if not command:
        raise ValueError('llama/param.txt is empty')

    replacements = {
        '$num_layers': str(gpu_layers or '0'),
        '$port': str(port),
    }
    model_value = str(model_path)
    for index, token in enumerate(command):
        token = token.replace('llama/$model_file', model_value)
        token = token.replace(r'llama\$model_file', model_value)
        token = token.replace('$model_file', model_value)
        for placeholder, replacement in replacements.items():
            token = token.replace(placeholder, replacement)
        command[index] = token

    unresolved = [token for token in command if re.search(r'\$[A-Za-z_]+', token)]
    if unresolved:
        raise ValueError(f'Unresolved llama-server placeholders: {unresolved}')

    executable = Path(command[0])
    if not executable.is_absolute():
        executable = Path.cwd() / executable
    if os.name == 'nt' and not executable.is_file() and not executable.suffix:
        executable = Path(str(executable) + '.exe')
    if executable.is_file():
        command[0] = str(executable.resolve())
    elif shutil.which(command[0]) is None:
        raise FileNotFoundError(f'llama-server executable not found: {command[0]}')

    _set_command_option(command, ('--model', '-m'), '--model', model_value)
    _set_command_option(command, ('--port',), '--port', str(port))
    if str(gpu_layers).strip():
        _set_command_option(
            command, ('--n-gpu-layers', '-ngl'), '--n-gpu-layers',
            str(gpu_layers).strip(),
        )
    return command


def _find_available_local_port():
    """Reserve an unused loopback port long enough to choose a test endpoint."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _offline_asr_test_audio(language):
    """Return the bundled speech sample matching the selected ASR language."""
    language_code = str(language or 'ja').lower()
    if language_code.startswith('zh'):
        language_code = 'zh'
    sample = Path('assets') / 'offline_model_test' / f'{language_code}.mp3'
    if not sample.is_file():
        sample = Path('assets') / 'offline_model_test' / 'en.mp3'
    return sample.resolve()


def open_path(path_value: str):
    target = os.path.abspath(path_value)
    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(target))

from prompt2srt import make_srt, make_lrc, merge_lrc_files
from srt2prompt import make_prompt, merge_srt_files

ONLINE_TRANSLATOR_MAPPING = {
    'Kimi': 'https://api.moonshot.cn',
    'Kimi (国际)': 'https://api.moonshot.ai',
    'GLM': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    'GLM (国际)': 'https://api.z.ai/api/paas/v4/chat/completions',
    'Deepseek': 'https://api.deepseek.com',
    'Minimax': 'https://api.minimaxi.com',
    'Minimax (国际)': 'https://api.minimaxi.io',
    '豆包': 'https://ark.cn-beijing.volces.com/api',
    '阿里云': 'https://dashscope.aliyuncs.com/compatible-mode',
    'Gemini': 'https://generativelanguage.googleapis.com/v1beta/openai',
    'OpenAI': 'https://api.openai.com',
    'Ollama': 'http://localhost:11434',
    "llamacpp（通用本地模型）": "http://localhost:8989",
}

TRANSLATOR_SUPPORTED = [
    "custom（自定义模型）",
    "sakura（日语本地模型）",
] + list(ONLINE_TRANSLATOR_MAPPING.keys())

LOCAL_TRANSLATOR_SUPPORTED = [
    translator for translator in TRANSLATOR_SUPPORTED
    if 'sakura' in translator or 'llamacpp' in translator
]
ONLINE_TRANSLATOR_SUPPORTED = [
    translator for translator in TRANSLATOR_SUPPORTED
    if translator not in LOCAL_TRANSLATOR_SUPPORTED
]


def _compose_output_format(content_type, file_type, enable_translation):
    """Build a valid output format for the actions selected on the input tab."""
    if not enable_translation:
        content_type = '原文'
    return f'{content_type}{file_type}'


def _split_output_format(output_format):
    """Split values such as ``双语SRT`` without assuming a fixed suffix width."""
    for file_type in ('SRT', 'LRC'):
        if output_format.endswith(file_type):
            return output_format[:-len(file_type)], file_type
    return output_format, ''

# redirect sys.stdout and sys.stderr to one log file
LOG_PATH = 'log.log'
sys.stdout = open(LOG_PATH, 'w', encoding='utf-8')
sys.stderr = sys.stdout

# ANSI 转义序列正则（覆盖 CSI、OSC、前景/背景色等）
_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def _strip_ansi(text: str) -> str:
    """移除 ANSI 转义序列"""
    return _ANSI_ESCAPE.sub('', text)

# 统一消息队列，所有消息都通过此队列流转
# 消息格式：(target: str, text: str)
#   target="status" → 上层"实时输出信息"框
#   target="detail" → 下层"日志文件"框
#   target="__COMPLETION__" → 完成哨兵，两个框都追加完成提示

class UIMessageQueue:
    """统一消息队列：线程安全，替代分散的日志写入和信号发射"""

    _COMPLETION_TARGET = "__COMPLETION__"
    _MAX_SIZE = 10000
    _DRAIN_EMPTY_LIMIT = 3       # drain_all 连续空返回次数上限
    _DRAIN_POLL_INTERVAL = 0.1   # drain_all 轮询间隔（秒）
    _DRAIN_MAX_WAIT = 3.0        # drain_all 最长等待（秒）

    def __init__(self, log_path: str = 'log.log'):
        self._queue: queue.Queue = queue.Queue(maxsize=self._MAX_SIZE)
        self._log_path = log_path
        self._file_lock = threading.Lock()
        self._completion_flag = threading.Event()

    def put(self, target: str, text: str) -> None:
        """线程安全地放入一条消息。target 为 'status' 或 'detail'。

        满时丢弃最旧消息（FIFO），避免 OOM。
        同时写入日志文件（自动剥离 ANSI 码）。
        """
        # 写入日志文件
        cleaned = _strip_ansi(text)
        if cleaned.strip():
            with self._file_lock:
                try:
                    with open(self._log_path, 'a', encoding='utf-8', errors='replace') as f:
                        f.write(cleaned + '\n')
                except Exception:
                    pass

        # 放入队列
        entry = (target, text)
        try:
            self._queue.put(entry, block=False)
        except queue.Full:
            # 丢弃最旧消息，放入新消息
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put(entry, block=False)
            except queue.Full:
                pass  # 极端情况：忽略

    def drain(self) -> list[tuple[str, str]]:
        """非阻塞地取出当前队列中所有消息。"""
        entries: list[tuple[str, str]] = []
        while True:
            try:
                entries.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return entries

    def drain_all(self, timeout: float | None = None) -> list[tuple[str, str]]:
        """阻塞式排空队列，直到连续 N 次空返回或超时。

        用于确保所有工作线程的消息已被取出。
        """
        if timeout is None:
            timeout = self._DRAIN_MAX_WAIT

        all_entries: list[tuple[str, str]] = []
        empty_streak = 0
        start = time()
        while empty_streak < self._DRAIN_EMPTY_LIMIT:
            batch = self.drain()
            if batch:
                all_entries.extend(batch)
                empty_streak = 0
            else:
                empty_streak += 1
                sleep(self._DRAIN_POLL_INTERVAL)
            if time() - start > timeout:
                break
        return all_entries

    def set_completion_flag(self) -> None:
        """标记翻译池已完成（原子操作）。"""
        self._completion_flag.set()

    def is_completion_ready(self) -> bool:
        """检查翻译池是否已完成。"""
        return self._completion_flag.is_set()

    def put_completion_sentinel(self) -> None:
        """放入完成哨兵消息（在 drain_all 之后调用）。"""
        self._queue.put((self._COMPLETION_TARGET, ''), block=False)

    @staticmethod
    def is_completion_entry(target: str) -> bool:
        """判断是否为完成哨兵。"""
        return target == UIMessageQueue._COMPLETION_TARGET

# 日志级别过滤辅助函数（模块级，供 read_log_file 调用）
def _line_passes_filter(line: str, filter_level: str) -> bool:
    """判断日志行是否通过级别过滤"""
    if filter_level == 'ALL':
        return True
    m = re.search(r'\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]', line)
    if not m:
        return True  # 无级别标记的行始终显示
    ranks = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
    thresholds = {'INFO+': 1, 'WARNING+': 2, 'ERROR+': 3}
    return ranks.get(m.group(1), 0) >= thresholds.get(filter_level, 0)

def _clean_control_chars(text: str) -> str:
    """清理日志行中的控制字符

    - \\r 处理：取最长段落（通常是实际内容，短段为进度条碎片）
    - 移除其他控制符（保留 \\t 和 \\n）
    - 清理进度条 \\r 残留的三字符前缀（如 yg2|、a0n|、23b|）
    """
    if '\r' in text:
        parts = text.split('\r')
        # 保留最长段落：实际日志内容远长于进度条碎片（yg2| 等仅4字符）
        text = max(parts, key=len)
    # 移除 0x00-0x08, 0x0B-0x0C, 0x0E-0x1F 范围的控制字符，保留 \\t (0x09) 和 \\n (0x0A)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    # 清理进度条碎片前缀：三个小写字母/数字 + 竖线（如 yg2|、a0n|、23b|）
    text = re.sub(r'^[a-z0-9]{3}\|', '', text)
    return text


def _decode_subprocess_line(data: bytes) -> str:
    """按 UTF-8→GBK→latin-1 顺序尝试解码子进程输出字节。"""
    for enc in ('utf-8', 'gbk', 'latin-1'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')


def _stream_proc_to_queue(proc, msg_queue, label=None):
    """后台线程目标：将子进程 stdout/stderr 流式转发到统一消息队列（target='detail'）。

    读取二进制并解码、剥离 ANSI/控制字符后入队（同时写入日志文件）。
    进程结束后自动关闭管道。
    """
    stream = proc.stdout
    if stream is None:
        return
    prefix = f"[{label}] " if label else ""
    try:
        for raw in iter(stream.readline, b''):
            if not raw:
                break
            line = _decode_subprocess_line(raw)
            line = _clean_control_chars(_strip_ansi(line.rstrip('\n\r')))
            if line.strip():
                msg_queue.put("detail", prefix + line)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


# GalTransl 逐行翻译输出解析器：将三行格式转换为 JSON，并按批次分组
# 原始格式:  v--{id}[-{speaker}]\n> Src: {text}\n> Dst: {text}
# 目标格式:  同一批次的所有 src 先输出，再输出所有 dst（纯 JSON，无前缀）
_TRANSLATION_LINE_RE = re.compile(r'^v--(\d+)')

class _TranslationLogParser:
    """将 GalTransl 逐行翻译记录转换为结构化 JSON，src/dst 分组输出"""

    def __init__(self):
        self._line_buf: list[str] = []      # 当前翻译条目的三行缓冲
        self._batch_src: list[str] = []     # 当前批次的 src JSON 行
        self._batch_dst: list[str] = []     # 当前批次的 dst JSON 行

    def feed(self, line: str) -> list[str]:
        """输入一行，返回转换后的零行或多行（批次边界时刷新）"""
        # 匹配翻译输出头部 v--{id}[-{speaker}]
        header_m = _TRANSLATION_LINE_RE.match(line)
        if header_m:
            # 新条目开始，刷新不完整的行缓冲
            flushed = self._flush_line_buf()
            self._line_buf = [line]
            return flushed

        if self._line_buf:
            if line.startswith('> Src: '):
                self._line_buf.append(line)
                return []
            if line.startswith('> Dst: '):
                self._line_buf.append(line)
                self._add_to_batch()
                self._line_buf = []
                return []
            # 模式中断：刷新所有缓冲区
            return self._flush_all() + [line]

        # 非翻译行：如果批次中有累积的翻译，先刷新批次
        flushed = self._flush_batch()
        if flushed:
            return flushed + [line]
        return [line]

    def flush(self) -> list[str]:
        """最终刷新所有残留缓冲"""
        return self._flush_all()

    # 内部方法

    def _add_to_batch(self):
        """将三行缓冲转换为 JSON 并添加到批次"""
        if len(self._line_buf) != 3:
            return
        header, src_line, dst_line = self._line_buf
        id_m = _TRANSLATION_LINE_RE.match(header)
        if not id_m:
            return
        trans_id = id_m.group(1)
        src_text = src_line[7:]   # 去掉 "> Src: " 前缀
        dst_text = dst_line[7:]   # 去掉 "> Dst: " 前缀
        self._batch_src.append(json.dumps(
            {"id": int(trans_id), "src": src_text}, ensure_ascii=False))
        self._batch_dst.append(json.dumps(
            {"id": int(trans_id), "dst": dst_text}, ensure_ascii=False))

    def _flush_line_buf(self) -> list[str]:
        """刷新不完整的行缓冲（模式中断时保留原始文本）"""
        result = self._line_buf
        self._line_buf = []
        return result

    def _flush_batch(self) -> list[str]:
        """刷新累积的批次：只输出 dst（翻译结果）"""
        if not self._batch_dst:
            return []
        result = list(self._batch_dst)
        self._batch_src = []
        self._batch_dst = []
        return result

    def _flush_all(self) -> list[str]:
        """刷新所有缓冲"""
        return self._flush_line_buf() + self._flush_batch()

@dataclass
class TranscribedFile:
    """已听写完成的文件上下文，传递给翻译线程"""
    base_path: str       # 文件基本路径（无扩展名），如 /path/to/file
    json_src: str        # 听写产出的 JSON 路径（在 cache/transcribed/ 下）
    output_dir: str      # 该文件的输出目录
    output_format: str   # 输出格式（如 '目标SRT', '双语SRT'）
    orig_srt_path: str   # 原始 SRT 路径（用于双语合并，空串表示无）


class ConcurrentTranslationPool:
    """并发翻译线程池：每文件一个工作线程，工作空间隔离"""

    verbose_galtransl: bool = False  # 类变量：详细模式开关，由 MainWindow 在启动翻译前设置

    @staticmethod
    def _translate_worker_thread(task_queue, result_queue, msg_queue, stop_event,
                                 project_dir, base_config_path, engine, worker_idx):
        """工作线程函数：从队列取任务并执行翻译"""
        while not stop_event.is_set():
            try:
                tf_dict = task_queue.get(timeout=1)
            except queue.Empty:
                continue

            if tf_dict is None:  # 哨兵信号
                result_queue.put(('done', worker_idx))
                break

            if stop_event.is_set():
                result_queue.put(('stopped', worker_idx))
                continue

            # 执行翻译
            try:
                ConcurrentTranslationPool._translate_one_impl(
                    tf_dict, worker_idx, project_dir, base_config_path, engine, msg_queue)
                result_queue.put(('success', worker_idx))
            except Exception as e:
                result_queue.put(('error', worker_idx, str(e)))

    @staticmethod
    def _translate_one_impl(tf_dict, worker_idx, project_dir, base_config_path,
                            engine, msg_queue):
        """在线程中执行单个文件的翻译"""
        base_path = tf_dict['base_path']
        json_src = tf_dict['json_src']
        output_dir = tf_dict['output_dir']
        output_format = tf_dict['output_format']
        orig_srt_path = tf_dict['orig_srt_path']

        base = os.path.basename(base_path)

        def send_status(msg):
            """向统一消息队列发送后端详细日志"""
            msg_queue.put("detail", msg)

        send_status(_("status_translating_start", idx=worker_idx, base=base))

        # 创建工作空间
        workspace = ConcurrentTranslationPool._create_workspace_impl(project_dir, worker_idx)
        json_name = os.path.basename(json_src)

        # 将听写产出的 JSON 复制到工作空间的 gt_input
        shutil.copy(json_src, os.path.join(workspace, 'gt_input', json_name))

        # 准备独立配置文件
        ConcurrentTranslationPool._prepare_config_impl(workspace, base_config_path, project_dir)

        try:
            send_status(_("status_translating_with", idx=worker_idx, engine=engine, workspace=workspace))
            creationflags = 0x08000000 if os.name == 'nt' else 0

            # Force the translation subprocess and this reader to agree on
            # UTF-8. Windows otherwise selects GBK for redirected pipes, and
            # valid filename characters such as ♪ make logging.StreamHandler
            # emit an internal UnicodeEncodeError traceback.
            proc_env = os.environ.copy()
            proc_env['PYTHONIOENCODING'] = 'utf-8'
            proc_env['PYTHONUTF8'] = '1'
            if ConcurrentTranslationPool.verbose_galtransl:
                proc_env['GALTRANSL_VERBOSE_STDOUT'] = '1'

            proc = subprocess.Popen(
                [*_TRANSLATE_CMD, workspace, engine],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                creationflags=creationflags, bufsize=1,
                env=proc_env,
            )

            # 翻译日志解析器：将 GalTransl 三行格式转换为 JSON
            _trans_parser = _TranslationLogParser()

            for line in iter(proc.stdout.readline, ''):
                # 清除 ANSI 转义序列和控制字符
                cleaned = _clean_control_chars(_strip_ansi(line.rstrip('\n\r')))
                if not cleaned:
                    continue
                # 通过解析器转换翻译输出格式（JSON 化），逐行写入日志和发送到 GUI
                for output_line in _trans_parser.feed(cleaned):
                    if output_line.strip():
                        send_status(output_line)

            # 刷新解析器缓冲区中残留的行
            for output_line in _trans_parser.flush():
                if output_line.strip():
                    send_status(output_line)

            proc.stdout.close()
            retcode = proc.wait()

            # 短暂等待，确保状态队列中的日志已排空发送到 GUI
            send_status(_("status_translate_proc_ended", idx=worker_idx, retcode=retcode))
            sleep(0.1)
            if retcode != 0:
                raise subprocess.CalledProcessError(retcode, _TRANSLATE_CMD)
        except Exception as e:
            send_status(_("status_translating_error", idx=worker_idx, base=base, error=e))
            raise

        # 生成翻译后字幕
        send_status(_("status_translating_srt", idx=worker_idx, base=base))
        ConcurrentTranslationPool._generate_output_impl(
            json_src, base_path, output_dir, output_format, workspace, orig_srt_path)

        send_status(_("status_translating_done", idx=worker_idx, base=base))

    @staticmethod
    def _create_workspace_impl(project_dir, worker_idx):
        """在线程中创建工作空间"""
        import time
        idx = int(time.time() * 1000000) + worker_idx
        workspace = os.path.join(project_dir, 'cache', f'translate_{idx}')
        for sub in ('gt_input', 'gt_output', 'transl_cache'):
            os.makedirs(os.path.join(workspace, sub), exist_ok=True)
        return workspace

    @staticmethod
    def _prepare_config_impl(workspace, base_config_path, project_dir):
        """在线程中准备配置文件"""
        with open(base_config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        abs_project_dir = os.path.abspath(project_dir).replace('\\', '/')
        content = content.replace('(project_dir)', abs_project_dir + '/')

        # 强制启用 saveLog：使 GalTransl 将完整日志写入 workspace/GalTransl.log
        content = re.sub(
            r'^(\s*)saveLog:\s*(?:true|false)\s*$',
            r'\1saveLog: true',
            content,
            flags=re.MULTILINE,
        )

        config_path = os.path.join(workspace, 'config.yaml')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return config_path

    @staticmethod
    def _generate_output_impl(json_src, base_path, output_dir, output_format, workspace, orig_srt_path=''):
        """在线程中生成输出文件"""
        json_name = os.path.basename(json_src)
        gt_output_json = os.path.join(workspace, 'gt_output', json_name)
        base_name = os.path.basename(base_path)

        if output_format in ('目标SRT', '双语SRT'):
            zh_srt_output = os.path.join(output_dir, base_name + '.tg.srt')
            make_srt(gt_output_json, zh_srt_output)

        if output_format in ('目标LRC', '双语LRC'):
            lrc_output = os.path.join(output_dir, base_name + '.lrc')
            make_lrc(gt_output_json, lrc_output)

        if output_format == '双语SRT':
            left = os.path.join(output_dir, base_name + '.srt')
            right = os.path.join(output_dir, base_name + '.tg.srt')
            if os.path.exists(left) and os.path.exists(right):
                merge_srt_files([left, right],
                                os.path.join(output_dir, base_name + '.combine.srt'))

        if output_format == '双语LRC':
            left = os.path.join(output_dir, base_name + '.orig.lrc')
            right = os.path.join(output_dir, base_name + '.zh.lrc')
            if os.path.exists(left) and os.path.exists(right):
                merge_lrc_files([left, right],
                                os.path.join(output_dir, base_name + '.combine.lrc'))

        if output_format not in ('双语SRT', '原文SRT'):
            left = os.path.join(output_dir, base_name + '.srt')
            if os.path.exists(left):
                os.remove(left)

    def __init__(self, project_dir, base_config_path, max_concurrent, stop_event,
                 msg_queue, local_model_config=None):
        """
        msg_queue: 统一消息队列（UIMessageQueue 实例）
        local_model_config: 本地模型配置，用于多线程本地模型翻译
            {
                'sakura_file': str,      # 模型文件路径
                'sakura_mode': str,      # GPU层数
                'param_llama': str,      # llama.cpp 参数
            }
        """
        self._project_dir = project_dir
        self._base_config_path = base_config_path
        self._max_concurrent = max_concurrent
        self._stop_event = stop_event
        self._msg_queue = msg_queue
        self._local_model_config = local_model_config
        self._task_queue = queue.Queue()
        self._result_queue = queue.Queue()
        self._active_threads: list[threading.Thread] = []
        self._error_count = 0
        self._error_lock = threading.Lock()
        # 本地模型相关（所有进程共享一个本地模型）
        self._shared_local_model_proc = None
        self._shared_local_model_port = None
        self._local_model_lock = threading.Lock()
        # 串行模式相关
        self._serial_mode = max_concurrent <= 0
        self._serial_lock = threading.Lock()
        self._engine = None
        # 跟踪 GalTransl 子进程用于取消时终止
        self._active_translate_procs: list[subprocess.Popen] = []
        self._procs_lock = threading.Lock()

    @property
    def error_count(self):
        with self._error_lock:
            return self._error_count

    def start(self, engine):
        """启动 N 个工作线程"""
        self._engine = engine

        # 串行模式：不启动工作进程
        if self._serial_mode:
            return

        # 如果配置了本地模型，启动一个共享的本地模型实例
        if self._local_model_config and self._local_model_config.get('sakura_file'):
            proc, port = self._start_local_model(0)
            if proc:
                with self._local_model_lock:
                    self._shared_local_model_proc = proc
                    self._shared_local_model_port = port
            else:
                self._msg_queue.put("status", _("status_local_model_start_fail"))

        # 创建线程事件
        self._thread_stop_event = threading.Event()

        # 并发模式：启动多个工作线程
        for i in range(self._max_concurrent):
            t = threading.Thread(
                target=ConcurrentTranslationPool._translate_worker_thread,
                args=(self._task_queue, self._result_queue, self._msg_queue,
                      self._thread_stop_event, self._project_dir, self._base_config_path,
                      engine, i),
                daemon=True
            )
            self._active_threads.append(t)
            t.start()

    def submit(self, tf):
        """提交翻译任务"""
        if self._serial_mode:
            # 串行模式
            with self._serial_lock:
                if self._stop_event.is_set():
                    return

                # 启动共享本地模型
                if self._local_model_config and self._local_model_config.get('sakura_file'):
                    with self._local_model_lock:
                        if not self._shared_local_model_proc:
                            proc, port = self._start_local_model(0)
                            if proc:
                                self._shared_local_model_proc = proc
                                self._shared_local_model_port = port
                            else:
                                self._msg_queue.put("status", _("status_local_model_start_fail"))

                # 执行翻译（在调用线程中同步执行）
                tf_dict = {
                    'base_path': tf.base_path,
                    'json_src': tf.json_src,
                    'output_dir': tf.output_dir,
                    'output_format': tf.output_format,
                    'orig_srt_path': tf.orig_srt_path,
                }
                try:
                    ConcurrentTranslationPool._translate_one_impl(
                        tf_dict, 0, self._project_dir, self._base_config_path,
                        self._engine, self._msg_queue)
                except Exception as e:
                    with self._error_lock:
                        self._error_count += 1
                    self._msg_queue.put("status", _("status_translation_fail", error=e))

                # 停止共享本地模型
                self._stop_shared_local_model()
        else:
            # 并发模式：放入队列
            tf_dict = {
                'base_path': tf.base_path,
                'json_src': tf.json_src,
                'output_dir': tf.output_dir,
                'output_format': tf.output_format,
                'orig_srt_path': tf.orig_srt_path,
            }
            self._task_queue.put(tf_dict)

    def done(self):
        """所有任务已提交，发送哨兵信号"""
        if self._serial_mode:
            return
        for _unused in range(self._max_concurrent):
            self._task_queue.put(None)

    def wait_all(self, timeout=600):
        """等待所有工作线程结束"""
        if self._serial_mode:
            return

        # 等待所有线程结束
        for t in self._active_threads:
            t.join(timeout=timeout / len(self._active_threads) if self._active_threads else timeout)

        # 处理结果队列中的错误
        while True:
            try:
                result = self._result_queue.get_nowait()
                if result[0] == 'error':
                    with self._error_lock:
                        self._error_count += 1
            except queue.Empty:
                break

        # 排空统一消息队列中可能残留的后端日志
        self._msg_queue.drain_all(timeout=2.0)

    def stop(self):
        """停止所有工作线程和子进程"""
        # 设置停止事件
        self._stop_event.set()
        if hasattr(self, '_thread_stop_event'):
            self._thread_stop_event.set()

        # 终止所有在途的 GalTransl 翻译子进程
        with self._procs_lock:
            for proc in self._active_translate_procs:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                except Exception:
                    pass
            # 等待子进程终止
            for proc in self._active_translate_procs:
                try:
                    proc.wait(timeout=3)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            self._active_translate_procs.clear()

        # 清空任务队列（丢弃未处理的任务）
        while True:
            try:
                self._task_queue.get_nowait()
            except queue.Empty:
                break

        # 等待所有工作线程结束
        for t in self._active_threads:
            t.join(timeout=3)
            if t.is_alive():
                self._msg_queue.put("status",
                    _("status_worker_not_exited", name=t.name))

        # 停止共享的本地模型进程
        self._stop_shared_local_model()

        # 排空消息队列中所有残留
        self._msg_queue.drain_all(timeout=2.0)

    def _stop_shared_local_model(self):
        """停止共享的本地模型"""
        with self._local_model_lock:
            proc = self._shared_local_model_proc
            self._shared_local_model_proc = None
            self._shared_local_model_port = None
        if proc:
            try:
                if proc.poll() is None:
                    self._msg_queue.put("status", _("status_local_model_stopping"))
                    proc.terminate()
                    proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def _start_local_model(self, worker_idx):
        """启动共享的本地模型服务"""
        if not self._local_model_config:
            return None, None

        cfg = self._local_model_config
        sakura_file = cfg.get('sakura_file', '')
        sakura_mode = cfg.get('sakura_mode', '100')
        param_llama = cfg.get('param_llama', '')

        if not sakura_file:
            return None, None

        port = 8989

        self._msg_queue.put("status", _("status_local_model_starting", port=port))

        try:
            args = _build_llama_server_command(
                sakura_file, sakura_mode, param_llama, port
            )
            creationflags = 0x08000000 if os.name == 'nt' else 0
            expected_model = str(Path(sakura_file).name)
            proc = subprocess.Popen(
                args,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            threading.Thread(
                target=_stream_proc_to_queue,
                args=(proc, self._msg_queue, expected_model),
                daemon=True,
            ).start()

            start_wait = time()

            while not self._stop_event.is_set():
                try:
                    chat_resp = requests.post(
                        f"http://localhost:{port}/v1/chat/completions",
                        json={
                            "model": expected_model,
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 1,
                            "temperature": 0
                        },
                        timeout=8
                    )
                    if chat_resp.status_code == 200:
                        try:
                            body = chat_resp.json()
                            if isinstance(body, dict) and body.get("choices"):
                                self._msg_queue.put("status",
                                    _("status_local_model_ready", port=port))
                                break
                        except Exception:
                            pass
                except requests.exceptions.RequestException:
                    pass

                if time() - start_wait > 120:
                    self._msg_queue.put("status",
                        _("status_local_model_timeout"))
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        pass
                    return None, None
                sleep(1)

            return proc, port
        except Exception as e:
            self._msg_queue.put("status",
                _("status_local_model_start_error", error=e))
            return None, None


class Widget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        # Set the scroll area as the parent of the widget
        self.vBoxLayout = QVBoxLayout(self)

        # Must set a globally unique object name for the sub-interface
        self.setObjectName(text.replace(' ', '-'))


class AspectRatioPixmapLabel(QLabel):
    """Display an image responsively without stretching its aspect ratio."""

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self._source_pixmap = QtGui.QPixmap(image_path)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(320)
        self._update_pixmap()

    def _update_pixmap(self):
        if self._source_pixmap.isNull():
            return
        QLabel.setPixmap(
            self,
            self._source_pixmap.scaled(
                self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            ),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()

# .env API Key 读写辅助函数
def _load_api_key() -> str:
    """从项目根目录 .env 文件中读取 API Key"""
    if not os.path.exists('.env'):
        return ''
    with open('.env', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('VOICETRANSL_API_KEY='):
                return line.split('=', 1)[1].strip()
    return ''


def _save_api_key(api_key: str) -> None:
    """将 API Key 写入项目根目录 .env 文件"""
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(f'VOICETRANSL_API_KEY={api_key}\n')


class MainWindow(QMainWindow):
    status = pyqtSignal(str)

    @staticmethod
    def default_output_dir() -> str:
        return str(Path.cwd() / 'project' / 'cache')

    def __init__(self):
        super().__init__()
        self.msg_queue = UIMessageQueue(LOG_PATH)
        self.thread = None
        self.worker = None
        self._suppress_auto_save = True
        self._button_mirrors = []
        self._dynamic_i18n_labels = []
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(200)
        self._auto_save_timer.timeout.connect(self._auto_save_config)
        self._load_ui_language()
        self.setWindowTitle(_("window_title"))
        self.setWindowIcon(QtGui.QIcon('icon.png'))
        self.init_system_tray()
        self.status.connect(lambda x: self.setWindowTitle(f"{_('window_title')} - {x}"))
        self.resize(800, 600)
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(102, 102))
        self.show()
        self.initUI()
        self._log_level_filter = 'ALL'  # 日志级别过滤默认值
        self.setup_timer()
        self.splashScreen.finish()

    def _load_ui_language(self):
        """从 gui_settings.yaml 加载已保存的界面语言，在任何 _() 调用之前执行"""
        try:
            if os.path.exists('gui_settings.yaml'):
                with open('gui_settings.yaml', 'r', encoding='utf-8') as f:
                    settings = yaml.safe_load(f) or {}
                saved_lang = settings.get('ui_language')
                if saved_lang and saved_lang in ('zh', 'en', 'ja'):
                    set_language(saved_lang)
        except Exception:
            pass

    def _emit_status(self, msg: str):
        """同时向统一消息队列和窗口标题发送状态消息"""
        self.msg_queue.put("status", msg)
        self.status.emit(msg)

    def _schedule_auto_save(self):
        """防抖自动保存：短时间内多次调用只执行最后一次"""
        if self._auto_save_timer and not self._auto_save_timer.isActive():
            self._auto_save_timer.start()

    def _auto_save_config(self):
        """执行静默自动保存"""
        try:
            self.save_config(silent=True)
        except Exception:
            pass

    def save_config(self, silent: bool = False):
        """保存 GUI 配置到 gui_settings.yaml 及相关文件"""
        if not silent:
            self._emit_status(_("status_reading_config"))
        asr_model_file = self.asr_model_file.currentText()
        aligner_file = self.aligner_file.currentText()
        asr_backend = self.asr_backend.currentText()
        translator = self.selected_translator()
        translator_mode = self.translator_mode.currentData() or 'online'
        language = self.transcription_lang.currentData() or 'ja'
        gpt_token = self.gpt_token.text()
        gpt_address = self.gpt_address.text()
        gpt_model = self.gpt_model.text()
        sakura_file = self.sakura_file.currentText()
        sakura_mode = self.sakura_mode.text()
        proxy_address = self.proxy_address.text()
        uvr_file = self.uvr_file.currentText()
        output_format = self.selected_output_format()
        subtitle_font = self.subtitle_font_combo.currentText()
        output_dir = self.output_dir_edit.text().strip() or self.default_output_dir()
        use_input_dir = self.use_input_dir_checkbox.isChecked()
        output_dir = os.path.abspath(os.path.expanduser(output_dir))
        os.makedirs(output_dir, exist_ok=True)
        enable_segment = self.enable_segment_checkbox.isChecked()
        segment_duration = self.segment_duration_spin.value()
        enable_transcription = self.enable_transcription_checkbox.isChecked()
        enable_translation = self.enable_translation_checkbox.isChecked()
        change_prompt_mode = self.change_prompt_mode.currentData() if hasattr(self, 'change_prompt_mode') else '不修改'
        auto_shutdown = self.auto_shutdown_checkbox.isChecked() if hasattr(self, 'auto_shutdown_checkbox') else False
        target_translation_lang = self.target_lang.currentData() if hasattr(self, 'target_lang') else 'zh-cn'
        current_lang = get_language()

        gui_settings = {
            'asr_model_file': asr_model_file,
            'aligner_file': aligner_file,
            'asr_backend': asr_backend,
            'translator': translator,
            'translator_mode': translator_mode,
            'online_translator': self.online_translator_group.currentText(),
            'local_translator': self.local_translator_group.currentText(),
            'language': language,
            'gpt_address': gpt_address,
            'gpt_model': gpt_model,
            'sakura_file': sakura_file,
            'sakura_mode': sakura_mode,
            'proxy_address': proxy_address,
            'uvr_file': uvr_file,
            'output_format': output_format,
            'output_target': self.output_target_combo.currentData(),
            'output_type': self.output_type_combo.currentData(),
            'subtitle_font': subtitle_font,
            'output_dir': output_dir,
            'use_input_dir': use_input_dir,
            'max_concurrent': self.max_concurrent_spin.value(),
            'enable_segment': enable_segment,
            'segment_duration': segment_duration,
            'enable_transcription': enable_transcription,
            'enable_translation': enable_translation,
            'change_prompt_mode': change_prompt_mode,
            'auto_shutdown': auto_shutdown,
            'log_level_filter': self.log_filter_combo.currentText(),
            'verbose_mode': self.verbose_checkbox.isChecked(),
            'ui_language': current_lang,
            'target_translation_lang': target_translation_lang,
        }
        with open('gui_settings.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(gui_settings, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        _save_api_key(gpt_token)

        with open('crispasr/param.txt', 'w', encoding='utf-8') as f:
            f.write(self.param_crispasr.toPlainText())

        with open('llama/param.txt', 'w', encoding='utf-8') as f:
            f.write(self.param_llama.toPlainText())

        with open('project/dict_pre.txt', 'w', encoding='utf-8') as f:
            f.write(self.before_dict.toPlainText())

        with open('project/dict_gpt.txt', 'w', encoding='utf-8') as f:
            f.write(self.gpt_dict.toPlainText())

        with open('project/dict_after.txt', 'w', encoding='utf-8') as f:
            f.write(self.after_dict.toPlainText())

        if not silent:
            self._emit_status(_("status_config_saved"))

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.FocusOut:
            self._schedule_auto_save()
        return super().eventFilter(obj, event)

    def _on_config_changed(self, *args):
        """控件值变更时的防抖处理"""
        if not self._suppress_auto_save:
            self._schedule_auto_save()

    def _install_auto_save_signals(self):
        """为可编辑控件连接值变更信号"""
        for widget in self.findChildren(QWidget):
            if isinstance(widget, QLineEdit):
                widget.editingFinished.connect(self._schedule_auto_save)
            elif isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self._on_config_changed)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self._on_config_changed)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self._on_config_changed)
            elif isinstance(widget, QTextEdit):
                widget.installEventFilter(self)

    def _apply_config_tooltips(self):
        """Keep visible labels compact and move longer guidance to tooltips."""
        tooltip_groups = (
            (('io_input_label', 'input_files_list'), 'io_input_tip'),
            (('io_proxy_label', 'proxy_address'), 'io_proxy_placeholder'),
            (('io_output_dir_label', 'output_dir_edit'), 'io_output_dir_tip'),
            (('use_input_dir_checkbox',), 'io_use_input_dir_tip'),
            (('io_output_target_label', 'output_target_combo'), 'io_output_target_tip'),
            (('io_output_type_label', 'output_type_combo'), 'io_output_type_tip'),
            (('enable_segment_checkbox',), 'io_segment_tip'),
            (('dict_before_label', 'before_dict'), 'dict_before_tip'),
            (('dict_gpt_label', 'gpt_dict'), 'dict_gpt_tip'),
            (('dict_after_label', 'after_dict'), 'dict_after_tip'),
            (('dict_extra_label', 'extra_prompt'), 'dict_extra_tip'),
            (('settings_asr_model_label', 'asr_model_file'), 'settings_asr_model_tip'),
            (('settings_asr_aligner_label', 'aligner_file'), 'settings_asr_aligner_tip'),
            (('settings_asr_backend_label', 'asr_backend'), 'settings_asr_backend_tip'),
            (('io_transcription_lang_label', 'transcription_lang'), 'settings_lang_tip'),
            (('settings_asr_param_label', 'param_crispasr'), 'settings_asr_param_placeholder'),
            (('settings_uvr_label', 'uvr_file'), 'settings_uvr_tip'),
            (('adv_translator_mode_label', 'translator_mode',
              'adv_online_translator_label', 'online_translator_group',
              'adv_local_translator_label', 'local_translator_group'),
             'adv_translator_tip'),
            (('io_concurrency_label', 'max_concurrent_spin'), 'io_concurrency_tip'),
            (('adv_online_token_label', 'gpt_token'), 'adv_online_token_placeholder'),
            (('adv_online_model_label', 'gpt_model'), 'adv_online_model_placeholder'),
            (('adv_online_address_label', 'gpt_address'), 'adv_online_address_tip'),
            (('adv_offline_param_label', 'param_llama'), 'adv_offline_param_placeholder'),
            (('clip_files_list',), 'clip_placeholder'),
            (('uvr_file_list',), 'clip_vocal_placeholder'),
            (('synth_video_files_list',), 'synth_video_placeholder'),
            (('synth_srt_files_list',), 'synth_srt_placeholder'),
            (('synth_audio_files_list',), 'synth_audio_placeholder'),
            (('summarize_prompt',), 'summarize_prompt_placeholder'),
            (('summarize_files_list',), 'summarize_input_placeholder'),
        )
        for attribute_names, translation_key in tooltip_groups:
            tooltip = _(translation_key)
            for attribute_name in attribute_names:
                widget = getattr(self, attribute_name, None)
                if widget is not None:
                    widget.setToolTip(tooltip)

    def initUI(self):
        os.makedirs('separate', exist_ok=True)
        self._legacy_interfaces = []
        self.initAboutTab()
        self.initInputOutputTab()
        self.initSettingsTab()
        self.initAdvancedSettingTab()
        self.initClipTab()
        self.initSynthTab()
        self.initSummarizeTab()
        self.initDictTab()
        self.initLogTab()
        self._apply_config_tooltips()
        self._assemble_six_tab_layout()
        self._install_auto_save_signals()
        self.load_config()

    def addSubInterface(self, widget, icon=None, text='', position=None):
        """Compatibility shim for the former FluentWindow navigation API.

        The individual page builders still register themselves here; the pages
        are assembled into the six horizontal tabs after all controls exist.
        """
        self._legacy_interfaces.append((widget, text))

    def switchTo(self, widget):
        """Select the horizontal tab containing a legacy page widget."""
        index = getattr(self, '_page_tab_indexes', {}).get(widget)
        if index is not None and hasattr(self, 'main_tab_bar'):
            self._select_main_tab(index)

    def _mirror_button(self, source_button, parent=None):
        """Create a right-column action that preserves the original signal."""
        button = QPushButton(source_button.text(), parent)
        button.setEnabled(source_button.isEnabled())
        button.clicked.connect(source_button.click)
        self._button_mirrors.append((source_button, button))
        source_button.hide()
        return button

    def _make_scroll_area(self, content_widget):
        """Wrap a complete tab body in a Fluent scroll area."""
        scroll = ScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet('QScrollArea { border: none; background: transparent; }')
        content_widget.setStyleSheet('background: transparent;')
        if content_widget.layout():
            content_widget.layout().setSizeConstraint(QLayout.SetMinimumSize)
        scroll.setWidget(content_widget)
        return scroll

    def _make_split_tab(self, config_widget, action_widgets, scrollable=True):
        """Build a tab containing one paired configuration/action section."""
        return self._make_sectioned_tab(
            [(None, config_widget, action_widgets)], scrollable=scrollable
        )

    def _make_sectioned_tab(self, sections, scrollable=True):
        """Build vertically stacked, one-to-one configuration/action sections.

        Each section owns one left configuration card and the actions that apply
        to it on the right.  The scroll area wraps both columns so their vertical
        relationship is preserved while scrolling.
        """
        page = QWidget(self)
        page.setObjectName('mainTabPage')
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        tab_body = QWidget(page)
        tab_body.setObjectName('mainTabScrollBody')
        body_layout = QVBoxLayout(tab_body)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(10)

        for title, config_widget, action_widgets in sections:
            section_row = QWidget(tab_body)
            section_layout = QHBoxLayout(section_row)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(10)

            config_frame = SimpleCardWidget(section_row)
            config_frame.setObjectName('tabConfigPanel')
            config_layout = QVBoxLayout(config_frame)
            config_layout.setContentsMargins(12, 12, 12, 12)
            config_layout.setSpacing(8)
            if title:
                title_label = SubtitleLabel(_(title))
                self._dynamic_i18n_labels.append((title_label, title))
                config_layout.addWidget(title_label)
            config_layout.addWidget(config_widget)

            action_frame = SimpleCardWidget(section_row)
            action_frame.setObjectName('tabActionPanel')
            # Every section row owns an independent horizontal layout, so a
            # width range lets labels/buttons produce slightly different right
            # column widths.  A shared fixed width keeps stacked action panels
            # on the same left and right edges.
            action_frame.setFixedWidth(240)
            action_layout = QVBoxLayout(action_frame)
            action_layout.setContentsMargins(12, 12, 12, 12)
            action_layout.setSpacing(8)
            action_title = SubtitleLabel(_('tab_actions_title'))
            self._dynamic_i18n_labels.append((action_title, 'tab_actions_title'))
            action_layout.addWidget(action_title)
            for item in action_widgets:
                if item is None:
                    action_layout.addSpacing(10)
                elif isinstance(item, str):
                    item_label = BodyLabel(_(item))
                    self._dynamic_i18n_labels.append((item_label, item))
                    action_layout.addWidget(item_label)
                elif isinstance(item, QPushButton):
                    action_layout.addWidget(self._mirror_button(item, action_frame))
                elif isinstance(item, QWidget):
                    action_layout.addWidget(item)
            action_layout.addStretch(1)

            section_layout.addWidget(config_frame, 1)
            section_layout.addWidget(action_frame)
            body_layout.addWidget(section_row)

        body_layout.addStretch(1)
        page_layout.addWidget(
            self._make_scroll_area(tab_body) if scrollable else tab_body
        )
        return page

    def _select_main_tab(self, index):
        if not 0 <= index < self.main_stack.count():
            return
        self.main_tab_bar.setCurrentIndex(index)
        self.main_stack.setCurrentIndex(index)

    def _assemble_six_tab_layout(self):
        """Compose the six top tabs and the tab-independent realtime output."""
        self.setMinimumSize(960, 700)
        self.resize(1180, 820)

        central = QWidget(self)
        central.setObjectName('sixTabRoot')
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)
        self.navigationInterface.hide()
        self.stackedWidget.addWidget(central)
        self.stackedWidget.setCurrentWidget(central)

        self.main_tab_bar = TabBar(central)
        self.main_tab_bar.setTabsClosable(False)
        self.main_tab_bar.setAddButtonVisible(False)
        self.main_tab_bar.setMovable(False)
        self.main_tab_bar.setScrollable(False)
        self.main_tab_bar.setTabMinimumWidth(150)
        self.main_tab_bar.setTabMaximumWidth(220)
        root_layout.addWidget(self.main_tab_bar)
        self.main_stack = QStackedWidget(central)
        root_layout.addWidget(self.main_stack, 1)

        welcome_page = self._make_split_tab(
            self.about_tab,
            [self.language_action_widget, None, self.btn_wiki,
             None, self.start_button, None, 'about_sponsor_title',
             self.btn_afdian, self.btn_bilibili, self.btn_kofi,],
            scrollable=False,
        )
        workbench_page = self._make_split_tab(
            self.input_output_tab,
            [self.run_button, self.cancel_button, None,
             self.open_output_button, self.clean_button],
        )

        # Keep each model configuration beside only the actions that affect it.
        self.settings_tab.setFrameShape(QFrame.StyledPanel)
        self.advanced_settings_tab.setFrameShape(QFrame.StyledPanel)
        models_page = self._make_sectioned_tab(
            [
                ('models_asr_actions', self.settings_tab,
                 [self.open_crispasr_dir, self.refresh_speech_models_button,
                  self.test_offline_asr_button]),
                ('models_translation_actions', self.advanced_settings_tab,
                 [self.open_model_dir, self.refresh_language_models_button,
                  self.test_offline_translation_button, self.test_online_button]),
            ]
        )

        self.save_dict_button = QPushButton(_('dict_save_btn'))
        self.save_dict_button.clicked.connect(lambda: self.save_config(silent=False))
        self.open_dict_dir_button = QPushButton(_('dict_open_dir_btn'))
        self.open_dict_dir_button.clicked.connect(
            lambda: open_path(os.path.join(os.getcwd(), 'project'))
        )
        dict_page = self._make_split_tab(
            self.dict_tab, [self.save_dict_button, self.open_dict_dir_button]
        )

        # Tool configurations and their actions are paired section by section.
        # The vocal-separation model is part of the vocal section itself.
        tools_page = self._make_sectioned_tab(
            [
                ('clip_tool_label', self.clip_trim_config,
                 [self.run_clip_button]),
                ('clip_vocal_split_label', self.clip_vocal_config,
                 [self.run_uvr_button, self.open_uvr_dir,
                  self.refresh_uvr_models_button]),
                ('synth_label', self.synth_video_config,
                 [self.synth_video_browse_btn, self.synth_srt_browse_btn,
                  self.run_synth_button]),
                ('synth_audio_label', self.synth_audio_config,
                 [self.run_synth_audio_button]),
                ('tab_summarize', self.summarize_tab,
                 [self.run_summarize_button]),
            ]
        )

        # The log tab contains persistent logs only. Realtime output is detached
        # below and remains visible while switching among all six tabs.
        self.log_layout.removeWidget(self.log_realtime_label)
        self.log_layout.removeWidget(self.output_text_edit)
        self.log_realtime_label.hide()
        log_page = self._make_split_tab(self.log_tab, [self.open_log_button])

        pages = [
            (welcome_page, 'tab_welcome'),
            (workbench_page, 'tab_workbench'),
            (models_page, 'tab_models'),
            (dict_page, 'tab_dict'),
            (tools_page, 'tab_tools'),
            (log_page, 'tab_log'),
        ]
        self._main_tab_i18n_keys = [key for _page, key in pages]
        for index, (page, title_key) in enumerate(pages):
            route_key = f'main-tab-{index}'
            self.main_tab_bar.addTab(
                route_key, _(title_key),
                onClick=lambda checked=False, i=index: self._select_main_tab(i),
            )
            self.main_stack.addWidget(page)
        self._select_main_tab(0)

        self._page_tab_indexes = {
            self.about_tab: 0,
            self.input_output_tab: 1,
            self.settings_tab: 2,
            self.advanced_settings_tab: 2,
            self.dict_tab: 3,
            self.clip_tab: 4,
            self.synth_tab: 4,
            self.summarize_tab: 4,
            self.log_tab: 5,
        }

        realtime_frame = SimpleCardWidget(central)
        realtime_frame.setObjectName('realtimeOutputPanel')
        realtime_layout = QVBoxLayout(realtime_frame)
        realtime_layout.setContentsMargins(12, 8, 12, 10)
        realtime_layout.setSpacing(5)
        self.realtime_output_label = SubtitleLabel(_('realtime_output_title'))
        realtime_layout.addWidget(self.realtime_output_label)
        self.output_text_edit.show()
        self.output_text_edit.setMinimumHeight(110)
        self.output_text_edit.setMaximumHeight(170)
        realtime_layout.addWidget(self.output_text_edit)
        root_layout.addWidget(realtime_frame)

    def browse_synth_video(self):
        files, _unused = QFileDialog.getOpenFileNames(self, _("dialog_select_video"), "", "Video Files (*.mp4 *.mkv *.avi *.mov *.flv);;All Files (*)")
        if files:
            current_text = self.synth_video_files_list.toPlainText().strip()
            new_text = "\n".join(files)
            if current_text:
                self.synth_video_files_list.setText(current_text + "\n" + new_text)
            else:
                self.synth_video_files_list.setText(new_text)

    def browse_synth_srt(self):
        files, _unused = QFileDialog.getOpenFileNames(self, _("dialog_select_subtitle"), "", "Subtitle Files (*.srt *.ass *.vtt);;All Files (*)")
        if files:
            current_text = self.synth_srt_files_list.toPlainText().strip()
            new_text = "\n".join(files)
            if current_text:
                self.synth_srt_files_list.setText(current_text + "\n" + new_text)
            else:
                self.synth_srt_files_list.setText(new_text)

    def browse_output_dir(self):
        current_dir = self.output_dir_edit.text().strip() or self.default_output_dir()
        selected = QFileDialog.getExistingDirectory(self, _("dialog_select_output_dir"), current_dir)
        if selected:
            self.output_dir_edit.setText(selected)

    def update_output_dir_controls(self):
        use_input_dir = self.use_input_dir_checkbox.isChecked() if hasattr(self, 'use_input_dir_checkbox') else False
        self.output_dir_edit.setEnabled(not use_input_dir)
        self.output_dir_button.setEnabled(not use_input_dir)

    def update_segment_controls(self):
        enabled = self.enable_segment_checkbox.isChecked() if hasattr(self, 'enable_segment_checkbox') else False
        self.segment_duration_spin.setEnabled(enabled)

    def update_processing_controls(self):
        """Keep language controls aligned with the actions selected on the input tab."""
        if hasattr(self, 'transcription_lang'):
            language_required = (
                getattr(self, 'enable_transcription_checkbox', None) is not None
                and self.enable_transcription_checkbox.isChecked()
            ) or (
                getattr(self, 'enable_translation_checkbox', None) is not None
                and self.enable_translation_checkbox.isChecked()
            )
            self.transcription_lang.setEnabled(language_required)
        if hasattr(self, 'target_lang'):
            translation_enabled = self.enable_translation_checkbox.isChecked()
            self.target_lang.setEnabled(translation_enabled)
            self.io_target_lang_label.setEnabled(translation_enabled)
            self.max_concurrent_spin.setEnabled(translation_enabled)
            self.io_concurrency_label.setEnabled(translation_enabled)

    def selected_translator(self):
        """Return the translator selected for the active online/local mode."""
        if self.translator_mode.currentData() == 'local':
            return self.local_translator_group.currentText()
        return self.online_translator_group.currentText()

    def set_selected_translator(self, translator, mode=None):
        """Restore a translator selection while accepting the legacy flat value."""
        inferred_mode = 'local' if translator in LOCAL_TRANSLATOR_SUPPORTED else 'online'
        selected_mode = mode if mode in ('online', 'local') else inferred_mode
        mode_index = self.translator_mode.findData(selected_mode)
        if mode_index >= 0:
            self.translator_mode.setCurrentIndex(mode_index)

        target_combo = (
            self.local_translator_group
            if selected_mode == 'local'
            else self.online_translator_group
        )
        if translator and target_combo.findText(translator) >= 0:
            target_combo.setCurrentText(translator)

    def update_translator_mode_controls(self):
        """Enable only the configuration controls used by the selected mode."""
        online_mode = self.translator_mode.currentData() != 'local'
        online_widgets = (
            self.adv_online_translator_label, self.online_translator_group,
            self.adv_online_token_label, self.gpt_token,
            self.adv_online_model_label, self.gpt_model,
            self.adv_online_address_label, self.gpt_address,
            self.test_online_button,
        )
        local_widgets = (
            self.adv_local_translator_label, self.local_translator_group,
            self.adv_offline_model_label, self.sakura_file,
            self.adv_offline_gpu_label, self.sakura_mode,
            self.adv_offline_param_label, self.param_llama,
            self.open_model_dir, self.refresh_language_models_button,
            self.test_offline_translation_button,
        )
        for widget in online_widgets:
            widget.setEnabled(online_mode)
        for widget in local_widgets:
            widget.setEnabled(not online_mode)
        for source_button, mirror_button in self._button_mirrors:
            if source_button in online_widgets or source_button in local_widgets:
                mirror_button.setEnabled(source_button.isEnabled())

    def selected_output_format(self):
        """Return the legacy composite output value used by processing code."""
        content = self.output_target_combo.currentData() or '原文'
        file_type = self.output_type_combo.currentData() or 'SRT'
        return f'{content}{file_type}'

    def _normalize_drop_paths(self, mime_data):
        paths = []
        try:
            urls = mime_data.urls()
        except Exception:
            urls = []

        if urls:
            for url in urls:
                if url.isLocalFile():
                    local_path = url.toLocalFile()
                    if local_path:
                        paths.append(local_path)
            return paths

        raw_text = mime_data.text() or ""
        if not raw_text:
            return paths

        for item in raw_text.splitlines():
            item = item.strip()
            if not item:
                continue
            if item.startswith("file://"):
                url = QtCore.QUrl(item)
                local_path = url.toLocalFile()
                if local_path:
                    paths.append(local_path)
                continue
            paths.append(item)
        return paths

    def _bind_drop_event(self, text_edit):
        def _on_drop(event):
            paths = self._normalize_drop_paths(event.mimeData())
            if paths:
                text_edit.setPlainText("\n".join(paths))
        text_edit.dropEvent = _on_drop

    def collect_font_candidates(self):
        # Scan ./font and common system font dirs for ttf/ttc/otf files
        candidates = []
        exts = {'.ttf', '.ttc', '.otf'}
        search_dirs = []
        # Windows fonts
        win_font_dir = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        search_dirs.append(win_font_dir)
        # macOS
        search_dirs.extend([Path('/Library/Fonts'), Path.home() / 'Library/Fonts'])
        # Linux common
        search_dirs.extend([Path('/usr/share/fonts'), Path('/usr/local/share/fonts'), Path.home() / '.fonts'])

        for d in search_dirs:
            if not d.exists():
                continue
            for p in d.rglob('*'):
                if p.suffix.lower() in exts:
                    candidates.append(p.stem)  # also add family name guess

        # de-duplicate while preserving order
        seen = set()
        unique = []
        for item in candidates:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique

    def refresh_speech_model_lists(self):
        if hasattr(self, 'asr_model_file'):
            current_model = self.asr_model_file.currentText()
            asr_models = _list_crispasr_models()
            self.asr_model_file.clear()
            self.asr_model_file.addItems(asr_models)
            if current_model in asr_models:
                self.asr_model_file.setCurrentText(current_model)

        if hasattr(self, 'aligner_file'):
            current_aligner = self.aligner_file.currentText()
            aligners = _list_crispasr_aligners()
            self.aligner_file.clear()
            self.aligner_file.addItems(aligners)
            if current_aligner in aligners:
                self.aligner_file.setCurrentText(current_aligner)

        if hasattr(self, 'asr_backend'):
            current_backend = self.asr_backend.currentText()
            backends = _list_crispasr_backends()
            self.asr_backend.clear()
            self.asr_backend.addItems(backends)
            if current_backend in backends:
                self.asr_backend.setCurrentText(current_backend)
            elif 'qwen3-1.7b' in backends:
                self.asr_backend.setCurrentText('qwen3-1.7b')

    def refresh_uvr_model_list(self):
        if hasattr(self, 'uvr_file'):
            current_uvr = self.uvr_file.currentText()
            uvr_lst = [i for i in os.listdir('separate') if i.endswith('onnx')]
            self.uvr_file.clear()
            self.uvr_file.addItems(uvr_lst)
            if current_uvr in uvr_lst:
                self.uvr_file.setCurrentText(current_uvr)

    def refresh_language_model_lists(self):
        if hasattr(self, 'sakura_file'):
            current_model = self.sakura_file.currentText()
            sakura_lst = [i for i in os.listdir('llama') if i.endswith('gguf')]
            self.sakura_file.clear()
            self.sakura_file.addItems(sakura_lst)
            if current_model in sakura_lst:
                self.sakura_file.setCurrentText(current_model)

    def cancel_task(self):
        self._emit_status(_("status_cancelling"))
        try:
            if self.worker:
                self.worker.stop()
        except Exception as e:
            self._emit_status(_("status_cancel_worker_error", error=e))

        try:
            if self.thread and self.thread.isRunning():
                self.thread.quit()
                if not self.thread.wait(2000):
                    self.thread.terminate()
                    self.thread.wait(2000)
        except Exception as e:
            self._emit_status(_("status_cancel_thread_error", error=e))

        self._emit_status(_("status_cancel_done"))

    def _migrate_config_txt(self):
        """从旧 config.txt 迁移到 gui_settings.yaml + .env，返回 gui_settings 字典"""
        with open('config.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()

        gpt_token = lines[3].strip() if len(lines) > 3 else ''
        _save_api_key(gpt_token)

        gui_settings = {
            'asr_model_file': lines[0].strip(),
            'translator': lines[1].strip(),
            'enable_transcription': lines[0].strip() != NO_TRANSCRIPTION,
            'enable_translation': lines[1].strip() != NO_TRANSLATION,
            'language': lines[2].strip(),
            'gpt_address': lines[4].strip(),
            'gpt_model': lines[5].strip(),
            'sakura_file': lines[6].strip(),
            'sakura_mode': lines[7].strip(),
            'proxy_address': lines[8].strip(),
            'uvr_file': lines[9].strip(),
            'output_format': lines[10].strip(),
            'subtitle_font': lines[11].strip() if len(lines) > 11 else "",
            'output_dir': lines[12].strip() if len(lines) > 12 else self.default_output_dir(),
            'use_input_dir': (lines[13].strip().lower() == 'true') if len(lines) > 13 else False,
            'max_concurrent': int(lines[14].strip()) if len(lines) > 14 else 1,
            'enable_segment': (lines[15].strip().lower() == 'true') if len(lines) > 15 else False,
            'segment_duration': int(lines[16].strip()) if len(lines) > 16 else 10,
            'change_prompt_mode': lines[17].strip() if len(lines) > 17 else '不修改',
            'auto_shutdown': (lines[18].strip().lower() == 'true') if len(lines) > 18 else False,
        }

        with open('gui_settings.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(gui_settings, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        return gui_settings

    def load_config(self):
        """加载 GUI 配置（优先 gui_settings.yaml，兼容旧 config.txt 自动迁移）"""
        self._suppress_auto_save = True
        gui_settings = {}

        if os.path.exists('gui_settings.yaml'):
            with open('gui_settings.yaml', 'r', encoding='utf-8') as f:
                gui_settings = yaml.safe_load(f) or {}
        elif os.path.exists('config.txt'):
            gui_settings = self._migrate_config_txt()

        if gui_settings:
            saved_asr_model = gui_settings.get('asr_model_file') or gui_settings.get('whisper_file')
            enable_transcription = gui_settings.get(
                'enable_transcription', saved_asr_model != NO_TRANSCRIPTION
            )
            if self.asr_model_file and saved_asr_model and saved_asr_model != NO_TRANSCRIPTION:
                self.asr_model_file.setCurrentText(saved_asr_model)
            saved_aligner = gui_settings.get('aligner_file')
            if saved_aligner:
                self.aligner_file.setCurrentText(saved_aligner)
            saved_backend = gui_settings.get('asr_backend', 'qwen3-1.7b')
            if saved_backend:
                self.asr_backend.setCurrentText(saved_backend)
            saved_translator = gui_settings.get('translator', '')
            enable_translation = gui_settings.get(
                'enable_translation', saved_translator != NO_TRANSLATION
            )
            saved_online_translator = gui_settings.get('online_translator', '')
            if self.online_translator_group.findText(saved_online_translator) >= 0:
                self.online_translator_group.setCurrentText(saved_online_translator)
            saved_local_translator = gui_settings.get('local_translator', '')
            if self.local_translator_group.findText(saved_local_translator) >= 0:
                self.local_translator_group.setCurrentText(saved_local_translator)
            if saved_translator and saved_translator != NO_TRANSLATION:
                self.set_selected_translator(
                    saved_translator, gui_settings.get('translator_mode')
                )
            self.enable_transcription_checkbox.setChecked(bool(enable_transcription))
            self.enable_translation_checkbox.setChecked(bool(enable_translation))
            saved_language = gui_settings.get('language', 'ja')
            language_index = self.transcription_lang.findData(saved_language)
            if language_index >= 0:
                self.transcription_lang.setCurrentIndex(language_index)
            self.gpt_address.setText(gui_settings.get('gpt_address', ''))
            self.gpt_model.setText(gui_settings.get('gpt_model', ''))
            if self.sakura_file:
                self.sakura_file.setCurrentText(gui_settings.get('sakura_file', ''))
            self.sakura_mode.setText(gui_settings.get('sakura_mode', ''))
            self.proxy_address.setText(gui_settings.get('proxy_address', ''))
            if self.uvr_file:
                self.uvr_file.setCurrentText(gui_settings.get('uvr_file', ''))
            _fmt_loaded = gui_settings.get('output_format', '双语SRT')
            # 迁移旧值：中文SRT/LRC → 目标SRT/LRC
            _fmt_migrate = {'中文SRT': '目标SRT', '中文LRC': '目标LRC'}
            _fmt_loaded = _fmt_migrate.get(_fmt_loaded, _fmt_loaded)
            _legacy_target, _legacy_type = _split_output_format(_fmt_loaded)
            _output_target = gui_settings.get('output_target', _legacy_target)
            _output_type = gui_settings.get('output_type', _legacy_type)
            _target_idx = self.output_target_combo.findData(_output_target)
            if _target_idx >= 0:
                self.output_target_combo.setCurrentIndex(_target_idx)
            _type_idx = self.output_type_combo.findData(_output_type)
            if _type_idx >= 0:
                self.output_type_combo.setCurrentIndex(_type_idx)
            subtitle_font = gui_settings.get('subtitle_font', '')
            if subtitle_font:
                self.subtitle_font_combo.setCurrentText(subtitle_font)
            output_dir = gui_settings.get('output_dir', '')
            if output_dir:
                self.output_dir_edit.setText(output_dir)
            self.use_input_dir_checkbox.setChecked(gui_settings.get('use_input_dir', False))
            self.max_concurrent_spin.setValue(gui_settings.get('max_concurrent', 1))
            self.enable_segment_checkbox.setChecked(gui_settings.get('enable_segment', False))
            self.segment_duration_spin.setValue(gui_settings.get('segment_duration', 10))
            change_prompt_mode = gui_settings.get('change_prompt_mode', '')
            if hasattr(self, 'change_prompt_mode') and change_prompt_mode:
                _pm_idx = self.change_prompt_mode.findData(change_prompt_mode)
                if _pm_idx >= 0:
                    self.change_prompt_mode.setCurrentIndex(_pm_idx)
            if hasattr(self, 'auto_shutdown_checkbox'):
                self.auto_shutdown_checkbox.setChecked(gui_settings.get('auto_shutdown', False))
            # 日志级别过滤和详细模式
            log_filter = gui_settings.get('log_level_filter', 'ALL')
            if hasattr(self, 'log_filter_combo'):
                self.log_filter_combo.setCurrentText(log_filter)
                self._log_level_filter = log_filter
            if hasattr(self, 'verbose_checkbox'):
                self.verbose_checkbox.setChecked(gui_settings.get('verbose_mode', False))
            if hasattr(self, 'target_lang'):
                _tl_idx = self.target_lang.findData(gui_settings.get('target_translation_lang', 'zh-cn'))
                if _tl_idx >= 0:
                    self.target_lang.setCurrentIndex(_tl_idx)

        # API Key 始终从 .env 加载
        api_key = _load_api_key()
        if api_key:
            self.gpt_token.setText(api_key)

        if not self.output_dir_edit.text().strip():
            self.output_dir_edit.setText(self.default_output_dir())

        self.update_output_dir_controls()
        self.update_processing_controls()

        if os.path.exists('crispasr/param.txt'):
            with open('crispasr/param.txt', 'r', encoding='utf-8') as f:
                self.param_crispasr.setPlainText(f.read())

        if os.path.exists('llama/param.txt'):
            with open('llama/param.txt', 'r', encoding='utf-8') as f:
                self.param_llama.setPlainText(f.read())

        if os.path.exists('project/dict_pre.txt'):
            with open('project/dict_pre.txt', 'r', encoding='utf-8') as f:
                self.before_dict.setPlainText(f.read())

        if os.path.exists('project/dict_gpt.txt'):
            with open('project/dict_gpt.txt', 'r', encoding='utf-8') as f:
                self.gpt_dict.setPlainText(f.read())

        if os.path.exists('project/dict_after.txt'):
            with open('project/dict_after.txt', 'r', encoding='utf-8') as f:
                self.after_dict.setPlainText(f.read())

        # 从 config.yaml 加载 prompt 设置
        try:
            if os.path.exists('project/config.yaml'):
                with open('project/config.yaml', 'r', encoding='utf-8') as f:
                    cfg = yaml.safe_load(f) or {}
                common_cfg = cfg.get('common', {})

                change_prompt_val = common_cfg.get('gpt.change_prompt', 'no')
                mode_reverse_mapping = {
                    'no': '不修改',
                    'AdditionalPrompt': '追加',
                    'OverwritePrompt': '覆盖'
                }
                if hasattr(self, 'change_prompt_mode'):
                    _pm_val = mode_reverse_mapping.get(change_prompt_val, '不修改')
                    _pm_idx = self.change_prompt_mode.findData(_pm_val)
                    if _pm_idx >= 0:
                        self.change_prompt_mode.setCurrentIndex(_pm_idx)

                prompt_content = common_cfg.get('gpt.prompt_content', '')
                if hasattr(self, 'extra_prompt') and prompt_content:
                    self.extra_prompt.setPlainText(prompt_content)
        except Exception:
            pass
        finally:
            self._suppress_auto_save = False

    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._consume_messages)
        self.timer.start(1000)

    def init_system_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        self.tray_icon = QSystemTrayIcon(self.windowIcon(), self)
        self.tray_icon.setToolTip(_("tray_tooltip"))

        tray_menu = QMenu(self)
        self.tray_restore_action = QAction(_("tray_show"), self)
        self.tray_quit_action = QAction(_("tray_quit"), self)
        self.tray_restore_action.triggered.connect(self.restore_from_tray)
        self.tray_quit_action.triggered.connect(QApplication.instance().quit)

        tray_menu.addAction(self.tray_restore_action)
        tray_menu.addSeparator()
        tray_menu.addAction(self.tray_quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.restore_from_tray()

    def _check_auto_shutdown(self):
        """在 GUI 线程中检查并发起系统关机。"""
        if not self.auto_shutdown_checkbox.isChecked():
            return

        if sys.platform == 'darwin':
            command = ['osascript', '-e', 'tell application "System Events" to shut down']
        elif os.name == 'nt':
            command = ['shutdown', '/s', '/t', '0']
        else:
            command = ['shutdown', '-h', 'now']

        self._emit_status(_("status_auto_shutdown"))
        try:
            subprocess.Popen(command)
        except Exception as e:
            self._emit_status(_("status_auto_shutdown_error", error=e))

    def _consume_messages(self):
        """定时器回调：从统一消息队列消费并分发到两个显示框"""
        if not hasattr(self, 'msg_queue'):
            return

        entries = self.msg_queue.drain()
        if not entries:
            return

        for target, text in entries:
            if UIMessageQueue.is_completion_entry(target):
                # 完成哨兵：两个框都追加
                completion_msg = _("status_all_done")
                self.output_text_edit.append(completion_msg)
                self.log_display.appendPlainText(completion_msg)
                self._check_auto_shutdown()
            elif target == 'status':
                self.output_text_edit.append(text)
            elif target == 'detail':
                # 应用日志级别过滤
                if self._log_level_filter != 'ALL':
                    if not _line_passes_filter(text, self._log_level_filter):
                        continue
                self.log_display.appendPlainText(text)

        # 自动滚动两个框到底部
        for widget in (self.output_text_edit, self.log_display):
            scrollbar = widget.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """确保在关闭窗口时停止定时器并关闭子进程，检查本地模型是否已关闭"""
        try:
            self.save_config(silent=True)
        except Exception:
            pass
        self.timer.stop()
        self.shutdown_children()

        # 检查本地模型是否仍在运行
        local_model_running = False
        if hasattr(self, 'worker') and self.worker:
            # 检查翻译池中的共享本地模型进程
            if hasattr(self.worker, '_translation_pool') and self.worker._translation_pool:
                pool = self.worker._translation_pool
                if hasattr(pool, '_shared_local_model_proc') and pool._shared_local_model_proc:
                    proc = pool._shared_local_model_proc
                    if proc and proc.poll() is None:
                        local_model_running = True
                        # 尝试再次停止
                        pool._stop_shared_local_model()
                        # 再次检查
                        if proc.poll() is None:
                            # 强制终止
                            try:
                                proc.kill()
                                proc.wait(timeout=2)
                            except Exception:
                                pass

        if local_model_running:
            print(_("status_local_model_closed"))

        if getattr(self, 'tray_icon', None):
            self.tray_icon.hide()
        event.accept()

    def shutdown_children(self):
        """关闭后台线程和子进程"""
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass

        try:
            if self.thread and self.thread.isRunning():
                self.thread.quit()
                if not self.thread.wait(2000):
                    self.thread.terminate()
                    self.thread.wait(2000)
        except Exception:
            pass

    def changeEvent(self, event):
        # Hide window instead of cluttering the taskbar when minimized
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.WindowStateChange and self.isMinimized():
            if getattr(self, 'tray_icon', None):
                QTimer.singleShot(0, self.hide)
                self.tray_icon.showMessage("VoiceTransl", _("tray_minimized"), QSystemTrayIcon.Information, 2000)

        if event.type() == QtCore.QEvent.ActivationChange and not self.isActiveWindow():
            self._schedule_auto_save()

    def initLogTab(self):
        self.log_tab = Widget("Log", self)
        self.log_layout = self.log_tab.vBoxLayout

        self.log_realtime_label = BodyLabel(_("log_realtime_label"))
        self.log_layout.addWidget(self.log_realtime_label)

        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.output_text_edit.setPlaceholderText(_("log_realtime_placeholder"))
        self.log_layout.addWidget(self.output_text_edit)

        self.log_file_label = BodyLabel(_("log_file_label"))
        self.log_layout.addWidget(self.log_file_label)

        # 日志过滤工具栏
        filter_layout = QHBoxLayout()
        self.log_filter_label = QLabel(_("log_filter_label"))
        self.log_filter_combo = QComboBox()
        self.log_filter_combo.addItems(["ALL", "INFO+", "WARNING+", "ERROR+"])
        self.log_filter_combo.currentTextChanged.connect(self._on_log_filter_changed)

        # 详细日志模式复选框
        self.verbose_checkbox = QCheckBox(_("log_verbose_checkbox"))
        self.verbose_checkbox.setToolTip(_("log_verbose_tooltip"))
        self.verbose_checkbox.stateChanged.connect(self._on_verbose_changed)

        filter_layout.addWidget(self.log_filter_label)
        filter_layout.addWidget(self.log_filter_combo)
        filter_layout.addStretch()
        filter_layout.addWidget(self.verbose_checkbox)
        self.log_layout.addLayout(filter_layout)

        # log
        self.log_display = QPlainTextEdit(self)
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("font-family: Consolas, Monospace; font-size: 10pt;")
        self.log_layout.addWidget(self.log_display)

        # open log file button
        self.open_log_button = QPushButton(_("log_open_btn"))
        self.open_log_button.clicked.connect(lambda: open_path(LOG_PATH))
        self.log_layout.addWidget(self.open_log_button)

        self.addSubInterface(self.log_tab, FluentIcon.INFO, _("tab_log"), NavigationItemPosition.TOP)

    def _on_log_filter_changed(self, filter_text: str):
        """级别过滤变更：仅影响后续到达的 detail 消息（已显示内容不变）"""
        self._log_level_filter = filter_text

    def _on_verbose_changed(self, state: int):
        """详细模式复选框变更"""
        ConcurrentTranslationPool.verbose_galtransl = (state == Qt.Checked)

    def initAboutTab(self):
        self.about_tab = Widget("About", self)
        self.about_layout = self.about_tab.vBoxLayout

        # introduce
        self.about_title_label = TitleLabel(_("about_title"))
        self.about_layout.addWidget(self.about_title_label)

        # This control is assembled into the welcome tab's action panel.
        self.language_action_widget = QWidget(self.about_tab)
        language_layout = QHBoxLayout(self.language_action_widget)
        language_layout.setContentsMargins(0, 0, 0, 0)
        self.lang_selector_label = BodyLabel(_("lang_selector_label"))
        language_layout.addWidget(self.lang_selector_label)
        self.lang_selector = QComboBox()
        self.lang_selector.addItem(_("lang_zh"), userData='zh')
        self.lang_selector.addItem(_("lang_en"), userData='en')
        self.lang_selector.addItem(_("lang_ja"), userData='ja')
        lang_map = {"zh": 0, "en": 1, "ja": 2}
        self.lang_selector.setCurrentIndex(lang_map.get(get_language(), 0))
        self.lang_selector.currentIndexChanged.connect(self._on_language_changed)
        language_layout.addWidget(self.lang_selector)

        # Main welcome visual
        self.about_avatar = AspectRatioPixmapLabel('avatar.png', self.about_tab)
        self.about_avatar.setToolTip(_("about_title"))
        self.about_layout.addWidget(self.about_avatar, 1)

        # start
        self.start_button = QPushButton(_("about_start_btn"))
        self.start_button.clicked.connect(lambda: self.switchTo(self.input_output_tab))
        self.about_layout.addWidget(self.start_button)

        # wiki button
        self.btn_wiki = QPushButton(_("about_wiki_btn"))
        self.btn_wiki.clicked.connect(lambda: open_url("https://github.com/shinnpuru/VoiceTransl"))
        self.about_layout.addWidget(self.btn_wiki)

        # sponsorship buttons
        btn_layout = QHBoxLayout()
        self.btn_afdian = QPushButton(_("about_afdian_btn"))
        self.btn_bilibili = QPushButton(_("about_bilibili_btn"))
        self.btn_kofi = QPushButton(_("about_kofi_btn"))

        def open_url(url):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

        self.btn_afdian.clicked.connect(lambda: open_url("https://afdian.com/a/shinnpuru"))
        self.btn_bilibili.clicked.connect(lambda: open_url("https://space.bilibili.com/36464441"))
        self.btn_kofi.clicked.connect(lambda: open_url("https://ko-fi.com/U7U018MISY"))

        btn_layout.addWidget(self.btn_afdian)
        btn_layout.addWidget(self.btn_bilibili)
        btn_layout.addWidget(self.btn_kofi)
        self.about_layout.addLayout(btn_layout)


        self.addSubInterface(self.about_tab, FluentIcon.HEART, _("tab_about"), NavigationItemPosition.TOP)

    @staticmethod
    def _retranslate_combo(combo, translation_keys):
        """Update translated combo-box labels without changing its selection."""
        combo.blockSignals(True)
        try:
            for index in range(combo.count()):
                key = translation_keys.get(combo.itemData(index))
                if key:
                    combo.setItemText(index, _(key))
        finally:
            combo.blockSignals(False)

    def _retranslate_ui(self):
        """Refresh every persistent UI string after changing the language."""
        text_bindings = {
            'log_realtime_label': 'log_realtime_label',
            'log_file_label': 'log_file_label',
            'log_filter_label': 'log_filter_label',
            'verbose_checkbox': 'log_verbose_checkbox',
            'open_log_button': 'log_open_btn',
            'about_title_label': 'about_title',
            'lang_selector_label': 'lang_selector_label',
            'start_button': 'about_start_btn',
            'btn_wiki': 'about_wiki_btn',
            'btn_afdian': 'about_afdian_btn',
            'btn_bilibili': 'about_bilibili_btn',
            'btn_kofi': 'about_kofi_btn',
            'io_input_label': 'io_input_label',
            'io_transcription_group_label': 'io_transcription_group_title',
            'enable_transcription_checkbox': 'io_enable_transcription_checkbox',
            'io_transcription_lang_label': 'io_transcription_lang_label',
            'enable_segment_checkbox': 'io_segment_checkbox',
            'io_segment_duration_label': 'io_segment_duration_label',
            'io_translation_group_label': 'io_translation_group_title',
            'enable_translation_checkbox': 'io_enable_translation_checkbox',
            'io_target_lang_label': 'io_target_lang_label',
            'io_proxy_label': 'io_proxy_label',
            'io_output_group_label': 'io_output_group_title',
            'io_output_dir_label': 'io_output_dir_label',
            'output_dir_button': 'io_browse_dir_btn',
            'use_input_dir_checkbox': 'io_use_input_dir_checkbox',
            'auto_shutdown_checkbox': 'io_auto_shutdown_checkbox',
            'io_output_target_label': 'io_output_target_label',
            'io_output_type_label': 'io_output_type_label',
            'run_button': 'io_run_btn',
            'cancel_button': 'io_cancel_btn',
            'open_output_button': 'io_open_output_btn',
            'clean_button': 'io_clean_btn',
            'dict_before_label': 'dict_before_label',
            'dict_gpt_label': 'dict_gpt_label',
            'dict_after_label': 'dict_after_label',
            'dict_extra_label': 'dict_extra_label',
            'dict_prompt_mode_label': 'dict_prompt_mode_label',
            'save_dict_button': 'dict_save_btn',
            'open_dict_dir_button': 'dict_open_dir_btn',
            'settings_asr_model_label': 'settings_asr_model_label',
            'settings_asr_aligner_label': 'settings_asr_aligner_label',
            'settings_asr_backend_label': 'settings_asr_backend_label',
            'settings_asr_param_label': 'settings_asr_param_label',
            'open_crispasr_dir': 'settings_open_crispasr_btn',
            'refresh_speech_models_button': 'settings_refresh_speech_btn',
            'test_offline_asr_button': 'settings_test_offline_asr_btn',
            'settings_uvr_label': 'settings_uvr_label',
            'open_uvr_dir': 'settings_open_uvr_btn',
            'refresh_uvr_models_button': 'settings_refresh_uvr_btn',
            'adv_translator_mode_label': 'adv_translator_mode_label',
            'io_concurrency_label': 'io_concurrency_label',
            'adv_online_translator_label': 'adv_online_translator_label',
            'adv_local_translator_label': 'adv_local_translator_label',
            'adv_online_token_label': 'adv_online_token_label',
            'adv_online_model_label': 'adv_online_model_label',
            'adv_online_address_label': 'adv_online_address_label',
            'adv_offline_model_label': 'adv_offline_model_label',
            'adv_offline_gpu_label': 'adv_offline_gpu_label',
            'adv_offline_param_label': 'adv_offline_param_label',
            'open_model_dir': 'adv_open_model_btn',
            'refresh_language_models_button': 'adv_refresh_model_btn',
            'test_offline_translation_button': 'adv_test_offline_btn',
            'test_online_button': 'adv_test_api_btn',
            'clip_start_label': 'clip_start_label',
            'clip_end_label': 'clip_end_label',
            'run_clip_button': 'clip_run_btn',
            'run_uvr_button': 'clip_vocal_run_btn',
            'synth_video_label': 'synth_video_label',
            'synth_video_browse_btn': 'synth_browse_video_btn',
            'synth_srt_label': 'synth_srt_label',
            'synth_srt_browse_btn': 'synth_browse_srt_btn',
            'synth_subtitle_type_label': 'synth_subtitle_type_label',
            'synth_font_label': 'synth_font_label',
            'run_synth_button': 'synth_run_btn',
            'run_synth_audio_button': 'synth_audio_run_btn',
            'summarize_prompt_label': 'summarize_prompt_label',
            'summarize_input_label': 'summarize_input_label',
            'run_summarize_button': 'summarize_run_btn',
            'realtime_output_label': 'realtime_output_title',
        }
        for attribute_name, translation_key in text_bindings.items():
            widget = getattr(self, attribute_name, None)
            if widget is not None:
                widget.setText(_(translation_key))

        placeholder_bindings = {
            'output_text_edit': 'log_realtime_placeholder',
            'input_files_list': 'io_input_placeholder',
            'proxy_address': 'io_proxy_placeholder',
            'before_dict': 'dict_before_placeholder',
            'gpt_dict': 'dict_gpt_placeholder',
            'after_dict': 'dict_after_placeholder',
            'extra_prompt': 'dict_extra_placeholder',
            'param_crispasr': 'settings_asr_param_placeholder',
            'gpt_token': 'adv_online_token_placeholder',
            'gpt_model': 'adv_online_model_placeholder',
            'gpt_address': 'adv_online_address_placeholder',
            'param_llama': 'adv_offline_param_placeholder',
            'clip_files_list': 'clip_placeholder',
            'clip_start_time': 'clip_start_placeholder',
            'clip_end_time': 'clip_end_placeholder',
            'uvr_file_list': 'clip_vocal_placeholder',
            'synth_video_files_list': 'synth_video_placeholder',
            'synth_srt_files_list': 'synth_srt_placeholder',
            'synth_audio_files_list': 'synth_audio_placeholder',
            'summarize_prompt': 'summarize_prompt_placeholder',
            'summarize_files_list': 'summarize_input_placeholder',
        }
        for attribute_name, translation_key in placeholder_bindings.items():
            widget = getattr(self, attribute_name, None)
            if widget is not None:
                widget.setPlaceholderText(_(translation_key))

        self._retranslate_combo(self.lang_selector, {
            'zh': 'lang_zh', 'en': 'lang_en', 'ja': 'lang_ja',
        })
        language_keys = {
            code: f"target_lang_{code.replace('-', '_')}"
            for code in ('zh-cn', 'zh-tw', 'en', 'ja', 'ko', 'ru', 'fr', 'zh')
        }
        self._retranslate_combo(self.transcription_lang, language_keys)
        self._retranslate_combo(self.target_lang, language_keys)
        self._retranslate_combo(self.output_target_combo, {
            '原文': 'output_target_original',
            '目标': 'output_target_translated',
            '双语': 'output_target_bilingual',
        })
        self._retranslate_combo(self.output_type_combo, {
            'SRT': 'output_type_srt', 'LRC': 'output_type_lrc',
        })
        self._retranslate_combo(self.change_prompt_mode, {
            '不修改': 'dict_prompt_mode_no',
            '追加': 'dict_prompt_mode_append',
            '覆盖': 'dict_prompt_mode_overwrite',
        })
        self._retranslate_combo(self.translator_mode, {
            'online': 'adv_translator_mode_online',
            'local': 'adv_translator_mode_local',
        })
        self._retranslate_combo(self.subtitle_type_combo, {
            '硬字幕': 'synth_sub_hard', '软字幕': 'synth_sub_soft',
        })

        for widget, translation_key in self._dynamic_i18n_labels:
            widget.setText(_(translation_key))
        for index, translation_key in enumerate(self._main_tab_i18n_keys):
            self.main_tab_bar.setTabText(index, _(translation_key))
        for source_button, mirror_button in self._button_mirrors:
            mirror_button.setText(source_button.text())

        self.setWindowTitle(_("window_title"))
        self.about_avatar.setToolTip(_("about_title"))
        self.verbose_checkbox.setToolTip(_("log_verbose_tooltip"))
        if getattr(self, 'tray_icon', None):
            self.tray_icon.setToolTip(_("tray_tooltip"))
            self.tray_restore_action.setText(_("tray_show"))
            self.tray_quit_action.setText(_("tray_quit"))
        self._apply_config_tooltips()

    def _on_language_changed(self, index: int):
        """Apply a UI language change immediately without rebuilding the window."""
        if self._suppress_auto_save:
            return
        lang_code = self.lang_selector.itemData(index) or "zh"
        set_language(lang_code)
        self._retranslate_ui()
        self._schedule_auto_save()
        lang_name = self.lang_selector.currentText()
        self._emit_status(_("status_lang_changed", lang=lang_name))
        if getattr(self, 'tray_icon', None):
            self.tray_icon.showMessage(
                _("notify_lang_changed_title"),
                _("notify_lang_changed_msg"),
                QSystemTrayIcon.Information,
                3000
            )

    def initInputOutputTab(self):
        self.input_output_tab = Widget("Home", self)
        self.input_output_layout = self.input_output_tab.vBoxLayout

        # Input Section (local files or URLs)
        self.io_input_label = BodyLabel(_("io_input_label"))
        self.input_output_layout.addWidget(self.io_input_label)
        self.input_files_list = QTextEdit()
        self.input_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.input_files_list)
        self.input_files_list.setPlaceholderText(_("io_input_placeholder"))
        self.input_output_layout.addWidget(self.input_files_list)

        # Transcription settings stay together.
        self.io_transcription_group_label = SubtitleLabel(_("io_transcription_group_title"))
        self.input_output_layout.addWidget(self.io_transcription_group_label)
        transcription_layout = QHBoxLayout()
        self.enable_transcription_checkbox = QCheckBox(_("io_enable_transcription_checkbox"))
        self.enable_transcription_checkbox.setChecked(True)
        self.enable_transcription_checkbox.stateChanged.connect(self.update_processing_controls)
        transcription_layout.addWidget(self.enable_transcription_checkbox)
        transcription_layout.addSpacing(16)
        self.io_transcription_lang_label = BodyLabel(_("io_transcription_lang_label"))
        transcription_layout.addWidget(self.io_transcription_lang_label)
        self.transcription_lang = QComboBox()
        trans_lang_codes = ['ja', 'en', 'ko', 'ru', 'fr', 'zh']
        for code in trans_lang_codes:
            self.transcription_lang.addItem(
                _(f"target_lang_{code.replace('-', '_')}"), userData=code
            )
        transcription_layout.addWidget(self.transcription_lang, 1)

        transcription_layout.addSpacing(16)
        self.enable_segment_checkbox = QCheckBox(_("io_segment_checkbox"))
        self.enable_segment_checkbox.stateChanged.connect(self.update_segment_controls)
        transcription_layout.addWidget(self.enable_segment_checkbox)
        self.io_segment_duration_label = BodyLabel(_("io_segment_duration_label"))
        transcription_layout.addWidget(self.io_segment_duration_label)
        self.segment_duration_spin = QSpinBox()
        self.segment_duration_spin.setRange(1, 20)
        self.segment_duration_spin.setValue(10)
        self.segment_duration_spin.setEnabled(False)
        transcription_layout.addWidget(self.segment_duration_spin)
        transcription_layout.addStretch(1)
        self.input_output_layout.addLayout(transcription_layout)

        # Translation settings stay together.
        self.io_translation_group_label = SubtitleLabel(_("io_translation_group_title"))
        self.input_output_layout.addWidget(self.io_translation_group_label)
        translation_layout = QHBoxLayout()
        self.enable_translation_checkbox = QCheckBox(_("io_enable_translation_checkbox"))
        self.enable_translation_checkbox.setChecked(False)
        self.enable_translation_checkbox.stateChanged.connect(self.update_processing_controls)
        translation_layout.addWidget(self.enable_translation_checkbox)
        translation_layout.addSpacing(16)
        self.io_target_lang_label = BodyLabel(_("io_target_lang_label"))
        translation_layout.addWidget(self.io_target_lang_label)
        self.target_lang = QComboBox()
        target_lang_codes = ['zh-cn', 'zh-tw', 'en', 'ja', 'ko', 'ru', 'fr']
        for code in target_lang_codes:
            self.target_lang.addItem(
                _(f"target_lang_{code.replace('-', '_')}"), userData=code
            )
        translation_layout.addWidget(self.target_lang, 1)

        translation_layout.addSpacing(16)
        self.io_concurrency_label = BodyLabel(_("io_concurrency_label"))
        translation_layout.addWidget(self.io_concurrency_label)
        self.max_concurrent_spin = QSpinBox()
        self.max_concurrent_spin.setRange(0, 20)
        self.max_concurrent_spin.setValue(0)
        translation_layout.addWidget(self.max_concurrent_spin)
        translation_layout.addStretch(1)
        self.input_output_layout.addLayout(translation_layout)

        # Proxy Section
        self.io_proxy_label = BodyLabel(_("io_proxy_label"))
        self.input_output_layout.addWidget(self.io_proxy_label)
        self.proxy_address = QLineEdit()
        self.proxy_address.setPlaceholderText(_("io_proxy_placeholder"))
        self.input_output_layout.addWidget(self.proxy_address)

        # Output Directory Section
        self.io_output_group_label = SubtitleLabel(_("io_output_group_title"))
        self.input_output_layout.addWidget(self.io_output_group_label)
        self.io_output_dir_label = BodyLabel(_("io_output_dir_label"))
        self.input_output_layout.addWidget(self.io_output_dir_label)
        output_dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(self.default_output_dir())
        self.output_dir_edit.setText(self.default_output_dir())
        output_dir_layout.addWidget(self.output_dir_edit)
        self.output_dir_button = QPushButton(_("io_browse_dir_btn"))
        self.output_dir_button.clicked.connect(self.browse_output_dir)
        output_dir_layout.addWidget(self.output_dir_button)
        self.input_output_layout.addLayout(output_dir_layout)

        selection_layout = QHBoxLayout()
        self.use_input_dir_checkbox = QCheckBox(_("io_use_input_dir_checkbox"))
        self.use_input_dir_checkbox.stateChanged.connect(self.update_output_dir_controls)
        selection_layout.addWidget(self.use_input_dir_checkbox)
        selection_layout.addStretch()
        self.auto_shutdown_checkbox = QCheckBox(_("io_auto_shutdown_checkbox"))
        selection_layout.addWidget(self.auto_shutdown_checkbox)
        selection_layout.addStretch()
        self.input_output_layout.addLayout(selection_layout)
        
        # Subtitle target and file type are selected independently.
        format_layout = QHBoxLayout()
        self.io_output_target_label = BodyLabel(_("io_output_target_label"))
        format_layout.addWidget(self.io_output_target_label)
        self.output_target_combo = QComboBox()
        for value, key in (
            ('原文', 'output_target_original'),
            ('目标', 'output_target_translated'),
            ('双语', 'output_target_bilingual'),
        ):
            self.output_target_combo.addItem(_(key), userData=value)
        self.output_target_combo.setCurrentIndex(0)
        format_layout.addWidget(self.output_target_combo, 1)

        self.io_output_type_label = BodyLabel(_("io_output_type_label"))
        format_layout.addWidget(self.io_output_type_label)
        self.output_type_combo = QComboBox()
        self.output_type_combo.addItem(_("output_type_srt"), userData='SRT')
        self.output_type_combo.addItem(_("output_type_lrc"), userData='LRC')
        format_layout.addWidget(self.output_type_combo, 1)
        self.input_output_layout.addLayout(format_layout)


        button_layout = QHBoxLayout()
        self.run_button = QPushButton(_("io_run_btn"))
        self.run_button.clicked.connect(self.run_worker)
        button_layout.addWidget(self.run_button)

        self.cancel_button = QPushButton(_("io_cancel_btn"))
        self.cancel_button.clicked.connect(self.cancel_task)
        button_layout.addWidget(self.cancel_button)

        self.open_output_button = QPushButton(_("io_open_output_btn"))
        self.open_output_button.clicked.connect(lambda: open_path(self.output_dir_edit.text().strip() or self.default_output_dir()))
        button_layout.addWidget(self.open_output_button)

        self.clean_button = QPushButton(_("io_clean_btn"))
        self.clean_button.clicked.connect(self.cleaner)
        button_layout.addWidget(self.clean_button)

        # Add the button row layout to the input output layout
        self.input_output_layout.addLayout(button_layout)

        self.addSubInterface(self.input_output_tab, FluentIcon.HOME, _("tab_input_output"), NavigationItemPosition.TOP)

    def initDictTab(self):
        self.dict_tab = Widget("Dict", self)
        self.dict_layout = self.dict_tab.vBoxLayout

        self.dict_before_label = BodyLabel(_("dict_before_label"))
        self.dict_layout.addWidget(self.dict_before_label)
        self.before_dict = QTextEdit()
        self.before_dict.setPlaceholderText(_("dict_before_placeholder"))
        self.dict_layout.addWidget(self.before_dict)

        self.dict_gpt_label = BodyLabel(_("dict_gpt_label"))
        self.dict_layout.addWidget(self.dict_gpt_label)
        self.gpt_dict = QTextEdit()
        self.gpt_dict.setPlaceholderText(_("dict_gpt_placeholder"))
        self.dict_layout.addWidget(self.gpt_dict)

        self.dict_after_label = BodyLabel(_("dict_after_label"))
        self.dict_layout.addWidget(self.dict_after_label)
        self.after_dict = QTextEdit()
        self.after_dict.setPlaceholderText(_("dict_after_placeholder"))
        self.dict_layout.addWidget(self.after_dict)

        self.dict_extra_label = BodyLabel(_("dict_extra_label"))
        self.dict_layout.addWidget(self.dict_extra_label)
        self.extra_prompt = QTextEdit()
        self.extra_prompt.setPlaceholderText(_("dict_extra_placeholder"))
        self.dict_layout.addWidget(self.extra_prompt)

        self.dict_prompt_mode_label = BodyLabel(_("dict_prompt_mode_label"))
        self.dict_layout.addWidget(self.dict_prompt_mode_label)
        self.change_prompt_mode = QComboBox()
        for _pm_val, _pm_key in (
            ('不修改', 'dict_prompt_mode_no'),
            ('追加', 'dict_prompt_mode_append'),
            ('覆盖', 'dict_prompt_mode_overwrite'),
        ):
            self.change_prompt_mode.addItem(_(_pm_key), userData=_pm_val)
        _default_pm_idx = self.change_prompt_mode.findData('不修改')
        if _default_pm_idx >= 0:
            self.change_prompt_mode.setCurrentIndex(_default_pm_idx)
        self.dict_layout.addWidget(self.change_prompt_mode)

        self.addSubInterface(self.dict_tab, FluentIcon.SETTING, _("tab_dict"), NavigationItemPosition.TOP)
        
    def initSettingsTab(self):
        self.settings_tab = Widget("Settings", self)
        self.settings_layout = self.settings_tab.vBoxLayout
        
        # CrispASR Section
        self.settings_asr_model_label = BodyLabel(_("settings_asr_model_label"))
        self.settings_layout.addWidget(self.settings_asr_model_label)
        self.asr_model_file = QComboBox()
        self.asr_model_file.addItems(_list_crispasr_models())
        self.settings_layout.addWidget(self.asr_model_file)

        self.settings_asr_aligner_label = BodyLabel(_("settings_asr_aligner_label"))
        self.settings_layout.addWidget(self.settings_asr_aligner_label)
        self.aligner_file = QComboBox()
        self.aligner_file.addItems(_list_crispasr_aligners())
        self.settings_layout.addWidget(self.aligner_file)

        self.settings_asr_backend_label = BodyLabel(_("settings_asr_backend_label"))
        self.settings_layout.addWidget(self.settings_asr_backend_label)
        self.asr_backend = QComboBox()
        self.asr_backend.addItems(_list_crispasr_backends())
        if self.asr_backend.findText('qwen3-1.7b') >= 0:
            self.asr_backend.setCurrentText('qwen3-1.7b')
        self.settings_layout.addWidget(self.asr_backend)

        self.settings_asr_param_label = BodyLabel(_("settings_asr_param_label"))
        self.settings_layout.addWidget(self.settings_asr_param_label)
        self.param_crispasr = QTextEdit()
        self.param_crispasr.setPlaceholderText(_("settings_asr_param_placeholder"))
        self.settings_layout.addWidget(self.param_crispasr)

        button_layout = QHBoxLayout()

        self.open_crispasr_dir = QPushButton(_("settings_open_crispasr_btn"))
        self.open_crispasr_dir.clicked.connect(lambda: open_path(os.path.join(os.getcwd(), 'crispasr')))
        button_layout.addWidget(self.open_crispasr_dir)

        self.refresh_speech_models_button = QPushButton(_("settings_refresh_speech_btn"))
        self.refresh_speech_models_button.clicked.connect(self.refresh_speech_model_lists)
        button_layout.addWidget(self.refresh_speech_models_button)

        self.test_offline_asr_button = QPushButton(_("settings_test_offline_asr_btn"))
        self.test_offline_asr_button.clicked.connect(self.run_test_offline_asr)
        button_layout.addWidget(self.test_offline_asr_button)
        self.settings_layout.addLayout(button_layout)

        # Created here for config loading; displayed beside vocal separation.
        self.settings_uvr_label = BodyLabel(_("settings_uvr_label"))
        self.uvr_file = QComboBox()
        uvr_lst = [i for i in os.listdir('separate') if i.endswith('onnx')]
        self.uvr_file.addItems(uvr_lst)
        self.open_uvr_dir = QPushButton(_("settings_open_uvr_btn"))
        self.open_uvr_dir.clicked.connect(lambda: open_path(os.path.join(os.getcwd(),'separate')))
        self.refresh_uvr_models_button = QPushButton(_("settings_refresh_uvr_btn"))
        self.refresh_uvr_models_button.clicked.connect(self.refresh_uvr_model_list)

        self.addSubInterface(self.settings_tab, FluentIcon.SETTING, _("tab_settings"), NavigationItemPosition.TOP)

    def initAdvancedSettingTab(self):
        self.advanced_settings_tab = Widget("AdvancedSettings", self)
        self.advanced_settings_layout = self.advanced_settings_tab.vBoxLayout

        # Translator Section
        model_row = QHBoxLayout()
        self.adv_translator_mode_label = BodyLabel(_("adv_translator_mode_label"))
        model_row.addWidget(self.adv_translator_mode_label)
        self.translator_mode = QComboBox()
        self.translator_mode.addItem(_("adv_translator_mode_online"), userData='online')
        self.translator_mode.addItem(_("adv_translator_mode_local"), userData='local')
        model_row.addWidget(self.translator_mode)
        model_row.addStretch()
        self.advanced_settings_layout.addLayout(model_row)

        translator_row = QHBoxLayout()
        self.adv_online_translator_label = BodyLabel(_("adv_online_translator_label"))
        translator_row.addWidget(self.adv_online_translator_label)
        self.online_translator_group = QComboBox()
        self.online_translator_group.addItems(ONLINE_TRANSLATOR_SUPPORTED)
        translator_row.addWidget(self.online_translator_group, 1)
        translator_row.addSpacing(20)
        self.adv_local_translator_label = BodyLabel(_("adv_local_translator_label"))
        translator_row.addWidget(self.adv_local_translator_label)
        self.local_translator_group = QComboBox()
        self.local_translator_group.addItems(LOCAL_TRANSLATOR_SUPPORTED)
        translator_row.addWidget(self.local_translator_group, 1)
        self.advanced_settings_layout.addLayout(translator_row)

        self.adv_online_token_label = BodyLabel(_("adv_online_token_label"))
        self.advanced_settings_layout.addWidget(self.adv_online_token_label)
        self.gpt_token = QLineEdit()
        self.gpt_token.setPlaceholderText(_("adv_online_token_placeholder"))
        self.advanced_settings_layout.addWidget(self.gpt_token)

        self.adv_online_model_label = BodyLabel(_("adv_online_model_label"))
        self.advanced_settings_layout.addWidget(self.adv_online_model_label)
        self.gpt_model = QLineEdit()
        self.gpt_model.setPlaceholderText(_("adv_online_model_placeholder"))
        self.advanced_settings_layout.addWidget(self.gpt_model)

        self.adv_online_address_label = BodyLabel(_("adv_online_address_label"))
        self.advanced_settings_layout.addWidget(self.adv_online_address_label)
        self.gpt_address = QLineEdit()
        self.gpt_address.setPlaceholderText(_("adv_online_address_placeholder"))
        self.advanced_settings_layout.addWidget(self.gpt_address)

        self.adv_offline_model_label = BodyLabel(_("adv_offline_model_label"))
        self.advanced_settings_layout.addWidget(self.adv_offline_model_label)
        self.sakura_file = QComboBox()
        sakura_lst = [i for i in os.listdir('llama') if i.endswith('gguf')]
        self.sakura_file.addItems(sakura_lst)
        self.advanced_settings_layout.addWidget(self.sakura_file)

        self.adv_offline_gpu_label = BodyLabel(_("adv_offline_gpu_label"))
        self.advanced_settings_layout.addWidget(self.adv_offline_gpu_label)
        self.sakura_mode = QLineEdit()
        self.sakura_mode.setText("100")
        self.advanced_settings_layout.addWidget(self.sakura_mode)

        self.adv_offline_param_label = BodyLabel(_("adv_offline_param_label"))
        self.advanced_settings_layout.addWidget(self.adv_offline_param_label)
        self.param_llama = QTextEdit()
        self.param_llama.setPlaceholderText(_("adv_offline_param_placeholder"))
        self.advanced_settings_layout.addWidget(self.param_llama)

        button_layout = QHBoxLayout()

        self.open_model_dir = QPushButton(_("adv_open_model_btn"))
        self.open_model_dir.clicked.connect(lambda: open_path(os.path.join(os.getcwd(),'llama')))
        button_layout.addWidget(self.open_model_dir)

        self.refresh_language_models_button = QPushButton(_("adv_refresh_model_btn"))
        self.refresh_language_models_button.clicked.connect(self.refresh_language_model_lists)
        button_layout.addWidget(self.refresh_language_models_button)

        self.test_offline_translation_button = QPushButton(_("adv_test_offline_btn"))
        self.test_offline_translation_button.clicked.connect(
            self.run_test_offline_translation
        )
        button_layout.addWidget(self.test_offline_translation_button)

        self.test_online_button = QPushButton(_("adv_test_api_btn"))
        self.test_online_button.clicked.connect(self.run_test_online_api)
        button_layout.addWidget(self.test_online_button)
        self.advanced_settings_layout.addLayout(button_layout)

        self.translator_mode.currentIndexChanged.connect(
            self.update_translator_mode_controls
        )
        self.update_translator_mode_controls()

        self.addSubInterface(self.advanced_settings_tab, FluentIcon.SETTING, _("tab_advanced_settings"), NavigationItemPosition.TOP)

    def initClipTab(self):
        self.clip_tab = Widget("Clip", self)
        self.clip_layout = self.clip_tab.vBoxLayout

        # Clip Section
        self.clip_trim_config = QWidget(self.clip_tab)
        clip_trim_layout = QVBoxLayout(self.clip_trim_config)
        clip_trim_layout.setContentsMargins(0, 0, 0, 0)
        clip_trim_layout.setSpacing(8)
        self.clip_files_list = QTextEdit()
        self.clip_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.clip_files_list)
        self.clip_files_list.setPlaceholderText(_("clip_placeholder"))
        clip_trim_layout.addWidget(self.clip_files_list)

        hbox = QHBoxLayout()
        left_v = QVBoxLayout()
        right_v = QVBoxLayout()

        self.clip_start_time = QLineEdit()
        self.clip_start_time.setPlaceholderText(_("clip_start_placeholder"))
        self.clip_start_label = BodyLabel(_("clip_start_label"))
        left_v.addWidget(self.clip_start_label)
        left_v.addWidget(self.clip_start_time)

        self.clip_end_time = QLineEdit()
        self.clip_end_time.setPlaceholderText(_("clip_end_placeholder"))
        self.clip_end_label = BodyLabel(_("clip_end_label"))
        right_v.addWidget(self.clip_end_label)
        right_v.addWidget(self.clip_end_time)

        hbox.addLayout(left_v)
        hbox.addLayout(right_v)
        clip_trim_layout.addLayout(hbox)

        self.run_clip_button = QPushButton(_("clip_run_btn"))
        self.run_clip_button.clicked.connect(self.run_clip)
        clip_trim_layout.addWidget(self.run_clip_button)
        self.clip_layout.addWidget(self.clip_trim_config)

        # Vocal Split
        self.clip_vocal_config = QWidget(self.clip_tab)
        clip_vocal_layout = QVBoxLayout(self.clip_vocal_config)
        clip_vocal_layout.setContentsMargins(0, 0, 0, 0)
        clip_vocal_layout.setSpacing(8)
        # Keep the selected separation model immediately beside this tool's
        # input configuration instead of in the speech-model settings.
        uvr_model_layout = QHBoxLayout()
        uvr_model_layout.addWidget(self.settings_uvr_label)
        uvr_model_layout.addWidget(self.uvr_file, 1)
        clip_vocal_layout.addLayout(uvr_model_layout)

        self.uvr_file_list = QTextEdit()
        self.uvr_file_list.setAcceptDrops(True)
        self._bind_drop_event(self.uvr_file_list)
        self.uvr_file_list.setPlaceholderText(_("clip_vocal_placeholder"))
        clip_vocal_layout.addWidget(self.uvr_file_list)

        self.run_uvr_button = QPushButton(_("clip_vocal_run_btn"))
        self.run_uvr_button.clicked.connect(self.run_vocal_split)
        clip_vocal_layout.addWidget(self.run_uvr_button)
        clip_vocal_layout.addWidget(self.open_uvr_dir)
        clip_vocal_layout.addWidget(self.refresh_uvr_models_button)
        self.clip_layout.addWidget(self.clip_vocal_config)

        self.addSubInterface(self.clip_tab, FluentIcon.DEVELOPER_TOOLS, _("tab_clip"), NavigationItemPosition.TOP)

    def initSynthTab(self):
        self.synth_tab = Widget("Synth", self)
        self.synth_layout = self.synth_tab.vBoxLayout

        # Video Synth
        self.synth_video_config = QWidget(self.synth_tab)
        synth_video_layout = QVBoxLayout(self.synth_video_config)
        synth_video_layout.setContentsMargins(0, 0, 0, 0)
        synth_video_layout.setSpacing(8)
        # Video Files
        vbox_video = QHBoxLayout()
        self.synth_video_label = BodyLabel(_("synth_video_label"))
        vbox_video.addWidget(self.synth_video_label)
        self.synth_video_browse_btn = QPushButton(_("synth_browse_video_btn"))
        self.synth_video_browse_btn.clicked.connect(self.browse_synth_video)
        vbox_video.addWidget(self.synth_video_browse_btn)
        synth_video_layout.addLayout(vbox_video)
        
        self.synth_video_files_list = QTextEdit()
        self.synth_video_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.synth_video_files_list)
        self.synth_video_files_list.setPlaceholderText(_("synth_video_placeholder"))
        synth_video_layout.addWidget(self.synth_video_files_list)

        # Subtitle Files
        vbox_srt = QHBoxLayout()
        self.synth_srt_label = BodyLabel(_("synth_srt_label"))
        vbox_srt.addWidget(self.synth_srt_label)
        self.synth_srt_browse_btn = QPushButton(_("synth_browse_srt_btn"))
        self.synth_srt_browse_btn.clicked.connect(self.browse_synth_srt)
        vbox_srt.addWidget(self.synth_srt_browse_btn)
        synth_video_layout.addLayout(vbox_srt)

        self.synth_srt_files_list = QTextEdit()
        self.synth_srt_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.synth_srt_files_list)
        self.synth_srt_files_list.setPlaceholderText(_("synth_srt_placeholder"))
        synth_video_layout.addWidget(self.synth_srt_files_list)

        hbox = QHBoxLayout()

        self.synth_subtitle_type_label = BodyLabel(_("synth_subtitle_type_label"))
        hbox.addWidget(self.synth_subtitle_type_label)
        self.subtitle_type_combo = QComboBox()
        self.subtitle_type_combo.addItem(_("synth_sub_hard"), userData="硬字幕")
        self.subtitle_type_combo.addItem(_("synth_sub_soft"), userData="软字幕")
        hbox.addWidget(self.subtitle_type_combo)

        self.synth_font_label = BodyLabel(_("synth_font_label"))
        hbox.addWidget(self.synth_font_label)

        self.subtitle_font_combo = QComboBox()
        for font_item in self.collect_font_candidates():
            self.subtitle_font_combo.addItem(font_item)
        hbox.addWidget(self.subtitle_font_combo)

        self.run_synth_button = QPushButton(_("synth_run_btn"))
        self.run_synth_button.clicked.connect(self.run_synth)
        hbox.addWidget(self.run_synth_button)
        synth_video_layout.addLayout(hbox)
        self.synth_layout.addWidget(self.synth_video_config)

        # Audio Synth
        self.synth_audio_config = QWidget(self.synth_tab)
        synth_audio_layout = QVBoxLayout(self.synth_audio_config)
        synth_audio_layout.setContentsMargins(0, 0, 0, 0)
        synth_audio_layout.setSpacing(8)
        self.synth_audio_files_list = QTextEdit()
        self.synth_audio_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.synth_audio_files_list)
        self.synth_audio_files_list.setPlaceholderText(_("synth_audio_placeholder"))
        synth_audio_layout.addWidget(self.synth_audio_files_list)
        self.run_synth_audio_button = QPushButton(_("synth_audio_run_btn"))
        self.run_synth_audio_button.clicked.connect(self.run_synth_audio)
        synth_audio_layout.addWidget(self.run_synth_audio_button)
        self.synth_layout.addWidget(self.synth_audio_config)

        self.addSubInterface(self.synth_tab, FluentIcon.DEVELOPER_TOOLS, _("tab_synth"), NavigationItemPosition.TOP)

    def initSummarizeTab(self):
        self.summarize_tab = Widget("Summarize", self)
        self.summarize_layout = self.summarize_tab.vBoxLayout

        self.summarize_prompt_label = BodyLabel(_("summarize_prompt_label"))
        self.summarize_layout.addWidget(self.summarize_prompt_label)
        self.summarize_prompt = QTextEdit()
        self.summarize_prompt.setPlaceholderText(_("summarize_prompt_placeholder"))
        self.summarize_layout.addWidget(self.summarize_prompt)

        self.summarize_input_label = BodyLabel(_("summarize_input_label"))
        self.summarize_layout.addWidget(self.summarize_input_label)
        self.summarize_files_list = QTextEdit()
        self.summarize_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.summarize_files_list)
        self.summarize_files_list.setPlaceholderText(_("summarize_input_placeholder"))
        self.summarize_layout.addWidget(self.summarize_files_list)

        self.run_summarize_button = QPushButton(_("summarize_run_btn"))
        self.run_summarize_button.clicked.connect(self.run_summarize)
        self.summarize_layout.addWidget(self.run_summarize_button)

        self.addSubInterface(self.summarize_tab, FluentIcon.DEVELOPER_TOOLS, _("tab_summarize"), NavigationItemPosition.TOP)

    def run_worker(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def run_clip(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.clip)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def run_synth(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.synth)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def run_synth_audio(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.audiosynth)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def run_vocal_split(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.vocal_split)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def run_summarize(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.summarize)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def show_model_selection_dialog(self, models):
        dialog = QDialog(self)
        dialog.setWindowTitle(_("dialog_select_model_title"))
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        label = QLabel(_("dialog_select_model_label"))
        layout.addWidget(label)

        combo = QComboBox()
        combo.addItems(models)
        layout.addWidget(combo)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton(_("dialog_ok"))
        cancel_btn = QPushButton(_("dialog_cancel"))
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        ok_btn.clicked.connect(lambda: (
            self.gpt_model.setText(combo.currentText()),
            dialog.accept()
        ))
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec_()

    def run_test_online_api(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.test_online_api)
        self.worker.show_model_dialog.connect(self.show_model_selection_dialog)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def _set_action_button_enabled(self, source_button, enabled):
        """Keep a hidden source action and its visible mirror in sync."""
        source_button.setEnabled(enabled)
        for source, mirror in self._button_mirrors:
            if source is source_button:
                mirror.setEnabled(enabled)

    def _offline_test_finished(self, source_button):
        enabled = True
        if source_button is self.test_offline_translation_button:
            enabled = self.translator_mode.currentData() == 'local'
        self._set_action_button_enabled(source_button, enabled)
        self.thread = None
        self.worker = None

    def _start_offline_test(self, worker_slot, source_button):
        if self.thread is not None and self.thread.isRunning():
            self._emit_status(_("status_offline_test_busy"))
            return

        self._set_action_button_enabled(source_button, False)
        thread = QThread(self)
        worker = MainWorker(self)
        worker.moveToThread(thread)
        thread.started.connect(worker_slot(worker))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(
            lambda button=source_button: self._offline_test_finished(button)
        )
        thread.finished.connect(thread.deleteLater)
        self.thread = thread
        self.worker = worker
        thread.start()

    def run_test_offline_asr(self):
        self._start_offline_test(
            lambda worker: worker.test_offline_asr,
            self.test_offline_asr_button,
        )

    def run_test_offline_translation(self):
        self._start_offline_test(
            lambda worker: worker.test_offline_translation,
            self.test_offline_translation_button,
        )
    
    def cleaner(self):
        self._emit_status(_("status_cleaning_intermediate"))
        if os.path.exists('project/gt_input'):
            shutil.rmtree('project/gt_input')
        if os.path.exists('project/gt_output'):
            shutil.rmtree('project/gt_output')
        if os.path.exists('project/transl_cache'):
            shutil.rmtree('project/transl_cache')
        self._emit_status(_("status_cleaning_output"))
        if os.path.exists('project/cache'):
            shutil.rmtree('project/cache')
        os.makedirs('project/cache', exist_ok=True)

def error_handler(func):
    def wrapper(self):
        try:
            func(self)
        except Exception as e:
            self._emit_status(_("status_generic_error", error=e))
            self.finished.emit()
            # Ensure all child processes are terminated on error
            self.stop()

    return wrapper
class MainWorker(QObject):
    finished = pyqtSignal()
    show_model_dialog = pyqtSignal(list)

    def __init__(self, master):
        super().__init__()
        self.master = master
        self.status = master.status
        self.msg_queue = master.msg_queue
        self.child_processes = []
        self._child_processes_lock = threading.Lock()
        self._proc_readers = {}
        self._stop_requested = False
        self._stop_event = asyncio.Event()

    def _emit_status(self, msg: str):
        """同时向统一消息队列和窗口标题发送状态消息"""
        self.msg_queue.put("status", msg)
        self.status.emit(msg)

    def _start_process(self, args, label=None):
        creationflags = 0x08000000 if os.name == 'nt' else 0
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        reader = threading.Thread(
            target=_stream_proc_to_queue,
            args=(proc, self.msg_queue, label),
            daemon=True,
        )
        with self._child_processes_lock:
            self.child_processes.append(proc)
            self._proc_readers[proc] = reader
        reader.start()
        self.pid = proc
        return proc

    def _cleanup_process(self, proc):
        if not proc:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            reader = None
            with self._child_processes_lock:
                if proc in self.child_processes:
                    self.child_processes.remove(proc)
                reader = self._proc_readers.pop(proc, None)
            if reader is not None:
                reader.join(timeout=2)

    def _terminate_all_children(self):
        with self._child_processes_lock:
            children = list(self.child_processes)
        for proc in children:
            self._cleanup_process(proc)

    def stop(self):
        self._stop_requested = True
        self._stop_event.set()
        self._terminate_all_children()
        if hasattr(self, '_translation_pool') and self._translation_pool:
            self._translation_pool.stop()

    def save_config(self, silent: bool = False):
        self.master.save_config(silent)

    @error_handler
    def update_translation_config(self):
        self._emit_status(_("status_config_translating"))
        translator = self.master.selected_translator()
        gpt_token = self.master.gpt_token.text() or _load_api_key()
        gpt_address = self.master.gpt_address.text()
        gpt_model = self.master.gpt_model.text()
        sakura_file = self.master.sakura_file.currentText()
        proxy_address = self.master.proxy_address.text()

        if not gpt_token:
            gpt_token = 'sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

        try:
            with open('project/config.yaml', 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            # 首次运行：从默认模板初始化配置文件
            from GalTransl.DefaultProjectConfig import DEFAULT_PROJECT_CONFIG_YAML
            self._emit_status(_("status_first_run_init"))
            os.makedirs('project', exist_ok=True)
            cfg = yaml.safe_load(DEFAULT_PROJECT_CONFIG_YAML) or {}
            with open('project/config.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(cfg, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        except Exception as e:
            self._emit_status(_("status_config_read_error", error=e))
            return

        # Update language setting
        if 'common' not in cfg:
            cfg['common'] = {}
        target_lang = self.master.target_lang.currentData() if hasattr(self.master, 'target_lang') else 'zh-cn'
        source_lang = self.master.transcription_lang.currentData() or 'ja'
        if source_lang == 'zh':
            source_lang = 'zh-cn'
        cfg['common']['language'] = f"{source_lang}2{target_lang}"

        # Update backendSpecific configuration
        if 'backendSpecific' not in cfg:
            cfg['backendSpecific'] = {}

        # Determine which backend to use
        if 'sakura' in translator:
            # Sakura LLM configuration
            if 'SakuraLLM' not in cfg['backendSpecific']:
                cfg['backendSpecific']['SakuraLLM'] = {}
            sakura_cfg = cfg['backendSpecific']['SakuraLLM']
            sakura_cfg['endpoints'] = ['http://127.0.0.1:8989']
            sakura_cfg['rewriteModelName'] = sakura_file if sakura_file else ""
        else:
            # OpenAI-Compatible configuration
            if 'OpenAI-Compatible' not in cfg['backendSpecific']:
                cfg['backendSpecific']['OpenAI-Compatible'] = {}
            openai_cfg = cfg['backendSpecific']['OpenAI-Compatible']

            # Determine endpoint and model
            if 'custom' in translator:
                endpoint = gpt_address if gpt_address else 'https://api.openai.com'
                model = gpt_model if gpt_model else ''
            else:
                endpoint = ONLINE_TRANSLATOR_MAPPING.get(translator, 'https://api.openai.com')
                model = gpt_model
                if 'llamacpp' in translator:
                    model = sakura_file

            # Remove trailing /v1 or /v1/ from endpoint
            endpoint = endpoint.rstrip('/')
            if endpoint.endswith('/v1'):
                endpoint = endpoint[:-3]

            # Configure tokens
            openai_cfg['tokens'] = [{
                'token': gpt_token,
                'endpoint': endpoint,
                'modelName': model
            }]
            openai_cfg['tokenStrategy'] = "random"
            openai_cfg['checkAvailable'] = True
            openai_cfg['stream'] = True
            openai_cfg['apiTimeout'] = 120
            openai_cfg['apiErrorWait'] = "auto"

        # Update proxy configuration
        if 'proxy' not in cfg:
            cfg['proxy'] = {}
        cfg['proxy']['enableProxy'] = bool(proxy_address)
        if proxy_address:
            cfg['proxy']['proxies'] = [{'address': proxy_address}]
        else:
            cfg['proxy']['proxies'] = []

        # Update extra prompt configuration (gpt.change_prompt and gpt.prompt_content)
        extra_prompt = self.master.extra_prompt.toPlainText().strip() if hasattr(self.master, 'extra_prompt') else ''
        change_prompt_mode = self.master.change_prompt_mode.currentData() if hasattr(self.master, 'change_prompt_mode') else '不修改'

        # Map UI mode to config values
        mode_mapping = {
            '不修改': 'no',
            '追加': 'AdditionalPrompt',
            '覆盖': 'OverwritePrompt'
        }

        if 'common' not in cfg:
            cfg['common'] = {}

        cfg['common']['gpt.change_prompt'] = mode_mapping.get(change_prompt_mode, 'no')

        if change_prompt_mode != '不修改' and extra_prompt:
            cfg['common']['gpt.prompt_content'] = extra_prompt
        elif change_prompt_mode == '不修改':
            # If mode is 'no', clear the prompt_content to use default
            if 'gpt.prompt_content' in cfg['common']:
                del cfg['common']['gpt.prompt_content']

        try:
            with open('project/config.yaml', 'w', encoding='utf-8') as f:
                yaml.dump(cfg, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        except Exception as e:
            self._emit_status(_("status_config_write_error", error=e))

    @error_handler
    def test_online_api(self):
        self._stop_requested = False
        self._stop_event.clear()
        self.save_config()
        translator = self.master.selected_translator()
        gpt_token = self.master.gpt_token.text() or _load_api_key()
        gpt_address = self.master.gpt_address.text()
        gpt_model = self.master.gpt_model.text()
        proxy_address = self.master.proxy_address.text()

        base_url = None
        if 'custom' in translator and gpt_address:
            base_url = gpt_address
        else:
            base_url = ONLINE_TRANSLATOR_MAPPING.get(translator)

        if not base_url:
            self._emit_status(_("status_api_select_model"))
            self.finished.emit()
            return

        base_url = base_url.rstrip('/') + '/v1/models'

        self._emit_status(_("status_api_testing", url=base_url))
        try:
            if proxy_address:
                os.environ['HTTP_PROXY'] = proxy_address
                os.environ['HTTPS_PROXY'] = proxy_address
            else:
                os.environ.pop('HTTP_PROXY', None)
                os.environ.pop('HTTPS_PROXY', None)

            headers = {
                'Authorization': f'Bearer {gpt_token}',
                'Content-Type': 'application/json'
            }

            resp = requests.get(base_url, headers=headers, timeout=20)
            resp.raise_for_status()

            models = []
            parse_error = False
            try:
                data = resp.json()
                if isinstance(data, dict) and 'data' in data:
                    for item in data['data']:
                        if isinstance(item, dict) and 'id' in item:
                            models.append(item['id'])
                if models:
                    self.show_model_dialog.emit(models)
                    self._emit_status(_("status_api_complete", count=len(models)))
                else:
                    parse_error = True
            except Exception:
                parse_error = True

            if parse_error:
                try:
                    body = resp.text[:500].replace('\n', ' ')
                except Exception:
                    body = str(resp)[:500].replace('\n', ' ')
                self._emit_status(_("status_api_complete_body", url=base_url, body=body))
        except Exception as e:
            self._emit_status(_("status_api_error", error=e))

        self.finished.emit()

    def test_offline_asr(self):
        """Load the selected CrispASR models and transcribe a user sample."""
        self._stop_requested = False
        self._stop_event.clear()
        started_at = time()
        proc = None
        try:
            language = self.master.transcription_lang.currentData() or 'ja'
            audio_file = _offline_asr_test_audio(language)
            if not audio_file.is_file():
                raise FileNotFoundError(_("offline_test_audio_missing"))

            model_file = self.master.asr_model_file.currentText().strip()
            aligner_file = self.master.aligner_file.currentText().strip()
            backend = self.master.asr_backend.currentText().strip()
            param_crispasr = self.master.param_crispasr.toPlainText().strip()
            if not model_file:
                raise ValueError(_("offline_test_asr_model_missing"))
            if not aligner_file:
                raise ValueError(_("offline_test_aligner_missing"))

            self._emit_status(_(
                "status_offline_asr_test_starting", model=model_file
            ))
            with tempfile.TemporaryDirectory(prefix='voicetransl_asr_test_') as temp_dir:
                output_base = Path(temp_dir) / 'transcript'
                command = _build_crispasr_command(
                    audio_file, output_base, model_file, language,
                    param_crispasr, aligner_file=aligner_file, backend=backend,
                )
                self.msg_queue.put("detail", _format_command(command))
                proc = self._start_process(command, label='CrispASR test')
                try:
                    return_code = proc.wait(timeout=300)
                except subprocess.TimeoutExpired as exc:
                    raise TimeoutError(_("offline_test_asr_timeout")) from exc

                if self._stop_requested:
                    self._emit_status(_("status_offline_test_cancelled"))
                    return
                if return_code != 0:
                    raise RuntimeError(f'CrispASR exited with code {return_code}')

                result_file = output_base.with_suffix('.srt')
                if not result_file.is_file() or result_file.stat().st_size == 0:
                    raise RuntimeError(_("offline_test_asr_no_output"))

            elapsed = time() - started_at
            self._emit_status(_(
                "status_offline_asr_test_success", seconds=elapsed
            ))
        except Exception as exc:
            if not self._stop_requested:
                self._emit_status(_("status_offline_asr_test_failed", error=exc))
        finally:
            if proc is not None:
                self._cleanup_process(proc)
            self.finished.emit()

    def test_offline_translation(self):
        """Start llama-server and perform one real chat completion."""
        self._stop_requested = False
        self._stop_event.clear()
        started_at = time()
        proc = None
        try:
            model_file = self.master.sakura_file.currentText().strip()
            gpu_layers = self.master.sakura_mode.text().strip()
            param_llama = self.master.param_llama.toPlainText().strip()
            if not model_file:
                raise ValueError(_("offline_test_translation_model_missing"))

            port = _find_available_local_port()
            command = _build_llama_server_command(
                model_file, gpu_layers, param_llama, port
            )
            self._emit_status(_(
                "status_offline_translation_test_starting", model=model_file
            ))
            self.msg_queue.put("detail", _format_command(command))
            proc = self._start_process(command, label='llama-server test')

            session = requests.Session()
            session.trust_env = False
            deadline = time() + 180
            last_error = ''
            while time() < deadline:
                if self._stop_requested:
                    self._emit_status(_("status_offline_test_cancelled"))
                    return
                return_code = proc.poll()
                if return_code is not None:
                    raise RuntimeError(f'llama-server exited with code {return_code}')
                try:
                    response = session.post(
                        f'http://127.0.0.1:{port}/v1/chat/completions',
                        json={
                            'model': Path(model_file).name,
                            'messages': [{
                                'role': 'user',
                                'content': 'Reply with only: OK',
                            }],
                            'max_tokens': 8,
                            'temperature': 0,
                        },
                        timeout=8,
                    )
                    if response.status_code == 200:
                        payload = response.json()
                        if isinstance(payload, dict) and payload.get('choices'):
                            elapsed = time() - started_at
                            self._emit_status(_(
                                "status_offline_translation_test_success",
                                seconds=elapsed,
                            ))
                            return
                    last_error = f'HTTP {response.status_code}: {response.text[:200]}'
                except requests.RequestException as exc:
                    last_error = str(exc)
                except ValueError as exc:
                    last_error = str(exc)
                sleep(1)

            detail = last_error or _("offline_test_no_response")
            raise TimeoutError(_("offline_test_translation_timeout", detail=detail))
        except Exception as exc:
            if not self._stop_requested:
                self._emit_status(_(
                    "status_offline_translation_test_failed", error=exc
                ))
        finally:
            if proc is not None:
                self._cleanup_process(proc)
            self.finished.emit()

    @error_handler
    def vocal_split(self):
        self._stop_requested = False
        self._stop_event.clear()
        self.save_config()
        uvr_file = self.master.uvr_file.currentText()
        if not uvr_file.endswith('.onnx'):
            self._emit_status(_("status_uvr_model_error"))
            self.finished.emit()
            return

        input_files = self.master.uvr_file_list.toPlainText()
        if input_files:
            input_files = input_files.strip().split('\n')
            for idx, input_file in enumerate(input_files):
                if self._stop_requested:
                    break
                if not os.path.exists(input_file):
                    self._emit_status(_("status_file_not_exist", file=input_file))
                    self.finished.emit()

                self._emit_status(_("status_vocal_split_label", idx=idx+1, total=len(input_files)))
                proc = self._start_process([*_SEPARATE_CMD, '-m', os.path.join('separate',uvr_file), input_file])
                proc.wait()
                self._cleanup_process(proc)

            self._emit_status(_("status_vocal_processing_done"))
        self.finished.emit()

    @error_handler
    def summarize(self):
        self._stop_requested = False
        self._stop_event.clear()
        self.save_config()
        # 统一刷新翻译配置，供摘要复用
        self.update_translation_config()
        input_files = self.master.summarize_files_list.toPlainText()
        # 使用与主程序相同的配置：从 project/config.yaml 读取 GPT 配置与代理
        try:
            with open('project/config.yaml', 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
        except Exception as e:
            self._emit_status(_("status_config_read_error", error=e))
            self.finished.emit()
            return

        backend = (cfg or {}).get('backendSpecific', {})
        openai_cfg = backend.get('OpenAI-Compatible', {})
        tokens = openai_cfg.get('tokens', []) or []
        token = tokens[0].get('token') if tokens else ''
        address = tokens[0].get('endpoint') if tokens else ''
        model = tokens[0].get('modelName') if tokens else ''

        # 代理设置同步
        proxy_cfg = (cfg or {}).get('proxy', {})
        if proxy_cfg.get('enableProxy'):
            proxies = proxy_cfg.get('proxies') or []
            if proxies and isinstance(proxies[0], dict):
                proxy_address = proxies[0].get('address')
                if proxy_address:
                    os.environ['HTTP_PROXY'] = proxy_address
                    os.environ['HTTPS_PROXY'] = proxy_address
        else:
            # 清理可能遗留的代理环境变量
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)

        prompt = self.master.summarize_prompt.toPlainText()
        if input_files:
            input_files = input_files.strip().split('\n')
            for idx, input_file in enumerate(input_files):
                if not os.path.exists(input_file):
                    self._emit_status(_("status_file_not_exist", file=input_file))
                    self.finished.emit()

                from summarize import summarize
                self._emit_status(_("status_summarize_processing", idx=idx+1, total=len(input_files)))
                summarize(input_file, address, model, token, prompt)
            self._emit_status(_("status_processing_done"))
        self.finished.emit()

    @error_handler
    def synth(self):
        self._stop_requested = False
        self._stop_event.clear()
        self.save_config()
        subtitle_font = self.master.subtitle_font_combo.currentText().strip()
        subtitle_type = self.master.subtitle_type_combo.currentData() or "硬字幕"
        
        video_files_text = self.master.synth_video_files_list.toPlainText().strip()
        srt_files_text = self.master.synth_srt_files_list.toPlainText().strip()
        
        def escape_sub_path(path_str: str) -> str:
            # ffmpeg subtitles filter needs windows drive colon escaped
            return path_str.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")

        def build_subtitle_filter(srt_path: str, font_value: str) -> str:
            srt_abs = escape_sub_path(str(Path(srt_path).resolve()))
            parts = [f"subtitles='{srt_abs}'"]
            if font_value:
                font_path = Path(font_value)
                if font_path.exists():
                    fonts_dir = escape_sub_path(str(font_path.parent.resolve()))
                    font_name = font_path.name.replace("'", "\\'")
                    parts.append(f"fontsdir='{fonts_dir}'")
                    parts.append(f"force_style='FontName={font_name}'")
                else:
                    font_name = font_value.replace("'", "\\'")
                    parts.append(f"force_style='FontName={font_name}'")
            return ':'.join(parts)

        if video_files_text and srt_files_text:
            video_files = video_files_text.split('\n')
            srt_files = srt_files_text.split('\n')
            
            if len(srt_files) != len(video_files):
                self._emit_status(_("status_synth_mismatch"))
                self.finished.emit()
                return
            
            for idx, (input_file, input_srt) in enumerate(zip(video_files, srt_files)):
                if self._stop_requested:
                    break
                if not os.path.exists(input_file):
                    self._emit_status(_("status_file_not_exist", file=input_file))
                    self.finished.emit()
                    return

                if not os.path.exists(input_srt):
                    self._emit_status(_("status_file_not_exist", file=input_srt))
                    self.finished.emit()
                    return

                self._emit_status(_("status_synth_processing", file=input_file, idx=idx+1, total=len(video_files)))
                
                output_file = input_file + '_synth.mp4'

                if subtitle_type == "硬字幕":
                    input_srt_cache = shutil.copy(input_srt, 'project/cache/')
                    subtitle_filter = build_subtitle_filter(input_srt_cache, subtitle_font)
                    if subtitle_font:
                        self._emit_status(_("status_synth_font", font=subtitle_font))
                    self._emit_status(_("status_synth_hard_sub"))
                    proc = self._start_process([_FFMPEG, '-y', '-i', input_file, '-vf', subtitle_filter, '-vcodec', 'libx264', '-acodec', 'aac', output_file])
                else:
                    self._emit_status(_("status_synth_soft_sub"))
                    # For soft subtitles, we just map the streams.
                    # Depending on the container and subtitle format, -c:s mov_text works for mp4.
                    proc = self._start_process([_FFMPEG, '-y', '-i', input_file, '-i', input_srt, '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text', output_file])

                proc.wait()
                self._cleanup_process(proc)
                self._emit_status(_("status_synth_done"))
            
        self.finished.emit()

    @error_handler
    def clip(self):
        self._stop_requested = False
        self._stop_event.clear()
        self.save_config()
        input_files = self.master.clip_files_list.toPlainText()
        clip_start = self.master.clip_start_time.text()
        clip_end = self.master.clip_end_time.text()
        if input_files:
            input_files = input_files.strip().split('\n')
            for idx, input_file in enumerate(input_files):
                if self._stop_requested:
                    break
                if not os.path.exists(input_file):
                    self._emit_status(_("status_file_not_exist", file=input_file))
                    self.finished.emit()

                self._emit_status(_("status_processing_file", file=input_file, idx=idx+1, total=len(input_files)))
                self._emit_status(_("status_clip_processing", start=clip_start, end=clip_end))
                proc = self._start_process([_FFMPEG, '-y', '-i', input_file, '-ss', clip_start, '-to', clip_end, '-vcodec', 'libx264', '-acodec', 'aac', os.path.join(*(input_file.split('.')[:-1]))+'_clip.'+input_file.split('.')[-1]])
                proc.wait()
                self._cleanup_process(proc)
                self._emit_status(_("status_clip_done"))
        self.finished.emit()

    @error_handler
    def audiosynth(self):
        self._stop_requested = False
        self._stop_event.clear()
        self.save_config()
        input_files = self.master.synth_audio_files_list.toPlainText()
        if input_files:
            input_files = input_files.strip().split('\n')
            audio_files = sorted([i for i in input_files if i.endswith('.wav') or i.endswith('.mp3') or i.endswith('.flac')])
            image_files = sorted([i for i in input_files if i.endswith('.png') or i.endswith('.jpg') or i.endswith('.jpeg')])
            if len(audio_files) != len(image_files):
                self._emit_status(_("status_audio_mismatch"))
                self.finished.emit()
            
            for idx, (audio_input, image_input) in enumerate(zip(audio_files, image_files)):
                if self._stop_requested:
                    break
                if not os.path.exists(audio_input):
                    self._emit_status(_("status_file_not_exist", file=audio_input))
                    self.finished.emit()

                if not os.path.exists(image_input):
                    self._emit_status(_("status_file_not_exist", file=image_input))
                    self.finished.emit()

                self._emit_status(_("status_processing_file", file=audio_input, idx=idx+1, total=len(image_files)))
                proc = self._start_process([_FFMPEG, '-y', '-loop', '1', '-r', '1', '-f', 'image2', '-i', image_input, '-i', audio_input, '-shortest', '-vcodec', 'libx264', '-acodec', 'aac', audio_input+'_synth.mp4'], label='ffmpeg')
                proc.wait()
                self._cleanup_process(proc)
                self._emit_status(_("status_synth_done"))
            
        self.finished.emit()

    def _process_single_audio(
        self, wav_file, asr_model_file, aligner_file, asr_backend, language,
        param_crispasr, json_path, start_named_proc, stop_named_proc,
    ):
        """使用 CrispASR + forced aligner 处理单个音频文件。"""
        base_path = wav_file[:-4]  # 去掉 .wav
        intermediate_srt = base_path + '.srt'
        work_root = Path('project/cache/crispasr_jobs').resolve()
        work_root.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix='job_', dir=work_root))
        staged_input = work_dir / f'input{Path(wav_file).suffix.lower()}'
        output_base = work_dir / 'transcript'
        generated_srt = output_base.with_suffix('.srt')
        try:
            shutil.copyfile(wav_file, staged_input)
            command = _build_crispasr_command(
                staged_input, output_base, asr_model_file, language, param_crispasr,
                aligner_file=aligner_file, backend=asr_backend,
            )
            self.msg_queue.put("detail", _format_command(command))
            asr_proc, _unused = start_named_proc('crispasr', command)
            return_code = asr_proc.wait()
            stop_named_proc('crispasr')
            if return_code != 0:
                raise RuntimeError(f'CrispASR exited with code {return_code}')
            if not generated_srt.is_file() or generated_srt.stat().st_size == 0:
                raise RuntimeError('CrispASR did not produce a non-empty SRT file')
            shutil.copyfile(generated_srt, intermediate_srt)
            make_prompt(intermediate_srt, json_path)
        finally:
            stop_named_proc('crispasr')
            shutil.rmtree(work_dir, ignore_errors=True)
            # 单文件流程中的 16k SRT 只是中间产物。
            if intermediate_srt.endswith('.16k.srt') and os.path.exists(intermediate_srt):
                try:
                    os.remove(intermediate_srt)
                except Exception:
                    pass

    def _get_audio_duration(self, audio_file):
        """获取音频文件时长（秒）"""
        try:
            creationflags = 0x08000000 if os.name == 'nt' else 0
            result = subprocess.run(
                [_FFPROBE, '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1', audio_file],
                capture_output=True, text=True, timeout=30, creationflags=creationflags
            )
            return float(result.stdout.strip())
        except Exception as e:
            self._emit_status(_("status_audio_duration_fail", error=e))
            return 0

    def _split_audio(self, audio_file, segment_duration_minutes, output_dir):
        """将音频文件切分为多个片段，返回片段路径列表"""
        segment_files = []
        segment_duration = segment_duration_minutes * 60  # 转换为秒

        total_duration = self._get_audio_duration(audio_file)
        if total_duration == 0:
            return None, 0

        num_segments = int(total_duration // segment_duration) + (1 if total_duration % segment_duration > 1 else 0)
        base_name = os.path.basename(audio_file).rsplit('.', 1)[0]

        self._emit_status(_("status_audio_duration", duration=total_duration, segments=num_segments))

        for i in range(num_segments):
            start_time = i * segment_duration
            end_time = min((i + 1) * segment_duration, total_duration)
            duration = end_time - start_time

            segment_file = os.path.join(output_dir, f"segment_{i:04d}.16k.wav")

            try:
                creationflags = 0x08000000 if os.name == 'nt' else 0
                proc = subprocess.run(
                    [_FFMPEG, '-y', '-i', audio_file, '-ss', str(start_time),
                     '-t', str(duration), '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', segment_file],
                    capture_output=True, timeout=120, creationflags=creationflags
                )
                if proc.returncode == 0 and os.path.exists(segment_file):
                    segment_files.append(segment_file)
                else:
                    self._emit_status(_("status_segment_slice_fail", idx=i+1))
            except Exception as e:
                self._emit_status(_("status_segment_slice_fail_detail", idx=i+1, error=e))

        return segment_files, total_duration

    def _merge_segment_translations(self, segment_files, segment_tfs, original_base_path, output_json_path, final_output_dir, output_format, duration):
        """合并多个分段的翻译结果，调整时间戳并生成最终字幕文件"""
        from prompt2srt import make_srt, make_lrc, merge_lrc_files
        from srt2prompt import merge_srt_files
        import glob as glob_module

        all_data = []
        time_offset = 0
        segment_srts_orig = []
        segment_srts_zh = []
        segment_lrcs_orig = []
        segment_lrcs_zh = []

        base_name = os.path.basename(original_base_path)

        for i, segment_file in enumerate(segment_files):
            segment_name = os.path.basename(segment_file[:-4])  # 去掉 .wav，保留 .16k
            segment_dir = os.path.dirname(segment_file)

            # 收集分段的字幕文件（用于双语合并）
            if output_format in ('原文SRT', '双语SRT'):
                orig_srt = os.path.join(segment_dir, segment_name + '.srt')
                if os.path.exists(orig_srt):
                    segment_srts_orig.append(orig_srt)

            if output_format in ('目标SRT', '双语SRT'):
                zh_srt = os.path.join(segment_dir, segment_name + '.tg.srt')
                if os.path.exists(zh_srt):
                    segment_srts_zh.append(zh_srt)

            if output_format in ('原文LRC', '双语LRC'):
                orig_lrc = os.path.join(segment_dir, segment_name + '.lrc')
                if os.path.exists(orig_lrc):
                    segment_lrcs_orig.append(orig_lrc)

            if output_format in ('目标LRC', '双语LRC'):
                zh_lrc = os.path.join(segment_dir, segment_name + '.zh.lrc')
                if os.path.exists(zh_lrc):
                    segment_lrcs_zh.append(zh_lrc)

        # 生成最终的合并字幕文件
        if output_format in ('原文SRT', '双语SRT'):
            final_srt = os.path.join(final_output_dir, base_name + '.srt')
            merge_srt_files(segment_srts_orig, final_srt, duration)

        if output_format in ('目标SRT', '双语SRT'):
            final_zh_srt = os.path.join(final_output_dir, base_name + '.tg.srt')
            merge_srt_files(segment_srts_zh, final_zh_srt, duration)

        if output_format == '双语SRT':
            final_combine_srt = os.path.join(final_output_dir, base_name + '.combine.srt')
            left = os.path.join(final_output_dir, base_name + '.srt')
            right = os.path.join(final_output_dir, base_name + '.tg.srt')
            if os.path.exists(left) and os.path.exists(right):
                merge_srt_files([left, right], final_combine_srt)

        if output_format in ('原文LRC', '双语LRC'):
            final_lrc = os.path.join(final_output_dir, base_name + '.lrc')
            if output_format == '双语LRC':
                final_lrc = os.path.join(final_output_dir, base_name + '.orig.lrc')
            merge_lrc_files(segment_lrcs_orig, final_lrc, duration)

        if output_format in ('目标LRC', '双语LRC'):
            final_zh_lrc = os.path.join(final_output_dir, base_name + '.zh.lrc')
            merge_lrc_files(segment_lrcs_zh, final_zh_lrc, duration)

        if output_format == '双语LRC':
            final_combine_lrc = os.path.join(final_output_dir, base_name + '.combine.lrc')
            left = os.path.join(final_output_dir, base_name + '.orig.lrc')
            right = os.path.join(final_output_dir, base_name + '.zh.lrc')
            if os.path.exists(left) and os.path.exists(right):
                merge_lrc_files([left, right], final_combine_lrc)

        return all_data

    @error_handler
    def run(self):
        # Reset stop event for new run
        self._stop_requested = False
        self._stop_event.clear()
        
        self.save_config()
        input_files = self.master.input_files_list.toPlainText()
        asr_model_file = self.master.asr_model_file.currentText()
        aligner_file = self.master.aligner_file.currentText()
        asr_backend = self.master.asr_backend.currentText()
        translator = self.master.selected_translator()
        language = self.master.transcription_lang.currentData() or 'ja'
        sakura_file = self.master.sakura_file.currentText()
        sakura_mode = self.master.sakura_mode.text()
        proxy_address = self.master.proxy_address.text()
        before_dict = self.master.before_dict.toPlainText()
        gpt_dict = self.master.gpt_dict.toPlainText()
        after_dict = self.master.after_dict.toPlainText()
        param_crispasr = self.master.param_crispasr.toPlainText()
        param_llama = self.master.param_llama.toPlainText()
        selected_output_format = self.master.selected_output_format()
        output_dir = self.master.output_dir_edit.text().strip() or self.master.default_output_dir()
        use_input_dir = self.master.use_input_dir_checkbox.isChecked()
        enable_segment = self.master.enable_segment_checkbox.isChecked()
        segment_duration_minutes = self.master.segment_duration_spin.value() if enable_segment else 0
        enable_transcription = self.master.enable_transcription_checkbox.isChecked()
        need_translate = self.master.enable_translation_checkbox.isChecked()
        output_content, output_type = _split_output_format(selected_output_format)
        output_format = _compose_output_format(output_content, output_type, need_translate)

        with open('crispasr/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_crispasr)

        with open('llama/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_llama)

        self._emit_status(_("status_init_project"))
        if use_input_dir:
            self._emit_status(_("status_use_input_dir"))
        else:
            self._emit_status(_("status_output_dir", dir=output_dir))

        os.makedirs('project/cache', exist_ok=True)
        if before_dict:
            with open('project/dict_pre.txt', 'w', encoding='utf-8') as f:
                f.write(before_dict.replace(' ','\t'))
        else:
            if os.path.exists('project/dict_pre.txt'):
                os.remove('project/dict_pre.txt')
        if gpt_dict:
            with open('project/dict_gpt.txt', 'w', encoding='utf-8') as f:
                f.write(gpt_dict.replace(' ','\t'))
        else:
            if os.path.exists('project/dict_gpt.txt'):
                os.remove('project/dict_gpt.txt')
        if after_dict:
            with open('project/dict_after.txt', 'w', encoding='utf-8') as f:
                f.write(after_dict.replace(' ','\t'))
        else:
            if os.path.exists('project/dict_after.txt'):
                os.remove('project/dict_after.txt')

        self._emit_status(_("status_current_input", files=input_files))

        if input_files:
            input_files = input_files.split('\n')
        else:
            input_files = []

        os.makedirs('project/cache', exist_ok=True)

        target_lang = self.master.target_lang.currentData() if hasattr(self.master, 'target_lang') else 'zh-cn'
        if need_translate:
            # 仅在本次任务需要翻译时刷新翻译配置。
            self.update_translation_config()
        else:
            self._emit_status(_("status_no_translator_skip"))
        if not enable_transcription:
            self._emit_status(_("status_no_transcribe_skip"))

        engine = 'ForGal-json'
        if need_translate and 'sakura' in translator:
            engine = 'sakura-v1.0'

        running_procs = {}
        proc_lock = threading.Lock()

        def start_named_proc(proc_name, args):
            with proc_lock:
                existing = running_procs.get(proc_name)
                if existing and existing.poll() is None:
                    self._emit_status(_("status_duplicate_proc", name=proc_name))
                    return existing, True
                if existing:
                    self._cleanup_process(existing)
                    running_procs.pop(proc_name, None)

                new_proc = self._start_process(args, label=proc_name)
                running_procs[proc_name] = new_proc
                return new_proc, False

        def stop_named_proc(proc_name):
            with proc_lock:
                target = running_procs.pop(proc_name, None)
                if target:
                    self._cleanup_process(target)

        # 流水线流程：听写线程 + 翻译线程并行
        transcribed_dir = os.path.join('project', 'cache', 'transcribed')
        os.makedirs(transcribed_dir, exist_ok=True)
        # 创建并发翻译线程池
        max_concurrent = self.master.max_concurrent_spin.value()

        # 本地模型配置
        local_model_config = None
        if 'sakura' in translator or 'llamacpp' in translator:
            local_model_config = {
                'sakura_file': sakura_file,
                'sakura_mode': sakura_mode,
                'param_llama': param_llama,
            }

        # 同步详细日志模式设置到翻译线程池
        ConcurrentTranslationPool.verbose_galtransl = self.master.verbose_checkbox.isChecked()

        self._translation_pool = None
        if need_translate:
            self._translation_pool = ConcurrentTranslationPool(
                project_dir='project',
                base_config_path='project/config.yaml',
                max_concurrent=max_concurrent,
                stop_event=self._stop_event,
                msg_queue=self.msg_queue,
                local_model_config=local_model_config,
            )
            self._translation_pool.start(engine)

        # 主线程：顺序执行下载+听写，产出放入队列
        for idx, input_file in enumerate(input_files):
            if self._stop_event.is_set():
                break
            if not os.path.exists(input_file):
                if input_file.startswith('BV'):
                    self._emit_status(_("status_downloading_video"))
                    res = send_request(URL_VIDEO_INFO, params={'bvid': input_file})
                    download([Video(
                        bvid=res['bvid'],
                        cid=res['cid'] if res['videos'] == 1 else res['pages'][0]['cid'],
                        title=res['title'] if res['videos'] == 1 else res['pages'][0]['part'],
                        up_name=res['owner']['name'],
                        cover_url=res['pic'] if res['videos'] == 1 else res['pages'][0]['pic'],
                    )], False)
                    self._emit_status(_("status_download_complete"))
                    title = res['title'] if res['videos'] == 1 else res['pages'][0]['part']
                    title = re.sub(r'[.:?/\\]', ' ', title).strip()
                    title = re.sub(r'\s+', ' ', title)
                    downloaded_file = os.path.abspath(f"{title}.mp4")
                    target_file = os.path.join(output_dir, os.path.basename(downloaded_file))
                    if os.path.exists(downloaded_file):
                        if os.path.exists(target_file):
                            os.remove(target_file)
                        input_file = shutil.move(downloaded_file, target_file)
                    else:
                        self._emit_status(_("status_download_not_found", file=downloaded_file))
                        self._stop_event.set()
                        break

                else:
                    ydl_outtmpl = os.path.join(output_dir, 'YoutubeDL_%(title)s_%(id)s.%(ext)s')
                    if proxy_address:
                        ydl_ctx = YoutubeDL({'proxy': proxy_address, 'outtmpl': ydl_outtmpl})
                    else:
                        ydl_ctx = YoutubeDL({'outtmpl': ydl_outtmpl})

                    with ydl_ctx as ydl:
                        self._emit_status(_("status_downloading_video"))
                        info = ydl.extract_info(input_file, download=True)
                        self._emit_status(_("status_download_complete"))
                        input_file = ydl.prepare_filename(info)
                        requested_downloads = info.get('requested_downloads') if isinstance(info, dict) else None
                        if requested_downloads and isinstance(requested_downloads[0], dict):
                            actual_file = requested_downloads[0].get('filepath')
                            if actual_file:
                                input_file = actual_file
                        if isinstance(info, dict) and info.get('_filename') and os.path.exists(info.get('_filename')):
                            input_file = info.get('_filename')

                    input_file = os.path.abspath(str(input_file or ''))
                    if not os.path.exists(input_file):
                        self._emit_status(_("status_download_not_found", file=input_file))
                        self._stop_event.set()
                        break

            self._emit_status(_("status_processing_file", file=input_file, idx=idx+1, total=len(input_files)))
            current_output_dir = output_dir
            if use_input_dir:
                current_output_dir = os.path.dirname(os.path.abspath(input_file)) or output_dir
                self._emit_status(_("status_file_output_dir", dir=current_output_dir))

            tf: TranscribedFile | None = None

            if input_file.endswith('.srt'):
                # —— SRT 输入：直接转换 ——
                self._emit_status(_("status_srt_converting"))
                json_path = os.path.join(transcribed_dir, os.path.basename(input_file).replace('.srt', '.json'))
                make_prompt(input_file, json_path)
                self._emit_status(_("status_srt_convert_done"))
                # 复制原始 SRT 到输出目录（供双语合并用）
                try:
                    orig_srt_src = os.path.abspath(input_file)
                    orig_srt_dst = os.path.join(current_output_dir, os.path.basename(orig_srt_src))
                    if os.path.exists(orig_srt_src):
                        shutil.copy(orig_srt_src, orig_srt_dst)
                except Exception:
                    pass
                # 原文 LRC（双语 LRC 需要）
                if output_format in ('原文LRC', '双语LRC'):
                    lrc_suffix = '.orig.lrc' if output_format == '双语LRC' else '.lrc'
                    lrc_output = os.path.join(current_output_dir, os.path.basename(input_file[:-4] + lrc_suffix))
                    make_lrc(json_path, lrc_output)
                base_path = input_file[:-4]  # 去掉 .srt
                tf = TranscribedFile(
                    base_path=base_path,
                    json_src=json_path,
                    output_dir=current_output_dir,
                    output_format=output_format,
                    orig_srt_path=os.path.abspath(input_file),
                )
            else:
                # 音视频输入：提取音频 → 听写（如果已有srt则跳过）
                if not enable_transcription:
                    continue

                base_path = input_file.rsplit('.', 1)[0] if '.' in input_file else input_file
                existing_srt = base_path + '.srt'
                wav_file = base_path + '.16k.wav'
                json_path = os.path.join(transcribed_dir, os.path.basename(base_path) + '.json')

                # 检测是否已有srt文件
                if os.path.exists(existing_srt):
                    self._emit_status(_("status_existing_srt_found", file=existing_srt))
                    make_prompt(existing_srt, json_path)

                    # 生成原文 SRT/LRC 输出（与正常听写流程一致）
                    if output_format == '原文SRT' or output_format == '双语SRT':
                        srt_output = os.path.join(current_output_dir, os.path.basename(base_path + '.srt'))
                        if not os.path.exists(srt_output):
                            make_srt(json_path, srt_output)

                    if output_format == '原文LRC' or output_format == '双语LRC':
                        lrc_name = os.path.basename(base_path + '.lrc')
                        if output_format == '双语LRC':
                            lrc_name = os.path.basename(base_path + '.orig.lrc')
                        lrc_output = os.path.join(current_output_dir, lrc_name)
                        if not os.path.exists(lrc_output):
                            make_lrc(json_path, lrc_output)

                    self._emit_status(_("status_asr_done_cached"))

                    if need_translate:
                        self._emit_status(_("status_submitting_translation"))
                        tf = TranscribedFile(
                            base_path=base_path,
                            json_src=json_path,
                            output_dir=current_output_dir,
                            output_format=output_format,
                            orig_srt_path='',
                        )
                        self._translation_pool.submit(tf)
                        continue

                self._emit_status(_("status_extracting_audio"))
                ffmpeg_proc, _unused = start_named_proc(
                    'ffmpeg_extract',
                    [_FFMPEG, '-y', '-i', input_file, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', wav_file]
                )
                ffmpeg_proc.wait()
                stop_named_proc('ffmpeg_extract')

                if not os.path.exists(wav_file):
                    self._emit_status(_("status_audio_extract_error"))
                    break

                # 检查是否启用分段处理
                base_path = wav_file[:-8]  # 去掉 .16k.wav
                json_path = os.path.join(transcribed_dir, os.path.basename(base_path) + '.json')

                total_duration = self._get_audio_duration(wav_file)
                threshold_seconds = segment_duration_minutes * 60

                if enable_segment and segment_duration_minutes > 0 and total_duration > threshold_seconds:
                    # 需要分段处理
                    self._emit_status(_("status_segment_threshold", duration=total_duration, threshold=threshold_seconds))

                    segment_dir = os.path.join('project', 'cache', 'segments', os.path.basename(base_path))
                    os.makedirs(segment_dir, exist_ok=True)

                    # 切分音频
                    segment_files, _unused = self._split_audio(wav_file, segment_duration_minutes, segment_dir)

                    if not segment_files:
                        self._emit_status(_("status_segment_fail"))
                        if os.path.exists(wav_file):
                            os.remove(wav_file)
                        break

                    # 对每个片段进行听写和翻译
                    segment_tfs = []  # 存储每个分段的 TranscribedFile
                    for i, segment_file in enumerate(segment_files):
                        if self._stop_event.is_set():
                            break
                        self._emit_status(_("status_segment_processing", idx=i+1, total=len(segment_files)))

                        segment_base = segment_file[:-4] # 去掉 .wav
                        segment_name = os.path.basename(segment_base)

                        segment_json = os.path.join(transcribed_dir, segment_name + '.json')
                        self._process_single_audio(
                            segment_file,
                            asr_model_file,
                            aligner_file,
                            asr_backend,
                            language,
                            param_crispasr,
                            segment_json,
                            start_named_proc,
                            stop_named_proc,
                        )

                        # 立即提交该分段进行翻译
                        if need_translate:
                            self._emit_status(_("status_segment_submit_translate", idx=i+1, total=len(segment_files)))
                            segment_tf = TranscribedFile(
                                base_path=segment_base,
                                json_src=segment_json,
                                output_dir=segment_dir,  # 临时输出到分段目录
                                output_format=output_format,
                                orig_srt_path='',
                            )
                            self._translation_pool.submit(segment_tf)
                            segment_tfs.append(segment_tf)

                    # 等待所有分段翻译完成
                    if need_translate and segment_tfs:
                        self._emit_status(_("status_wait_segments"))
                        self._translation_pool.done()
                        self._translation_pool.wait_all(timeout=600)

                    # 合并所有片段的翻译结果
                    self._emit_status(_("status_merge_segments"))
                    self._merge_segment_translations(segment_files, segment_tfs, base_path, json_path, current_output_dir, output_format, threshold_seconds)

                    self._emit_status(_("status_segment_done"))

                    # 分段处理已完成，跳过常规流程
                    tf = None
                else:
                    # 正常流程（未启用分段）
                    self._emit_status(_("status_asr_in_progress"))
                    self._process_single_audio(
                        wav_file,
                        asr_model_file,
                        aligner_file,
                        asr_backend,
                        language,
                        param_crispasr,
                        json_path,
                        start_named_proc,
                        stop_named_proc,
                    )

                    # 生成原文 SRT/LRC 输出
                    if output_format == '原文SRT' or output_format == '双语SRT':
                        srt_output = os.path.join(current_output_dir, os.path.basename(base_path + '.srt'))
                        make_srt(json_path, srt_output)

                    if output_format == '原文LRC' or output_format == '双语LRC':
                        lrc_name = os.path.basename(base_path + '.lrc')
                        if output_format == '双语LRC':
                            lrc_name = os.path.basename(base_path + '.orig.lrc')
                        lrc_output = os.path.join(current_output_dir, lrc_name)
                        make_lrc(json_path, lrc_output)

                    # 清理临时文件
                    if os.path.exists(wav_file):
                        os.remove(wav_file)

                    self._emit_status(_("status_asr_done"))

                    tf = TranscribedFile(
                        base_path=base_path,
                        json_src=json_path,
                        output_dir=current_output_dir,
                        output_format=output_format,
                        orig_srt_path='',
                    )

            if need_translate and tf is not None:
                self._translation_pool.submit(tf)

        # 发送哨兵，等待翻译线程结束
        self._emit_status(_("status_all_transcribed"))
        if self._translation_pool is not None:
            self._translation_pool.done()
            self._translation_pool.wait_all(timeout=600)
            self._translation_pool.stop()

            err_count = self._translation_pool.error_count
            if err_count > 0:
                self._emit_status(_("status_translate_fail_count", count=err_count))

        # 完成屏障：先排空消息队列，再放入完成哨兵
        # 确保所有翻译日志在"所有文件处理完成"之前被 GUI 消费
        self.msg_queue.drain_all(timeout=3.0)
        self.msg_queue.put_completion_sentinel()
        self.msg_queue.set_completion_flag()
        self.finished.emit()

if __name__ == "__main__":
    os.makedirs('project/cache', exist_ok=True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
