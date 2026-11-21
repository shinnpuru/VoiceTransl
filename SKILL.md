---
name: voicetransl-cli
description: 使用 Windows VoiceTransl 打包版（如 F:\VoiceTransl）的命令行工具，无需启动 GUI，完成音视频下载、听写打轴、字幕翻译、SRT/LRC 导出、人声分离、剪辑、字幕压制和摘要；包含端到端听写翻译流程及独立 Python 环境策略。
---

# VoiceTransl 无界面工作流

本 skill 将 `app.py` 的编排转为 Agent 可执行的命令行流程。推理优先调用发行包自带 EXE；Python 只承担缺少独立 EXE 的衔接工作。**不要运行或导入 `app.py`，不要启动 `VoiceTransl.exe`。**

**环境长期复用：每次任务只创建输出/缓存目录，不创建 venv，不重复安装或升级包。先解析已配置的固定解释器；普通本地听写翻译不执行 pip。**

## 1. 整体流程与任务路由

```text
本地音视频 ──────────────────────────┐
URL / BV号 → yt-dlp 下载 → 实际媒体文件 ┤
                                     ↓
                         [可选：UVR 人声分离]
                                     ↓
                  FFmpeg → 单声道 16kHz PCM WAV
                                     ↓
                  [长音频可分段，记录每段起始秒数]
                                     ↓
          CrispASR + ASR GGUF + forced-aligner GGUF → 原文 SRT
                                     ↓
已有 SRT ─────────────────→ SRT → 时间轴 JSON
                                     ↓
                独立翻译项目 / gt_input / *.json
                                     ↓
          translate.exe 项目目录 ForGal-json / sakura-v1.0
                      ↙                         ↘
              在线兼容 API                本地 llama-server
                      ↘                         ↙
                 gt_output / 同名 JSON（message 为译文）
                                     ↓
            [分段结果加起始偏移，合并时间轴，重新编号]
                                     ↓
           原文 / 目标 / 双语 SRT 或 LRC → 检查 → 交付
                                     ↓
                    [可选：字幕压制、封面视频、摘要]
```

根据用户要求只执行必要阶段：

| 请求 | 执行路线 |
| --- | --- |
| 听写、打轴 | 媒体 → WAV → CrispASR → 原文字幕 |
| 听写并翻译 | 媒体 → WAV → CrispASR → JSON → 翻译 → 目标/双语字幕 |
| 翻译已有 SRT | SRT → JSON → 翻译 → 导出；跳过音频提取与 ASR |
| 只转换字幕格式 | SRT → JSON → SRT/LRC；无需模型、密钥 |
| 已有同名原文 SRT | 检查内容与媒体匹配后可复用；用户要求重新听写时重做 |
| 分离、剪辑、合成、摘要 | 直接进入第 7 节对应操作 |

开始时明确输入、输出目录、源语言、目标语言、是否翻译及输出格式。从用户指令、已有任务配置和模型文件推断；只有缺失关键参数且无法推断时才询问。翻译默认延续 app.py 的 `ForGal-json`，日语到简体中文可用 `ja2zh-cn`；不要将示例语言强加到其他输入。

## 2. 定位发行包和 Python

以下均为 PowerShell。每个示例中的占位文件名需要替换为实际输入；后续代码复用本节变量。

