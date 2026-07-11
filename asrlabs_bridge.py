"""ASRLabs CLI 适配层

封装 asrlabs transcribe / align / list 命令的子进程调用，
提供引擎元数据同步、听写+对齐流程编排、JSON 格式转换等功能。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# PyInstaller 打包后使用独立 exe，源码运行时使用 python -m asrlabs
_FROZEN = hasattr(sys, '_MEIPASS')
_ASRLABS_CMD = ['asrlabs/asrlabs'] if _FROZEN else [sys.executable, '-m', 'asrlabs']

# 引擎元数据缓存（避免每次调用都启动子进程）
_transcriber_cache: list[dict] | None = None
_aligner_cache: list[dict] | None = None


def _run_asrlabs_json(args: list[str], timeout: int = 30) -> str:
    """运行 asrlabs 命令并返回 stdout 字符串

    Args:
        args: asrlabs 子命令及参数列表
        timeout: 超时秒数

    Returns:
        stdout 输出文本
    """
    creationflags = 0x08000000 if os.name == 'nt' else 0
    proc = subprocess.run(
        [*_ASRLABS_CMD, *args],
        capture_output=True, text=True,
        timeout=timeout, creationflags=creationflags,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"asrlabs 命令失败 (exit={proc.returncode}): {proc.stderr}")
    return proc.stdout


def fetch_engine_metadata(force_refresh: bool = False) -> tuple[list[dict], list[dict]]:
    """从 asrlabs list --json 获取引擎元数据

    首次调用后缓存结果，后续调用直接返回缓存。

    Args:
        force_refresh: True 时强制重新获取

    Returns:
        (transcribers, aligners) 元组
        transcribers: [{"name", "display_name", "supports_timestamps",
                         "recommended_aligner", "supported_devices", "supports_initial_prompt"}, ...]
        aligners: [{"name", "display_name"}, ...]
    """
    global _transcriber_cache, _aligner_cache

    if _transcriber_cache is None or force_refresh:
        raw = _run_asrlabs_json(['list', 'transcribers', '--json'])
        _transcriber_cache = json.loads(raw)

    if _aligner_cache is None or force_refresh:
        raw = _run_asrlabs_json(['list', 'aligners', '--json'])
        _aligner_cache = json.loads(raw)

    return _transcriber_cache, _aligner_cache


def get_transcriber_meta(engine_name: str) -> dict | None:
    """获取指定听写引擎的元数据

    Args:
        engine_name: 引擎名，如 "faster-whisper"

    Returns:
        元数据字典，找不到返回 None
    """
    transcribers, _ = fetch_engine_metadata()
    for t in transcribers:
        if t['name'] == engine_name:
            return t
    return None


def list_transcribe_models() -> list[str]:
    """扫描 models/transcribe/ 目录，返回可用模型文件夹列表

    Returns:
        模型文件夹名列表，如 ["faster-whisper-large-v3", "Qwen3-ASR-1.7B"]
    """
    models_dir = Path('models/transcribe')
    if not models_dir.exists():
        return []
    return sorted([
        d.name for d in models_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ])


def list_align_models() -> list[str]:
    """扫描 models/align/ 目录，返回可用模型文件夹列表

    Returns:
        模型文件夹名列表
    """
    models_dir = Path('models/align')
    if not models_dir.exists():
        return []
    return sorted([
        d.name for d in models_dir.iterdir()
        if d.is_dir() and not d.name.startswith('.')
    ])


def transcribe(
    audio_path: str,
    engine: str,
    model_path: str,
    language: str,
    device: str,
    compute_type: str,
    output_dir: str,
    output_name: str,
    extra_args: str,
    msg_queue,
    stop_event,
) -> str:
    """调用 asrlabs transcribe，返回输出的 JSON 文件路径

    Args:
        audio_path: 音频文件路径
        engine: 引擎名（如 "faster-whisper"）
        model_path: 模型路径（本地路径或 HF ID，空串使用引擎默认）
        language: 语言代码（ISO 639-1，如 "ja"）
        device: 设备类型（"auto"/"cuda"/"cpu"/"vulkan"）
        compute_type: 计算精度（"float16"/"int8"/"float32"）
        output_dir: 输出目录
        output_name: 输出文件名 stem（不含扩展名）
        extra_args: 额外命令行参数（空格分隔的字符串）
        msg_queue: UIMessageQueue 实例，用于日志转发
        stop_event: threading.Event，用于取消检测

    Returns:
        输出的 JSON 文件路径
    """
    cmd = [*_ASRLABS_CMD, 'transcribe', audio_path,
           '-m', engine,
           '-l', language,
           '--device', device,
           '--compute-type', compute_type,
           '-d', output_dir,
           '-o', output_name]

    if model_path:
        cmd.extend(['--model-path', model_path])

    if extra_args.strip():
        cmd.extend(extra_args.split())

    return _run_with_log(cmd, msg_queue, stop_event, output_dir, output_name)


def align(
    audio_path: str,
    transcribe_json_path: str,
    aligner: str,
    model_path: str,
    device: str,
    output_dir: str,
    output_name: str,
    extra_args: str,
    msg_queue,
    stop_event,
) -> str:
    """调用 asrlabs align，返回对齐后的 JSON 文件路径

    Args:
        audio_path: 音频文件路径
        transcribe_json_path: 听写产出的 JSON 路径
        aligner: 对齐器名称（如 "qwen3_align"）
        model_path: 对齐模型路径（空串使用默认）
        device: 设备类型
        output_dir: 输出目录
        output_name: 输出文件名 stem（与听写相同则覆盖）
        extra_args: 额外命令行参数
        msg_queue: UIMessageQueue 实例
        stop_event: threading.Event

    Returns:
        对齐后的 JSON 文件路径
    """
    cmd = [*_ASRLABS_CMD, 'align', audio_path, transcribe_json_path,
           '--aligner', aligner,
           '--device', device,
           '-d', output_dir,
           '-o', output_name]

    if model_path:
        cmd.extend(['--model-path', model_path])

    if extra_args.strip():
        cmd.extend(extra_args.split())

    return _run_with_log(cmd, msg_queue, stop_event, output_dir, output_name)


def _run_with_log(cmd, msg_queue, stop_event, output_dir, output_name) -> str:
    """运行 asrlabs 子进程，转发日志到 msg_queue，返回 JSON 路径

    主要逻辑：
    1. subprocess.Popen 启动子进程
    2. 逐行读取 stdout/stderr，转发到 UIMessageQueue
    3. 检测 stop_event，提前终止子进程
    4. 等待子进程结束，校验返回码
    5. 返回 <output_dir>/<output_name>.json 路径
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    creationflags = 0x08000000 if os.name == 'nt' else 0
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, creationflags=creationflags, bufsize=1,
    )

    # 逐行读取输出并转发到消息队列
    for line in iter(proc.stdout.readline, ''):
        if stop_event.is_set():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
            break

        cleaned = line.rstrip('\n\r')
        if cleaned.strip():
            msg_queue.put("detail", f"[ASRLabs] {cleaned}")

    proc.stdout.close()
    retcode = proc.wait()

    if retcode != 0:
        raise RuntimeError(f"asrlabs 子进程失败 (exit={retcode})")

    json_path = os.path.join(output_dir, output_name + '.json')
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"asrlabs 未生成预期输出文件: {json_path}")

    return json_path


