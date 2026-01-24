
<h1><p align='center' >VoiceTransl</p></h1>
<div align=center><img src="https://img.shields.io/github/v/release/shinnpuru/VoiceTransl"/>   <img src="https://img.shields.io/github/license/shinnpuru/VoiceTransl"/>   <img src="https://img.shields.io/github/stars/shinnpuru/VoiceTransl"/></div>

VoiceTransl是一站式离线AI视频字幕生成和翻译软件，从视频下载，音频提取，听写打轴，字幕翻译，视频合成，字幕总结各个环节为翻译者提供便利。本项目基于[Galtransl](https://github.com/xd2333/GalTransl)，采用GPLv3许可。

<div align=center><img src="title.jpg" alt="title" style="width:512px;"/></div>

## 特色

* 支持多种翻译模型，包括在线模型（任意OpenAI兼容接口）和本地模型（Sakura、Galtransl及Ollama、Llamacpp）。
* 支持AMD/NVIDIA/Intel GPU加速，翻译引擎支持调整显存占用。
* 支持多种输入格式，包括音频、视频、SRT字幕。
* 支持多种输出格式，包括SRT字幕、LRC字幕。
* 支持多种语言，包括日语，英语，韩语，俄语，法语。
* 支持VAD（语音活动检测），自动识别音频中的语音段落。
* 支持字典功能，可以自定义翻译字典，替换输入输出。
* 支持世界书/台本输入，可以自定义翻译参考资料。
* 支持从YouTube/Bilibili及媒体链接直接下载视频。
* 支持文件和链接批量处理，自动识别文件类型。
* 支持音频切分，字幕合并和视频合成。
* 支持视频总结，将视频内容总结为带时间轴简短的文本。
* 支持人声分离，将人声和伴奏分离，支持多种模型。

## 模式

本软件支持五种模式，分别是下载模式，翻译模式，听写模式，完整模式和工具模式。

1. 下载模式：支持从YouTube/Bilibili直接下载视频。请填写视频链接，语音识别选择不进行听写，字幕翻译选择不进行翻译，然后点击运行按钮。
2. 翻译模式：支持字幕翻译，支持多种翻译模型。请填写字幕文件，语音识别选择不进行听写，字幕翻译选择模型，然后点击运行按钮。
3. 听写模式：支持音频听写，支持多种听写模型。请填写音视频文件或视频链接，语音识别选择模型，字幕翻译选择不进行翻译，然后点击运行按钮。
4. 完整模式：支持从下载到翻译的完整流程。请填写音视频文件或视频链接，语音识别选择模型，字幕翻译选择模型，然后点击运行按钮。
5. 工具模式：支持音频分离，音频切分，字幕合并，视频合成和视频总结。请填写相应输入，选择工具，然后点击运行按钮。

## 在线镜像

打开即用的AI翻译，与配置环境说拜拜，推荐大家使用优云智算算力租赁平台。万卡4090 超多好玩免费的镜像给大家免费体验,高性价比算力租赁平台,上市公司ucloud旗下，专业有保障。点击链接直达[镜像地址](https://www.compshare.cn/images/compshareImage-16qc028dgfoh?referral_code=1RFfR2FQ2FyEVRJMyrOn5d&ytag=GPU_YY-GH_simple)，使用说明请看
[视频教程](https://b23.tv/qN9bDHi)。使用昕蒲邀请链接注册可得实名20增金+链接注册20+高校企业认证再得10，还可享95折，4090一小时只要1.98 ：[邀请链接](https://passport.compshare.cn/register?referral_code=1RFfR2FQ2FyEVRJMyrOn5d&ytag=simple_bilibili)

## 下载地址

下载最新版本的[VoiceTransl](https://github.com/shinnpuru/VoiceTransl/releases/)，解压后运行`VoiceTransl.exe`。

## 使用说明

使用说明请见 [视频教程](https://www.bilibili.com/video/BV1koZ6YuE1x)或者[Wiki说明](https://github.com/shinnpuru/VoiceTransl/wiki)。

## 声明

本软件仅供学习交流使用，不得用于商业用途。本软件不对任何使用者的行为负责，不保证翻译结果的准确性。使用本软件即代表您同意自行承担使用本软件的风险，包括但不限于版权风险、法律风险等。请遵守当地法律法规，不要使用本软件进行任何违法行为。

## 如果对你有帮助的话请给一个Star!

![Star History Chart](https://api.star-history.com/svg?repos=shinnpuru/VoiceTransl&type=Date)