```powershell
$Install = 'F:\VoiceTransl'  # 用户指定的发行包位置，可换盘符
$Bundle = if (Test-Path -LiteralPath "$Install\_internal\ffmpeg\ffmpeg.exe") {
    Join-Path $Install '_internal'
} else { $Install }
$FFmpeg = Join-Path $Bundle 'ffmpeg\ffmpeg.exe'
$FFprobe = Join-Path $Bundle 'ffmpeg\ffprobe.exe'
$ASR = Join-Path $Bundle 'crispasr\crispasr.exe'
$Translate = Join-Path $Bundle 'translate\translate.exe'
$Separate = Join-Path $Bundle 'separate\separate.exe'
$Llama = Join-Path $Bundle 'llama\llama-server.exe'
# 设置为当前 SKILL.md 所在目录，随 skill 一起携带 scripts 子目录。
$SkillDir = Join-Path $env:USERPROFILE '.codex\skills\voicetransl-cli'
$Helper = Join-Path $SkillDir 'scripts\voicetransl_headless.py'
$Py = & (Join-Path $SkillDir 'scripts\resolve_voicetransl_python.ps1') -Install $Install
if (!$Py) { throw '未找到可复用的 Python 解释器' }
# 使用新的 ASCII 任务路径，避免 native 工具的中文路径问题、同名输入冲突。
$Job = 'F:\VoiceTransl-jobs\job-001'
New-Item -ItemType Directory -Force -Path $Job | Out-Null
Set-Location -LiteralPath $Bundle
```

检查本任务需要的工具存在，并对当前版本运行 `--help`；不要假定包与源码版本完全一致。模型用 `Get-ChildItem -LiteralPath "$Bundle\crispasr" -Filter '*.gguf'` 和 `Get-ChildItem -LiteralPath "$Bundle\llama" -Filter '*.gguf'` 枚举；分离模型在 `separate\*.onnx`。可以用 `& $ASR --list-backends-json` 查实际后端。

`translate.exe` 的两个位置参数分别是**项目目录或 YAML 路径**、**翻译引擎**；引擎不是模型名称。均应显式提供，否则可能无操作或进入交互。翻译时工作目录保持 `$Bundle`，使 `plugins`、`translation_guidelines` 等相对资源可用。各推理 EXE 必须保留旁边的 DLL 与自身 `_internal`，不要单独复制 EXE。

### Python 调用策略

1. 有打包 CLI 的任务直接用 EXE，无需安装对应 Python 包或整份 `requirements.txt`。
2. `srt-to-json`、`export`、`merge` 只用标准库；`init-project` 使用随技能附带的 `scripts/vendor/pyyaml.zip`，无需 pip。该压缩包包含 PyYAML 6.0.3 纯 Python 源码及 MIT 许可证，可跨 Python 小版本使用，不包含 `.pyd`。携带技能时保留整个 scripts 目录。
3. 解释器解析脚本依次使用：显式 `-Python` / `VOICETRANSL_PYTHON` → `$Install\agent-runtime\python.json` 已缓存路径 → 已存在的固定环境、旧环境或源码 `.venv` → 系统 Python / py launcher。脚本只检查并缓存可用的 Python 3.10+ 绝对路径，**不会创建 venv、安装包或升级环境**。后续始终复用 `$Py`，无需 activate。
4. 听写、翻译本地媒体时，现成 Python + 打包 EXE + 技能所带 YAML 库已足够；无需检查/安装下载和摘要的依赖。下载才检查 `yt_dlp`，摘要才检查 `openai`。
5. 包中的 `python311.dll`、`base_library.zip` 和 `.pyd` **不是解释器，也不是可直接复用的 site-packages**；不要把它们加入 `PYTHONPATH`，不要用 `VoiceTransl.exe -m ...`。不要通过 DLL 加载或解包 PYZ 来执行 GUI 内嵌模块。

用户提供了固定解释器时，首次配置一次即可，例如：

```powershell
$Py = & "$SkillDir\scripts\resolve_voicetransl_python.ps1" `
  -Install $Install -Python 'E:\GalTransl-ASMR\.venv\Scripts\python.exe'