def convert_to_galtransl_json(asrlabs_json_path: str, output_path: str):
    """将 ASRLabs JSON 转为 GalTransl JSON 格式

    ASRLabs 格式:
        {"text": "...", "segments": [{"text": "...", "start": 0.5, "end": 2.3, ...}], ...}

    GalTransl 格式:
        [{"start": 0.5, "end": 2.3, "message": "..."}, ...]

    Args:
        asrlabs_json_path: ASRLabs 产出的 JSON 文件路径
        output_path: 转换后的 GalTransl JSON 文件路径
    """
    with open(asrlabs_json_path, encoding='utf-8') as f:
        data = json.load(f)

    galtransl_data = []
    for seg in data.get('segments', []):
        text = seg.get('text', '').strip()
        if not text:
            continue
        galtransl_data.append({
            'start': seg.get('start', 0.0),
            'end': seg.get('end', 0.0),
            'message': text,
        })

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(galtransl_data, f, ensure_ascii=False, indent=4)


def run_transcribe_and_align(
    audio_path: str,
    engine: str,
    model_path: str,
    language: str,
    device: str,
    compute_type: str,
    aligner: str,
    align_model_path: str,
    align_device: str,
    transcribe_extra: str,
    align_extra: str,
    output_dir: str,
    output_name: str,
    msg_queue,
    stop_event,
) -> str:
    """完整的听写+对齐流程，返回 GalTransl JSON 路径

    主要逻辑：
    1. 调用 asrlabs transcribe → 产出 ASRLabs JSON
    2. 如果 aligner 不为 "none" 且引擎无内置时间戳 → 调用 asrlabs align
       如果 aligner 不为 "none" 但引擎已有时间戳 → 仍可二次对齐（用户选择）
    3. 将最终 JSON 转为 GalTransl 格式

    Args:
        aligner: 对齐器名称，"none" 表示跳过对齐
        其余参数同 transcribe() / align()

    Returns:
        GalTransl 格式 JSON 文件路径
    """
    # 步骤 1：听写
    asrlabs_json = transcribe(
        audio_path, engine, model_path, language, device, compute_type,
        output_dir, output_name, transcribe_extra, msg_queue, stop_event,
    )

    # 步骤 2：对齐（可选）
    if aligner and aligner != 'none':
        asrlabs_json = align(
            audio_path, asrlabs_json, aligner, align_model_path,
            align_device, output_dir, output_name,
            align_extra, msg_queue, stop_event,
        )

    # 步骤 3：转为 GalTransl 格式
    galtransl_json = os.path.join(output_dir, output_name + '.galtransl.json')
    convert_to_galtransl_json(asrlabs_json, galtransl_json)

    return galtransl_json
