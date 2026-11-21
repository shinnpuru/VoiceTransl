"""Small headless adapters for the VoiceTransl CLI skill; no GUI imports.

Subtitle operations use only Python's standard library. Project setup uses the
bundled pure-Python PyYAML archive, with no installation. Only optional summary
and download features need extra packages. Native inference stays in EXEs.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys


def load_yaml_module():
    """Use the portable YAML dependency without pip, venv, or native extensions."""
    archive = Path(__file__).resolve().parent / 'vendor' / 'pyyaml.zip'
    if archive.is_file() and str(archive) not in sys.path:
        sys.path.insert(0, str(archive))
    import yaml
    return yaml


def read_text(path):
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("gb18030")


def validate(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Subtitle data must be a non-empty JSON array")
    for i, row in enumerate(rows, 1):
        start, end = row["start"], row["end"]
        if (isinstance(start, bool) or isinstance(end, bool)
                or not isinstance(start, (int, float))
                or not isinstance(end, (int, float))
                or not math.isfinite(start) or not math.isfinite(end)
                or start < 0 or end < start
                or not isinstance(row["message"], str)):
            raise ValueError(f"Invalid subtitle cue {i}")
    return rows


def load_rows(path):
    return validate(json.loads(read_text(path)))


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, rows):
    write_text(path, json.dumps(validate(rows), ensure_ascii=False, indent=2) + "\n")


def srt_to_json(source, target):
    text = read_text(source).replace("\r\n", "\n").replace("\r", "\n").strip()
    stamp = r"(\d+):(\d{2}):(\d{2})[,.](\d{3})"
    timing = re.compile(rf"^{stamp}\s*-->\s*{stamp}(?:\s+.*)?$")
    rows = []
    for block in re.split(r"\n[ \t]*\n", text):
        lines = block.splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        match = timing.fullmatch(lines[0].strip()) if lines else None
        if not match or len(lines) < 2:
            raise ValueError(f"Malformed SRT cue {len(rows) + 1}")
        nums = list(map(int, match.groups()))
        def seconds(values):
            h, m, s, ms = values
            if m >= 60 or s >= 60:
                raise ValueError("Invalid SRT timestamp")
            return ((h * 3600 + m * 60 + s) * 1000 + ms) / 1000
        rows.append(dict(start=seconds(nums[:4]), end=seconds(nums[4:]),
                         message="\n".join(lines[1:])))
    write_json(target, rows)


def timestamp(seconds, lrc=False):
    total_ms = round(seconds * 1000)
    total_s, ms = divmod(total_ms, 1000)
    if lrc:
        minutes, secs = divmod(total_s, 60)
        return f"{minutes:02}:{secs:02}.{ms:03}"
    minutes, secs = divmod(total_s, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


def export(args):
    rows = load_rows(args.input)
    if args.original:
        original = load_rows(args.original)
        if len(original) != len(rows) or any(
            abs(a[k] - b[k]) > .002
            for a, b in zip(original, rows) for k in ("start", "end")
        ):
            raise ValueError("Original and translated cue timelines differ")
        # Match app.py: separate original/target cues at the same timestamp.
        rows = [cue for pair in zip(original, rows) for cue in pair]
        rows.sort(key=lambda cue: cue["start"])
    if args.format == "srt":
        text = "".join(f"{i}\n{timestamp(r['start'])} --> {timestamp(r['end'])}\n"
                       f"{r['message']}\n\n" for i, r in enumerate(rows, 1))
    else:
        text = "".join(f"[{timestamp(r['start'], True)}] "
                       + r['message'].replace('\n', ' ') + "\n" for r in rows)
    write_text(args.output, text)


def merge(args):
    if len(args.inputs) != len(args.offsets):
        raise ValueError("Each segment needs its actual start offset in seconds")
    rows = []
    for path, offset in zip(args.inputs, args.offsets):
        if not math.isfinite(offset) or offset < 0:
            raise ValueError("Offsets must be finite and non-negative")
        for cue in load_rows(path):
            rows.append(dict(cue, start=cue['start'] + offset, end=cue['end'] + offset))
    rows.sort(key=lambda cue: cue['start'])
    write_json(args.output, rows)


def init_project(args):
    yaml = load_yaml_module()
    template = Path(args.template).resolve()
    project = Path(args.project).resolve()
    if (project / "config.yaml").exists():
        raise FileExistsError("Choose a new task directory; config.yaml already exists")
    cfg = yaml.safe_load(read_text(template))
    common = cfg.setdefault('common', {})
    common.update(language=args.language, saveLog=True)
    common['start_time'] = ''
    cfg.setdefault('plugin', {})['filePlugin'] = 'file_galtransl_json'
    if args.prompt_file:
        common['gpt.change_prompt'] = 'AdditionalPrompt'
        common['gpt.prompt_content'] = read_text(args.prompt_file)
    backend = cfg.setdefault('backendSpecific', {})
    endpoint = args.endpoint.rstrip('/')
    if endpoint.endswith('/v1'):
        endpoint = endpoint[:-3]
    if args.engine == 'sakura-v1.0':
        backend.setdefault('SakuraLLM', {}).update(
            endpoints=[endpoint], rewriteModelName=args.model)
    else:
        token = os.environ.get(args.token_env)
        if not token:
            raise ValueError(f"Set {args.token_env}; use a non-empty dummy key for local servers")
        backend.setdefault('OpenAI-Compatible', {}).update(
            tokens=[dict(token=token, endpoint=endpoint, modelName=args.model)],
            checkAvailable=True)
    for name in ('gt_input', 'gt_output', 'transl_cache'):
        (project / name).mkdir(parents=True, exist_ok=True)
    for item in template.parent.glob('*.txt'):
        if item.is_file():
            shutil.copyfile(item, project / item.name)
    dictionary = cfg.setdefault('dictionary', {})
    for key, filename in [('preDict', 'dict_pre.txt'), ('gpt.dict', 'dict_gpt.txt'),
                          ('postDict', 'dict_after.txt')]:
        entries = dictionary.setdefault(key, [])
        entry = '(project_dir)' + filename
        if entry not in entries:
            entries.append(entry)
        (project / filename).touch(exist_ok=True)
    # Resolve project-local entries to the task, preserving all other settings.
    text = yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)
    text = text.replace('(project_dir)', project.as_posix() + '/')
    write_text(project / 'config.yaml', text)
    print(f"Project prepared: {project}")


def summarize(args):
    yaml = load_yaml_module()
    from openai import OpenAI
    cfg = yaml.safe_load(read_text(args.config))
    entry = cfg['backendSpecific']['OpenAI-Compatible']['tokens'][0]
    address = entry['endpoint'].rstrip('/')
    if address.endswith('/chat/completions'):
        address = address[:-len('/chat/completions')]
    if not address.endswith('/v1'):
        address += '/v1'
    prompt = (read_text(args.prompt_file) if args.prompt_file else
              '请总结以下字幕的关键事件，不超过10项，保留 mm:ss 时间戳。')
    proxy = cfg.get('proxy', {})
    # Scope this configuration to the short-lived helper process.
    if proxy.get('enableProxy') and proxy.get('proxies'):
        os.environ['HTTP_PROXY'] = os.environ['HTTPS_PROXY'] = proxy['proxies'][0]['address']
    else:
        for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
            os.environ.pop(key, None)
    with OpenAI(api_key=entry['token'], base_url=address, timeout=120, max_retries=1) as client:
        result = client.chat.completions.create(
            model=entry['modelName'],
            messages=[dict(role='user', content=prompt + '\n\n' + read_text(args.input))],
            temperature=.7, max_tokens=2048)
    content = result.choices[0].message.content
    if not content:
        raise ValueError('API returned an empty summary')
    write_text(args.output, content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('srt-to-json')
    p.add_argument('-i', '--input', required=True)
    p.add_argument('-o', '--output', required=True)
    p = sub.add_parser('export')
    p.add_argument('-i', '--input', required=True)
    p.add_argument('-o', '--output', required=True)
    p.add_argument('--format', choices=['srt', 'lrc'], default='srt')
    p.add_argument('--original', help='Original JSON for bilingual output')
    p = sub.add_parser('merge')
    p.add_argument('-i', '--inputs', nargs='+', required=True)
    p.add_argument('--offsets', nargs='+', type=float, required=True)
    p.add_argument('-o', '--output', required=True)
    p = sub.add_parser('init-project')
    p.add_argument('--template', required=True)
    p.add_argument('--project', required=True)
    p.add_argument('--endpoint', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--token-env', default='VOICETRANSL_API_KEY')
    p.add_argument('--language', default='ja2zh-cn')
    p.add_argument('--engine', choices=['ForGal-json', 'sakura-v1.0'], default='ForGal-json')
    p.add_argument('--prompt-file')
    p = sub.add_parser('summarize')
    p.add_argument('-i', '--input', required=True)
    p.add_argument('-o', '--output', required=True)
    p.add_argument('--config', required=True)
    p.add_argument('--prompt-file')
    args = parser.parse_args()
    if args.command == 'srt-to-json':
        srt_to_json(args.input, args.output)
    else:
        {'export': export, 'merge': merge, 'init-project': init_project,
         'summarize': summarize}[args.command](args)


if __name__ == '__main__':
    main()