# 解释器路径写入 F:\VoiceTransl\agent-runtime\python.json；下次不再传 -Python。
```

只有可选功能缺包，且没有其他已经具备该包的可用解释器时，才初始化/补充**同一个持久环境**。不向系统 Python 或源码项目环境自动塞入新依赖，不在 `$Job` 下创建环境：

```powershell
$NeededModule = 'yt_dlp'  # 下载；摘要时为 openai
& $Py -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$NeededModule') else 1)"
if ($LASTEXITCODE -ne 0) {
    $FixedEnv = Join-Path $Install 'agent-runtime\venv'
    $FixedPy = Join-Path $FixedEnv 'Scripts\python.exe'
    if (!(Test-Path -LiteralPath $FixedPy)) {
        & $Py -m venv $FixedEnv  # 固定位置只初始化一次
        if ($LASTEXITCODE -ne 0) { throw '固定可选功能环境初始化失败' }
    }
    $Py = $FixedPy
    # 在目标环境再次检测，已有包时不会执行 pip。
    & $Py -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$NeededModule') else 1)"
    if ($LASTEXITCODE -ne 0) {
        $Package = if ($NeededModule -eq 'yt_dlp') { 'yt-dlp' } else { 'openai' }
        & $Py -m pip install $Package
        if ($LASTEXITCODE -ne 0) { throw '可选依赖安装失败' }
    }
    $Py = & "$SkillDir\scripts\resolve_voicetransl_python.ps1" -Install $Install -Python $Py
}
```

**不要把上述可选初始化代码放进每次任务的常规准备步骤；仅在实际请求下载/摘要且检测缺包时使用。** 后续任务从路径缓存直接复用，不清理、重建或例行升级该环境。包损坏时修复具体依赖，不先删除整个环境。

完全没有 Python 时才一次性准备固定运行时；已有 uv 可用 `uv python install 3.11` / `uv python find 3.11` 获得持久解释器，再交给解析脚本缓存。没有可用安装途径时明确报告缺失。网络不可用时，可选依赖用匹配 Python/Windows 架构的 wheelhouse 安装到固定环境；普通本地工作流无需联网安装 Python 包。

可用源码时也可直接运行 `srt2prompt.py -i ... -o ...`（依赖 `pysrt`）或 `prompt2srt.py -i ... -o ...`（标准库，只导出 SRT）。本 skill 的 helper 不要求这些源文件存在。`summarize.py` 没有 argparse 入口，直接运行不会执行摘要，应调用 helper 的 `summarize` 子命令。

只有打包分离器缺失且有源码时，才准备 `numpy librosa soundfile tqdm onnxruntime-directml` 并执行 `separate.py`。Windows 源码固定选用 `DmlExecutionProvider`，普通 `onnxruntime` 不是等价 GPU 替代；CPU 回退需要明确修改源码的 provider 选择。翻译源码有完整 GalTransl 与插件依赖，优先修复/换用完整发行包，不假定安装 `openai` 就能运行 `translate.py`。

## 3. 提取音频与听写

```powershell
$InputMedia = 'D:\Media\sample.mp4'
$Wav = Join-Path $Job 'input.16k.wav'
$SourceSrt = Join-Path $Job 'source.srt'
$SourceJson = Join-Path $Job 'source.json'
& $FFmpeg -nostdin -n -i $InputMedia -vn -acodec pcm_s16le -ac 1 -ar 16000 $Wav
if ($LASTEXITCODE -ne 0) { throw '音频提取失败' }
& $FFprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $Wav
```

先读取 `$Bundle\crispasr\param.txt`，沿用发行包支持的参数。以下是所检查发行包的 Qwen3-ASR + 强制对齐路线（源语言按任务修改）：

```powershell
$AsrModel = Join-Path $Bundle 'crispasr\qwen3-asr-1.7b-q4_k.gguf'
$Aligner = Join-Path $Bundle 'crispasr\qwen3-forced-aligner-0.6b-q4_k.gguf'
$AsrCache = Join-Path $Bundle 'crispasr\cache'
New-Item -ItemType Directory -Force -Path $AsrCache | Out-Null
& $ASR --backend qwen3-1.7b --model $AsrModel --aligner-model $Aligner `
  --force-aligner --language ja --file $Wav `
  --output-srt --output-file "$Job\source" --split-on-punct `
  --vad --vad-model firered --vad-threshold 0.3 --vad-min-silence-duration-ms 200 `
  --max-new-tokens 96 --frequency-penalty 0.8 --cache-dir $AsrCache
