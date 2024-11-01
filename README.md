
<div align=center><img src="title.jpg" alt="title" style="width:512px;"/></div>

<h1><p align='center' >GalTransl for ASMR</p></h1>
<div align=center><img src="https://img.shields.io/github/v/release/XD2333/GalTransl"/>   <img src="https://img.shields.io/github/license/XD2333/GalTransl"/>   <img src="https://img.shields.io/github/stars/XD2333/GalTransl"/></div>
<p align='center' >支持GPT3.5/4/Newbing等大语言模型的ASMR自动化翻译解决方案</p>
  
  GalTransl是一套将数个基础功能上的微小创新与对GPT提示工程（Prompt Engineering）的深度利用相结合的Galgame自动化翻译工具，用于制作内嵌式翻译补丁。 GalTransl for ASMR是GalTransl的一个分支，您可以使用本程序将日语音视频文件/字幕文件转换为中文字幕文件。

## 特色

* 支持多种翻译模型，包括在线模型（GPT3.5、GPT4、Moonshot、Minimax、Qwen、GLM）和本地模型（Sakura、Index、Galtransl）等。
* 支持AMD/NVIDIA/Intel GPU加速（Vulkan），翻译引擎支持调整显存占用。
* 支持多种输入格式，包括音频、视频、SRT字幕。
* 支持多种输出格式，包括SRT字幕、LRC字幕。
* 支持字典功能，可以自定义翻译字典，替换输入输出。
* 支持从YouTube/Bilibili直接下载视频。
* 支持文件和链接批量处理，自动识别文件类型。

## 使用

* 从Release页面下载最新版本的[GalTransl for ASMR](https://github.com/shinnpuru/GalTransl-for-ASMR/releases)，解压后运行`app.exe`。

* 听写模型基于[whisper.cpp](https://github.com/ggerganov/whisper.cpp)引擎，需要自行下载，请选择合适的模型下载然后放到`app.exe`旁边。

| 模型  | 磁盘    | 显存     | 链接 |
| ------ | ------- | ------- | ----- |
| small  | 466 MiB | ~852 MB | [下载](https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-small.bin?download=true) |
| medium | 1.5 GiB | ~2.1 GB | [下载](https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin?download=true) |
| large  | 2.9 GiB | ~3.9 GB | [下载](https://hf-mirror.com/ggerganov/whisper.cpp/resolve/main/ggml-large-v2.bin?download=true) |

* 本地翻译模型基于[llama.cpp](https://github.com/ggerganov/llama.cpp)引擎，需要自行下载，请选择合适的模型下载然后放到`app.exe`旁边。可以参考[GalTransl](https://github.com/xd2333/GalTransl)，[Index](https://github.com/bilibili/Index-1.9B)，[Sakura](https://github.com/SakuraLLM/SakuraLLM)等项目，仅支持`.gguf`格式的模型。

| 模型  | 磁盘    | 显存     | 链接 |
| ------ | ------- | ------- | ----- |
| Index-1.9B-Q4  | 1.24 MiB | ~4G | [下载](https://hf-mirror.com/IndexTeam/Index-1.9B-Chat-GGUF/resolve/main/ggml-model-Q4_K_M.gguf?download=true) |
| Sakura-7B-Q4  | 4.56 GiB | ~8 GB | [下载](https://hf-mirror.com/SakuraLLM/Sakura-7B-LNovel-v0.9-GGUF/resolve/main/sakura-7b-lnovel-v0.9-Q4_K_M.gguf?download=true) |
| GalTransl-7B-Q6 | 5.9 GiB | ~11 GB | [下载](https://hf-mirror.com/SakuraLLM/GalTransl-7B-v2.5/resolve/main/GalTransl-7B-v2-Q6_K.gguf?download=true) |
| Sakura-13B-Q4  | 9.45 GB | ~16 GB | [下载](https://hf-mirror.com/SakuraLLM/Sakura-14B-LNovel-v0.9b-GGUF/resolve/main/sakura-13b-lnovel-v0.9b-Q4_K_M.gguf?download=true) |

## 开发

1. 安装依赖
```
pip install -r requirements.txt
```

2. 构建程序
```
pyinstaller --windowed app.py --hidden-import=tiktoken_ext.openai_public --hidden-import=tiktoken_ext
```

3. 拷贝文件

将`whisper`文件夹，`project`文件夹，`llama`文件夹和`ffmpeg.exe`拷贝到`dist/app/`文件夹下。


## 声明

本软件仅供学习交流使用，不得用于商业用途。本软件不对任何使用者的行为负责，不保证翻译结果的准确性。使用本软件即代表您同意自行承担使用本软件的风险，包括但不限于版权风险、法律风险等。请遵守当地法律法规，不要使用本软件进行任何违法行为。
