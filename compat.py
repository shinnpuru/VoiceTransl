import os
import shutil
from pathlib import Path


def migrate_config_txt(config_path: str = 'config.txt') -> dict:
    """从旧 config.txt 迁移到 gui_settings.yaml 格式

    config.txt 行结构（按行号）:
        0: whisper_file     1: translator    2: language
        3: gpt_token        4: gpt_address   5: gpt_model
        6: sakura_file      7: sakura_mode   8: proxy_address
        9: uvr_file        10: output_format 11: subtitle_font
       12: output_dir      13: use_input_dir 14: max_concurrent
       15: enable_segment  16: segment_duration 17: change_prompt_mode

    Returns:
        gui_settings 字典（与 gui_settings.yaml 结构一致）
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # API Key 写入 .env（与旧版行为一致）
    gpt_token = lines[3].strip() if len(lines) > 3 else ''
    _save_api_key(gpt_token)

    return {
        'whisper_file': lines[0].strip(),
        'translator': lines[1].strip(),
        'language': lines[2].strip(),
        'gpt_address': lines[4].strip(),
        'gpt_model': lines[5].strip(),
        'sakura_file': lines[6].strip(),
        'sakura_mode': lines[7].strip(),
        'proxy_address': lines[8].strip(),
        'uvr_file': lines[9].strip(),
        'output_format': lines[10].strip(),
        'subtitle_font': lines[11].strip() if len(lines) > 11 else "",
        'output_dir': lines[12].strip() if len(lines) > 12 else '',
        'use_input_dir': (lines[13].strip().lower() == 'true') if len(lines) > 13 else False,
        'max_concurrent': int(lines[14].strip()) if len(lines) > 14 else 1,
        'enable_segment': (lines[15].strip().lower() == 'true') if len(lines) > 15 else False,
        'segment_duration': int(lines[16].strip()) if len(lines) > 16 else 10,
        'change_prompt_mode': lines[17].strip() if len(lines) > 17 else '不修改',
    }


def migrate_old_whisper_models(
    old_whisper_file: str,
    log_fn=None,
) -> dict:
    """将旧版 whisper/whisper-faster 模型迁移到 models/transcribe/，并清理旧目录

    迁移规则:
    - whisper-faster/faster-whisper-* 目录 → models/transcribe/（CTranslate2 格式，兼容）
    - whisper/ggml-*.bin → 跳过并警告（whisper.cpp ggml 格式，与 ASRLabs stable-ts 后端不兼容）
    - whisper/ggml-silero-*.bin → 跳过（VAD 模型，ASRLabs 内置 Silero VAD）
    - 迁移完成后删除 whisper/ 和 whisper-faster/ 目录

    Args:
        old_whisper_file: 旧配置中的 whisper_file 值（如 "faster-whisper-large-v3"）
        log_fn: 日志回调函数，签名为 log_fn(str)；为 None 时静默

    Returns:
        {'asr_engine': str, 'asr_model': str}
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    result = {'asr_engine': '', 'asr_model': ''}
    transcribe_dir = Path('models/transcribe')
    transcribe_dir.mkdir(parents=True, exist_ok=True)

    # 1. 迁移 whisper-faster/ 下的 faster-whisper-* 模型目录
    faster_dir = Path('whisper-faster')
    if faster_dir.exists():
        for item in faster_dir.iterdir():
            if item.is_dir() and item.name.startswith('faster-whisper'):
                target = transcribe_dir / item.name
                if not target.exists():
                    try:
                        shutil.move(str(item), str(target))
                        _log(f"[INFO] 模型迁移: {item.name} -> models/transcribe/")
                    except Exception as e:
                        _log(f"[WARN] 模型迁移失败: {item.name}: {e}")

    # 2. 检测 whisper/ 下的 ggml 模型（不兼容，跳过）
    whisper_dir = Path('whisper')
    if whisper_dir.exists():
        ggml_models = [m for m in whisper_dir.glob('ggml-*.bin') if 'silero' not in m.name]
        if ggml_models:
            names = ", ".join(m.name for m in ggml_models)
            _log(f"[WARN] ggml 格式模型（{names}）与 ASRLabs 不兼容，已跳过。"
                 f"请在 models/transcribe/ 中放置 stable-ts 或 HuggingFace 格式的 Whisper 模型。")

    # 3. 根据旧配置映射到新引擎
    mapped = map_whisper_to_asr(old_whisper_file)
    result['asr_engine'] = mapped['asr_engine']
    result['asr_model'] = mapped['asr_model']
    # 如果模型目录已迁移到 models/transcribe/，修正路径
    if result['asr_model'] and result['asr_engine'] == 'faster-whisper':
        model_name = os.path.basename(result['asr_model'])
        migrated_path = str(transcribe_dir / model_name)
        if os.path.exists(migrated_path):
            result['asr_model'] = migrated_path

    # 4. 删除旧目录
    for old_dir in [Path('whisper'), Path('whisper-faster')]:
        if old_dir.exists():
            try:
                shutil.rmtree(old_dir)
                _log(f"[INFO] 已清理旧目录: {old_dir}/")
            except Exception as e:
                _log(f"[WARN] 清理旧目录失败 {old_dir}/: {e}")

    return result


def migrate_output_format(old_fmt: str) -> str:
    """旧格式名 → 新格式名映射

    '中文SRT' → '目标SRT'
    '中文LRC' → '目标LRC'
    其余值原样返回
    """
    _FORMAT_MIGRATION = {'中文SRT': '目标SRT', '中文LRC': '目标LRC'}
    return _FORMAT_MIGRATION.get(old_fmt, old_fmt)


def map_whisper_to_asr(old_whisper_file: str) -> dict:
    """将旧 whisper_file 字符串映射为 ASRLabs 引擎配置

    Args:
        old_whisper_file: 旧配置值，如 "faster-whisper-large-v3" 或 "ggml-medium.bin"

    Returns:
        {'asr_engine': str, 'asr_model': str}
        - faster-whisper-* → asr_engine='faster-whisper', asr_model=旧完整路径
        - ggml-*           → asr_engine='whisper',         asr_model=''（格式不兼容，留空）
        - 其他/空           → 均为空串
    """
    if old_whisper_file.startswith('faster-whisper'):
        return {
            'asr_engine': 'faster-whisper',
            'asr_model': os.path.join('whisper-faster', old_whisper_file),
        }
    elif old_whisper_file.startswith('ggml'):
        return {
            'asr_engine': 'whisper',
            'asr_model': '',  # ggml 不兼容，留空让用户自行配置
        }
    return {'asr_engine': '', 'asr_model': ''}


def _save_api_key(api_key: str) -> None:
    """将 API Key 写入 .env 文件（与 app.py 中的逻辑一致）"""
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(f'VOICETRANSL_API_KEY={api_key}\n')