if ($LASTEXITCODE -ne 0) { throw 'CrispASR 失败' }
if (!(Test-Path -LiteralPath $SourceSrt) -or (Get-Item -LiteralPath $SourceSrt).Length -eq 0) {
    throw '未生成非空原文 SRT；检查日志及是否包含语音'
}
& $Py $Helper srt-to-json -i $SourceSrt -o $SourceJson
if ($LASTEXITCODE -ne 0) { throw '原文 SRT 转换失败' }
```

注意：

- `--output-file` 是**不带扩展名**的输出前缀；上例产物是 `source.srt`。CrispASR 的原生 JSON 不一定符合 GalTransl 输入格式，因此通过 SRT 转换。
- ASR 模型、aligner 和后端必须匹配。已有 SRT 时直接设置 `$SourceSrt` 并执行最后的转换，不需要 WAV、ASR 模型或 aligner。
- VAD 等辅助模型可能在首次运行时下载。完全离线前检查缓存；缺失时报告缺失，不静默切换 ASR 模型或声称已离线就绪。GPU 不可用时按该版本 `--help` 选择 `--gpu-backend cpu` / `--no-gpu`，并说明速度变化。
- native 运行时遇到非 ASCII 路径可能失败。媒体先放入 ASCII 任务目录，模型/缓存/程序路径也应为 ASCII；已有短路径可用，否则移动或复制所需资源到 ASCII 目录。shell 引号不能修复 native 的编码限制。
- `--max-len` 在 app.py 针对 CrispASR v0.8.28 按 UTF-8 字节换算：日/中/韩字符数乘 3、俄语乘 2、其他乘 1；其他版本先验证实际行为。

## 4. 建立独立翻译项目

每个任务单独建项目，不直接把输入写入发行包的 `project/gt_input`。目录结构：

```text
job-001/
  source.srt, source.json
  project/
    config.yaml
    dict_pre.txt, dict_gpt.txt, dict_after.txt
    gt_input/source.json
    gt_output/source.json
    transl_cache/
```

JSON 是数组，时间单位为**秒**，不是毫秒；翻译前后保留 `start/end`，翻译修改 `message`：

```json
[{"start": 0.8, "end": 2.5, "message": "こんにちは。"}]
```

从发行包 `project/config.yaml` 复制配置并调整；不要从零写一份缺少插件/字典/问题分析字段的配置。helper 保留已有配置，关闭继承的定时启动，启用日志，复制模板同目录的 txt 字典，生成任务内绝对字典路径。**不会自动同步 GUI 设置**：`gui_settings.yaml` 可作参考，但 CLI 不读取其语言、模型、提示词或输出选项；必须写入项目 YAML。

### 在线兼容接口或已运行的本地接口

```powershell
$Project = Join-Path $Job 'project'
# 从已有安全来源将密钥放入当前进程环境 VOICETRANSL_API_KEY；不要打印或写进命令行。
& $Py $Helper init-project --template "$Bundle\project\config.yaml" `
  --project $Project --endpoint 'https://api.example.com' --model 'actual-model-id' `
  --language 'ja2zh-cn'
if ($LASTEXITCODE -ne 0) { throw '翻译项目初始化失败' }
Copy-Item -LiteralPath $SourceJson -Destination "$Project\gt_input\source.json"
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:VOICETRANSL_PROGRESS = '1'
& $Translate $Project ForGal-json
if ($LASTEXITCODE -ne 0) { throw '翻译进程失败，检查任务日志' }
```

示例域名/模型必须替换为实际设置。配置含密钥，不向日志/回复输出全文。helper 从指定环境变量读取 key，写入任务配置，不将 key 置于子进程参数。已有配置中其他后端的密钥也可能被复制，交付时只给产物及脱敏配置。

主要配置对应关系：

| 需求 | 项目 config.yaml 字段 |
| --- | --- |
| 语言 | `common.language`，例如 `ja2zh-cn`、`en2zh-cn` |
| 接口/密钥/模型 | `backendSpecific.OpenAI-Compatible.tokens[]` 的 `endpoint/token/modelName` |
| 附加提示词/台本参考 | `common.gpt.change_prompt: AdditionalPrompt` + `common.gpt.prompt_content`；helper 可传 `--prompt-file` |
| 覆盖提示词 | `OverwritePrompt`；需要自行保留输入和输出约束，通常采用追加 |
| 术语/替换 | `dictionary.preDict / gpt.dict / postDict` 引用任务字典；条目按模板格式、制表符分隔 |
| JSON 插件 | `plugin.filePlugin: file_galtransl_json`；导出文本在 `message` |
| 代理 | `proxy.enableProxy` 与 `proxy.proxies[].address`；本地接口禁用代理 |
| 请求并发 | `common.workersPerProject`、分片和每批句数；按服务限额调整 |
| 思考开关 | 当前源码用 `backendSpecific.OpenAI-Compatible.thinkingEnabled`；旧包确认支持情况 |

通用翻译配置 endpoint 沿用 app.py：去掉末尾 `/v1`；后端负责拼接路由。供应商要求完整 `/chat/completions` 的特殊地址按其接口与本包实现配置，不能机械再加 `/v1`。摘要使用 SDK 的 `base_url`，区别见第 7 节。

### 自行启动本地 GGUF 翻译模型

先读取 `llama\param.txt`，列出实际 GGUF；ASR GGUF 不能当翻译模型。所检查的发行包没有 llama GGUF，缺模型时需要用户已有模型或明确的下载来源，不声称“打包即离线可翻译”。

```powershell
$Model = Join-Path $Bundle 'llama\actual-translation-model.gguf'
$Server = Start-Process -FilePath $Llama -WorkingDirectory "$Bundle\llama" `
  -ArgumentList ('-m "{0}" -ngl 100 --host 127.0.0.1 --port 8989' -f $Model) `
  -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$Job\llama.stdout.log" -RedirectStandardError "$Job\llama.stderr.log"
```

先确认端口空闲；占用时选择新端口并同步配置。轮询 `http://127.0.0.1:8989/health` 与 `/v1/models`，确认模型加载完成且模型标识匹配，再启动翻译；设置合理启动截止时间，失败读日志。不要仅凭进程存在判断就绪。显存不足减少 `-ngl`；CPU 为 `-ngl 0`。

通用模型仍用 `ForGal-json`，初始化时 endpoint 改为 `http://127.0.0.1:8989`，model 使用实际 `/v1/models` 返回的 ID，并设 `$env:VOICETRANSL_API_KEY = 'local'`。本地配置显式禁用 `proxy.enableProxy`，必要时设置 `NO_PROXY=127.0.0.1,localhost`。

Sakura 专用模型初始化时传 `--engine sakura-v1.0`，翻译执行 `& $Translate $Project sakura-v1.0`；对应配置是 `backendSpecific.SakuraLLM.endpoints/rewriteModelName`。Sakura 专用后端不读取通用额外提示词。用完只停止本任务创建的 `$Server.Id`，在 `finally` 中清理；不要按名称结束其他用户的 llama-server。

## 5. 导出、验证和交付

`translate.py` 会捕获部分异常并打印错误，因此 **退出码 0 不能单独证明翻译成功**。先确认 `gt_output/source.json` 本次生成、非空且内容可解析；检查 `GalTransl.log`、`error.log` 和失败句标记。重跑应使用明确的原项目缓存或新目录，避免把旧结果当成新结果。

```powershell
$TargetJson = Join-Path $Project 'gt_output\source.json'
& $Py $Helper export -i $TargetJson -o "$Job\source.tg.srt"
if ($LASTEXITCODE -ne 0) { throw '目标字幕导出失败' }
& $Py $Helper export -i $TargetJson --original $SourceJson -o "$Job\source.combine.srt"
if ($LASTEXITCODE -ne 0) { throw '双语字幕导出或时间轴检查失败' }
# 按所需格式选择；无需全部导出：
# & $Py $Helper export -i $SourceJson --format lrc -o "$Job\source.orig.lrc"
# & $Py $Helper export -i $TargetJson --format lrc -o "$Job\source.lrc"
# & $Py $Helper export -i $TargetJson --original $SourceJson --format lrc -o "$Job\source.combine.lrc"
```

helper 检查 JSON 数组非空、时间非负/有限、结束不早于开始和 message 类型；双语导出还检查原译句数与时间轴一致。双语格式沿用 app.py：原文、译文作为相同时间戳的独立条目，不是把两行合进一个 cue。若播放器需要单 cue 双行，按用户要求另行合并并说明格式。

最后检查原译句数/时间轴、空文本、`(Failed)` 等标记，抽查开头/中间/结尾的原文与译文；有媒体时用 FFprobe 对照末尾时间与媒体时长。大量原文未改变可能是翻译失败，也可能是专名/同语言，结合日志判断。无语音时报告无语音而不是伪造字幕。只在产物验证通过后报告完成，提供实际输出路径、语言、模型与失败/跳过项。保留任务缓存用于续跑，任务未完成时不清理原文、媒体或失败日志。

## 6. 长音频、批量与续跑

- 每个输入独立任务目录，按完整路径区分同名文件。ASR 顺序执行通常更稳，翻译可在明确的资源和 API 限额内并发；共享同一个本地翻译服务即可，不要每段启动一个模型。
- 用 FFprobe 获取真实时长，按任务选择例如 30 分钟一段。每段用 FFmpeg `-ss 起始秒 -t 片段时长` 提取为单声道 16k PCM WAV，记录**实际起始偏移秒数**。最后一段使用剩余时长。
- 对每段重复第 3～5 节；段内时间从 0 开始。合并原文 JSON 与译文 JSON 时分别加同一组起始偏移，然后统一导出，避免时间轴在每段重新归零：

```powershell
& $Py $Helper merge -i "$Job\seg000.json" "$Job\seg001.json" `
  --offsets 0 1800 -o "$Job\source.json"
& $Py $Helper merge -i "$Job\seg000.tg.json" "$Job\seg001.tg.json" `
  --offsets 0 1800 -o "$Job\target.json"
```

不要按“上一段最后一句的结束时间”推算下一段偏移，静音会使整条时间轴漂移。有重叠分段时需去重重叠区，不直接拼接。LRC 按数值时间排序，不按超过 99 分钟的时间字符串排序。

续跑优先复用已验证的 SRT 和同任务 `transl_cache`，保持模型、语言、分片参数与输入一致；改变这些条件时使用新项目。取消时只终止本任务子进程，保留已完成段及清单；不要执行 GUI 的全局清理或自动关机逻辑。

## 7. 其他 GUI 功能的 CLI 路线

### 下载（URL、YouTube、Bilibili）

用独立 Python 的 yt-dlp 统一处理，BV 号先转成 `https://www.bilibili.com/video/BV...`。不依赖冻结在 GUI 内的 `bilibili_dl` 包：

```powershell
& $Py -m yt_dlp --no-playlist --ffmpeg-location "$Bundle\ffmpeg" `
  -P $Job -o 'download_%(id)s.%(ext)s' --print 'after_move:filepath' `
  'https://www.bilibili.com/video/BVxxxxxxxxxx'
```

使用下载完成后打印的实际路径，不从标题猜文件名。合集或分 P 按用户选择调整；GUI 的 BV 路线默认第一页，上例不承诺复制其命名行为。需要登录时使用用户提供的 cookie 文件/已授权浏览器来源；代理通过 yt-dlp `--proxy` 传入。失败时报告具体错误，不把下载网页当媒体继续处理。

### 人声分离

```powershell
& $Separate -m "$Bundle\separate\UVR_MDXNET_KARA_2.onnx" $InputMedia
```

按需先用 FFmpeg 提取到任务目录的 WAV 再分离。**所检查源码中的命名相反**：`*_no_vocals.wav` 实际接收模型预测的人声，`*_vocals.wav` 接收 `mix - prediction` 残差信号。发行包可能已修复，先用短样本试听/检查两个轨道，选实际人声送入 ASR，不只根据文件名判断。`--chunks`、`--margin` 可控制分块；模型的 `n_fft/dim_t/dim_f` 要与模型匹配。

### 剪辑、图片配音频、字幕合成

```powershell
# 00:01:00～00:02:30（用明确持续时长避免 -to 的歧义）
& $FFmpeg -nostdin -n -ss '00:01:00' -i $InputMedia -t '00:01:30' `
  -c:v libx264 -c:a aac "$Job\clip.mp4"
# 用户明确配对图片/音频；不要靠分别排序默默配对
& $FFmpeg -nostdin -n -loop 1 -framerate 1 -i 'D:\Media\cover.jpg' -i $Wav `
  -shortest -c:v libx264 -pix_fmt yuv420p -vf 'pad=ceil(iw/2)*2:ceil(ih/2)*2' `
  -c:a aac "$Job\cover-video.mp4"
# MP4 软字幕（显式映射；如原编码不兼容 MP4，应转码或改 MKV）
& $FFmpeg -nostdin -n -i $InputMedia -i "$Job\source.combine.srt" `
  -map '0:v:0' -map '0:a?' -map '1:0' -c:v copy -c:a copy -c:s mov_text "$Job\soft.mp4"
```

硬字幕将 SRT 复制为 `$Job\burn.srt`，以任务目录为 cwd，减少 Windows 滤镜路径转义问题：

```powershell
Push-Location -LiteralPath $Job
try {
    & $FFmpeg -nostdin -n -i $InputMedia `
      -vf "subtitles=burn.srt:force_style='FontName=Microsoft YaHei'" `
      -c:v libx264 -c:a aac "$Job\hard.mp4"
    if ($LASTEXITCODE -ne 0) { throw '字幕压制失败' }
} finally { Pop-Location }
```

字体名称应是实际已安装字体；指定 fontsdir 时按 FFmpeg 滤镜语法额外转义盘符冒号、反斜线、引号。各命令检查退出码与输出流/时长。示例 `-n` 防止覆盖已有文件；要重做时选新输出路径或依据用户已授权的覆盖要求处理。

### 带时间戳摘要

```powershell
& $Py $Helper summarize -i "$Job\source.tg.srt" -o "$Job\summary.txt" `
  --config "$Project\config.yaml"
# 可追加 --prompt-file 'D:\Media\summary-prompt.txt'
```

摘要读取 OpenAI-Compatible 配置，转换为 SDK 的 `/v1` base_url；对非标准版本前缀的供应商，应在 helper 中按实际接口调整，不能重复拼接路由。Sakura 专用配置不会自动变成通用摘要模型；需要有摘要能力的兼容接口。长字幕超过上下文时先按时间段摘要，再按全局时间合并，不截断后声称处理完整。API 错误和空返回由 helper 以非零状态退出；检查输出存在且非空。原 `summarize.py` 会吞异常且可能复用缺少 `/v1` 的 GUI 地址，故这里采用显式适配入口。

## 8. 失败定位顺序

1. 检查路径、当前工作目录、实际 CLI 的 `--help` 与必需资源，尤其独立 EXE 的私有 DLL。
2. 提取失败查 FFmpeg；听写失败查 CrispASR stderr、模型/aligner/辅助缓存、native 路径及显存。
3. 翻译失败查项目配置的插件/语言/接口/模型/字典路径、项目日志；在线查鉴权/限流，本地查健康状态与上下文容量。限制重试，持续同一错误时停止并保留现场。
4. 导出失败查 `gt_output` JSON 是否本次生成、是否仍包含时间轴；不会通过改扩展名将 Whisper 原始 JSON 当成 GalTransl JSON。

依据：仓库 `app.py` 的 `_build_crispasr_command`、`_build_llama_server_command`、`ConcurrentTranslationPool` 与 `MainWorker`，以及 `translate.py`、`separate.py`、字幕转换模块。上述发行包路径和参数已在 `F:\VoiceTransl` 核对；其他发行版以现场资源和帮助为准。
