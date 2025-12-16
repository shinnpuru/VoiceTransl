
TRANSLATIONS = {
    'CN': {
        "lang_name": "简体中文",
        # Explicit mappings for logic keys (optional but good for consistency)
        '不进行听写': '不进行听写',
        '不进行翻译': '不进行翻译',
        '原文SRT': '原文SRT',
        '原文LRC': '原文LRC',
        '中文LRC': '中文LRC',
        '双语LRC': '双语LRC',
        '中文SRT': '中文SRT',
        '双语SRT': '双语SRT',
    },
    'EN': {
        "lang_name": "English",
        "VoiceTransl": "VoiceTransl",
        "VoiceTransl - {x}": "VoiceTransl - {x}",
        "🎉 感谢使用VoiceTransl！": "🎉 Thanks for using VoiceTransl!",
        """
VoiceTransl（原Galtransl for ASMR）是一个开源免费的离线AI视频字幕生成和翻译软件，您可以使用本程序从外语音视频文件/字幕文件生成中文字幕文件。

项目地址及使用说明: https://github.com/shinnpuru/VoiceTransl。
B站教程：https://space.bilibili.com/36464441/lists/3239068。
""": """
VoiceTransl (formerly Galtransl for ASMR) is an open-source, free, offline AI video subtitle generation and translation software. You can use this program to generate Chinese subtitle files from foreign language audio/video files or subtitle files.

Project URL and instructions: https://github.com/shinnpuru/VoiceTransl.
Bilibili Tutorial: https://space.bilibili.com/36464441/lists/3239068.
""",
        "🔧 模式说明": "🔧 Mode Description",
        """
（1）仅下载模式：选择不进行听写和不进行翻译；
（2）仅听写模式：选择听写模型，选择不进行翻译；
（3）仅翻译模式：上传SRT文件，并且选择翻译模型；
（4）完整模式：选择所有功能。
""": """
(1) Download Only Mode: Select 'No Dictation' and 'No Translation'.
(2) Dictation Only Mode: Select a dictation model and 'No Translation'.
(3) Translation Only Mode: Upload SRT file and select a translation model.
(4) Full Mode: Select all functions.
""",
        "🎇 支持昕蒲": "🎇 Support Shinnpuru",
        """
如果您喜欢这个项目并希望支持开发，欢迎通过以下方式赞助：
1. 爱发电: https://afdian.com/a/shinnpuru（微信和支付宝）
2. B站充电: https://space.bilibili.com/36464441（大会员可用免费B币）
3. Ko-fi: https://ko-fi.com/U7U018MISY（PayPal及信用卡）
您的支持将帮助昕蒲持续改进和维护这个项目！
""": """
If you like this project and want to support its development, you are welcome to sponsor via:
1. Afdian: https://afdian.com/a/shinnpuru (WeChat & Alipay)
2. Bilibili Charging: https://space.bilibili.com/36464441 (Free B-coins for premium members)
3. Ko-fi: https://ko-fi.com/U7U018MISY (PayPal & Credit Card)
Your support helps Shinnpuru improve and maintain this project!
""",
        "🚀 开始": "🚀 Start",
        "关于": "About",
        "📂 请拖拽音视频文件/SRT文件到这里，可多选，路径请勿包含非英文和空格。": "📂 Drag audio/video/SRT files here (multi-select). No non-English chars or spaces in path.",
        "当前未选择本地文件...": "No local files selected...",
        "🔗 或者输入B站视频BV号或者YouTube及其他视频链接（每行一个）。": "🔗 Or enter Bilibili BV ID or YouTube/other video links (one per line).",
        "例如：https://www.youtube.com/watch?v=...\n例如：BV1Lxt5e8EJF": "Ex: https://www.youtube.com/watch?v=...\nEx: BV1Lxt5e8EJF",
        "🌐 设置代理地址以便下载视频和翻译。": "🌐 Set proxy address for video download and translation.",
        "例如：http://127.0.0.1:7890，留空为不使用": "Ex: http://127.0.0.1:7890 (Empty to disable)",
        "🎥 选择输出的字幕格式。": "🎥 Select output subtitle format.",
        '原文SRT': 'Original SRT',
        '原文LRC': 'Original LRC',
        '中文LRC': 'Chinese LRC',
        '双语LRC': 'Bilingual LRC',
        '中文SRT': 'Chinese SRT',
        '双语SRT': 'Bilingual SRT',
        "🚀 运行": "🚀 Run",
        "当前无输出信息...": "No output information...",
        "📁 打开下载和缓存文件夹": "📁 Open Download/Cache Folder",
        "🧹 清空下载和缓存": "🧹 Clear Download/Cache",
        "主页": "Home",
        "📜 日志文件": "📜 Log File",
        "日志": "Log",
        "🗣️ 选择用于语音识别的模型文件。": "🗣️ Select model file for speech recognition.",
        '不进行听写': 'No Dictation',
        "🌍 选择输入的语言。(ja=日语，en=英语，ko=韩语，ru=俄语，fr=法语，zh=中文，仅听写）": "🌍 Select input language (ja=Japanese, en=English, ko=Korean, ru=Russian, fr=French, zh=Chinese, Dictation Only)",
        "📁 打开Whisper目录": "📁 Open Whisper Dir",
        "📁 打开Faster Whisper目录": "📁 Open Faster Whisper Dir",
        "🔧 输入Whisper命令行参数。": "🔧 Enter Whisper command line params.",
        "每个参数空格隔开，请参考Whisper.cpp，不清楚请保持默认。": "Space-separated params. Refer to Whisper.cpp. Leave default if unsure.",
        "🔧 输入Whisper-Faster命令行参数。": "🔧 Enter Whisper-Faster command line params.",
        "每个参数空格隔开，请参考Faster Whisper文档，不清楚请保持默认。": "Space-separated params. Refer to Faster Whisper docs. Leave default if unsure.",
        "听写设置": "Dictation Settings",
        "🚀 选择用于翻译的模型类别。": "🚀 Select translator model category.",
        '不进行翻译': 'No Translation',
        "🚀 在线模型令牌": "🚀 Online Model Token",
        "留空为使用上次配置的Token。": "Leave empty to use last configured Token.",
        "🚀 在线模型名称": "🚀 Online Model Name",
        "例如：deepseek-chat": "Ex: deepseek-chat",
        "🚀 自定义API地址（gpt-custom）": "🚀 Custom API Address (gpt-custom)",
        "例如：http://127.0.0.1:11434": "Ex: http://127.0.0.1:11434",
        "📶 测试连接": "📶 Test Connection",
        "正在连接...": "Connecting...",
        "💻 离线模型文件（galtransl， sakura，llamacpp）": "💻 Offline Model File (galtransl, sakura, llamacpp)",
        "💻 离线模型参数（galtransl， sakura，llamacpp）": "💻 Offline Model Params (galtransl, sakura, llamacpp)",
        "📁 打开离线模型目录": "📁 Open Offline Model Dir",
        "🔧 输入Llama.cpp命令行参数。": "🔧 Enter Llama.cpp command line params.",
        "每个参数空格隔开，请参考Llama.cpp文档，不清楚请保持默认。": "Space-separated params. Refer to Llama.cpp docs. Leave default if unsure.",
        "翻译设置": "Translation Settings",
        "📚 配置翻译前的字典。": "📚 Pre-translation Dictionary",
        "日文原文(Tab键)日文替换词\n日文原文(Tab键)日文替换词": "JP(Tab)JP_Replace\nJP(Tab)JP_Replace",
        "📚 配置翻译中的字典。": "📚 In-translation Dictionary",
        "日文(Tab键)中文\n日文(Tab键)中文": "JP(Tab)CN\nJP(Tab)CN",
        "📚 配置翻译后的字典。": "📚 Post-translation Dictionary",
        "中文原文(Tab键)中文替换词\n中文原文(Tab键)中文替换词": "CN(Tab)CN_Replace\nCN(Tab)CN_Replace",
        "📕 配置额外提示。": "📕 Extra Prompts",
        "请在这里输入额外的提示信息，例如世界书或台本内容。": "Enter extra prompts here, e.g., world book or script content.",
        "字典设置": "Dictionary Settings",
        "🔪 分割合并工具": "🔪 Split/Merge Tool",
        "拖拽文件到方框内，点击运行即可，每个文件生成一个文件夹，滑动条数字代表切割每段音频的长度（秒）。": "Drag files here, click Run. Each file creates a folder. Slider sets split duration (sec).",
        "🚀 分割": "🚀 Split",
        "拖拽多个字幕文件到方框内，点击运行即可，每次合并成一个文件。时间戳按照上面滑动条分割的时间累加。": "Drag multiple subtitle files here, click Run to merge. Timestamps accumulate based on slider.",
        "🚀 合并": "🚀 Merge",
        "✂️ 切片工具": "✂️ Clip Tool",
        "拖拽视频文件到方框内，并填写开始和结束时间，点击运行即可。": "Drag video file here, set start/end time, click Run.",
        "开始时间（HH:MM:SS.xxx）": "Start Time (HH:MM:SS.xxx)",
        "结束时间（HH:MM:SS.xxx）": "End Time (HH:MM:SS.xxx)",
        "🚀 切片": "🚀 Clip",
        "分割工具": "Split Tools",
        "🎤 人声分离工具": "🎤 Vocal Separation Tool",
        "选择用于伴奏分离的模型文件。": "Select model for vocal separation.",
        "📁 打开UVR模型目录": "📁 Open UVR Model Dir",
        "拖拽音频文件到方框内，点击运行即可。输出文件为原文件名_vocal.wav和_no_vocal.wav。": "Drag audio files here, click Run. Outputs: _vocal.wav and _no_vocal.wav.",
        "🚀 人声分离": "🚀 Separate Vocals",
        "💾 字幕合成工具": "💾 Subtitle Synthesis Tool",
        "拖拽字幕文件和视频文件到下方框内，点击运行即可。字幕和视频文件需要一一对应，例如output.mp4和output.mp4.srt。": "Drag subtitle and video files here. Must correspond 1-to-1 (e.g., output.mp4 & output.mp4.srt).",
        "🚀 字幕合成": "🚀 Synthesize Subtitles",
        "🎵 音频合成工具": "🎵 Audio Synthesis Tool",
        "拖拽音频文件（wav，mp3，flac）和图像（png,jpg,jpeg）到下方框内，点击运行即可。音频和图像文件需要一一对应。": "Drag audio (wav,mp3,flac) and image (png,jpg,jpeg) here. Must correspond 1-to-1.",
        "🚀 视频合成": "🚀 Synthesize Video",
        "合成工具": "Synthesis Tools",
        "🌍 OpenAI兼容地址": "🌍 OpenAI Compatible Address",
        "例如：https://api.deepseek.com/v1": "Ex: https://api.deepseek.com/v1",
        "🚩 模型名称": "🚩 Model Name",
        "例如：deepseek-chat": "Ex: deepseek-chat",
        "📛 模型令牌": "📛 Model Token",
        "🖋️ 模型提示": "🖋️ Model Prompt",
        "请为以下内容创建一个带有时间戳（mm:ss格式）的粗略摘要，不多于10个事件。请关注关键事件和重要时刻，并确保所有时间戳都采用分钟:秒钟格式。": "Create a rough summary with timestamps (mm:ss), max 10 events. Focus on key moments.",
        "📁 输入文件": "📁 Input Files",
        "拖拽文件到方框内，点击运行即可。输出文件为输入文件名.summary.txt。": "Drag files here, click Run. Output: filename.summary.txt.",
        "字幕总结": "Summarize",
        "成功": "Success",
        "连接成功！\n响应状态码: {status_code}": "Connection Successful!\nStatus Code: {status_code}",
        "[INFO] 连接测试成功！": "[INFO] Connection test successful!",
        "错误": "Error",
        "连接发生错误: {message}": "Connection Error: {message}",
        "[ERROR] 连接测试错误: {message}": "[ERROR] Connection test error: {message}",
        "失败": "Failed",
        "连接失败。\n状态码: {status_code}\n响应: {message}": "Connection Failed.\nStatus Code: {status_code}\nResponse: {message}",
        "[ERROR] 连接测试失败: {status_code} {message}": "[ERROR] Connection test failed: {status_code} {message}",
        "提示": "Tip",
        "当前选中的模型不支持在线连接测试。": "Selected model does not support online connection test.",
        "[INFO] 正在测试连接... URL: {api_address}": "[INFO] Testing connection... URL: {api_address}",
        "[INFO] 正在读取配置...": "[INFO] Reading config...",
        "[INFO] 配置保存完成！": "[INFO] Config saved!",
        "[ERROR] 请选择正确的UVR模型文件！": "[ERROR] Please select a valid UVR model file!",
        "[ERROR] {input_file}文件不存在，请重新选择文件！": "[ERROR] {input_file} not found, please re-select!",
        "[INFO] 正在进行伴奏分离...第{idx}个，共{total}个": "[INFO] Separating vocals... {idx}/{total}",
        "[INFO] 文件处理完成！": "[INFO] File processing complete!",
        "[INFO] 正在进行文本摘要...第{idx}个，共{total}个": "[INFO] Summarizing text... {idx}/{total}",
        "[INFO] 当前处理文件：{input_file} 第{idx}个，共{total}个": "[INFO] Processing file: {input_file} {idx}/{total}",
        "[INFO] 正在进行音频提取...每{split_mode}秒分割一次": "[INFO] Extracting audio... Split every {split_mode}s",
        "[INFO] 音频分割完成！": "[INFO] Audio split complete!",
        "[INFO] 所有文件处理完成！": "[INFO] All files processed!",
        "[ERROR] 字幕文件和视频文件数量不匹配，请重新选择文件！": "[ERROR] Mismatch in number of subtitle and video files!",
        "[INFO] 视频合成完成！": "[INFO] Video synthesis complete!",
        "[INFO] 正在进行切片...从{clip_start}到{clip_end}...": "[INFO] Clipping... from {clip_start} to {clip_end}...",
        "[INFO] 视频切片完成！": "[INFO] Video clip complete!",
        "[ERROR] 音频文件和图像文件数量不匹配，请重新选择文件！": "[ERROR] Mismatch in number of audio and image files!",
        "[INFO] 正在初始化项目文件夹...": "[INFO] Initializing project folders...",
        "[INFO] 当前输入文件：{input_files}, 当前视频链接：{yt_url}": "[INFO] Input files: {input_files}, Video URL: {yt_url}",
        "[INFO] 正在进行翻译配置...": "[INFO] Configuring translation...",
        "[INFO] 正在下载视频...": "[INFO] Downloading video...",
        "[INFO] 视频下载完成！": "[INFO] Video download complete!",
        "[INFO] 正在进行字幕转换...": "[INFO] Converting subtitles...",
        "[INFO] 字幕转换完成！": "[INFO] Subtitle conversion complete!",
        "[INFO] 不进行听写，跳过听写步骤...": "[INFO] No dictation, skipping...",
        "[INFO] 正在进行音频提取...": "[INFO] Extracting audio...",
        "[ERROR] 音频提取失败，请检查文件格式！": "[ERROR] Audio extraction failed, check file format!",
        "[INFO] 正在进行语音识别...": "[INFO] Recognizing speech...",
        "[INFO] 语音识别完成！": "[INFO] Speech recognition complete!",
        "[INFO] 翻译器未选择，跳过翻译步骤...": "[INFO] No translator selected, skipping...",
        "[INFO] 听写语言为中文，跳过翻译步骤...": "[INFO] Dictation language is Chinese, skipping translation...",
        "[INFO] 正在启动Llamacpp翻译器...": "[INFO] Starting Llamacpp translator...",
        "[INFO] 未选择模型文件，跳过翻译步骤...": "[INFO] No model file selected, skipping translation...",
        "[INFO] 正在等待Sakura翻译器启动...": "[INFO] Waiting for Sakura translator...",
        "[INFO] 正在进行翻译...": "[INFO] Translating...",
        "[INFO] 正在生成字幕文件...": "[INFO] Generating subtitle files...",
        "[INFO] 字幕文件生成完成！": "[INFO] Subtitle files generated!",
        "[INFO] 正在关闭Llamacpp翻译器...": "[INFO] Closing Llamacpp translator...",
        "[INFO] 正在清理中间文件...": "[INFO] Cleaning intermediate files...",
        "[INFO] 正在清理输出...": "[INFO] Cleaning output...",
        "[{timestamp}] 错误: 日志文件 '{LOG_PATH}' 未找到。正在等待文件创建...\n": "[{timestamp}] Error: Log file '{LOG_PATH}' not found. Waiting for creation...\n",
        "\n[{timestamp}] 检测到日志文件截断或轮转。从头开始读取...\n": "\n[{timestamp}] Log file truncated/rotated. Reading from beginning...\n",
        "[{timestamp}] 错误: 日志文件 '{LOG_PATH}' 再次检查时未找到。\n": "[{timestamp}] Error: Log file '{LOG_PATH}' not found on re-check.\n",
        "[{timestamp}] 读取日志文件IO错误: {e}\n": "[{timestamp}] IO Error reading log file: {e}\n",
        "[{timestamp}] 读取日志文件时发生未知错误: {e}\n": "[{timestamp}] Unknown error reading log file: {e}\n",
        "选择音视频文件/SRT文件": "Select Audio/Video/SRT Files",
    }
}

class Translator:
    def __init__(self):
        self.current_lang = 'CN'

    def set_language(self, lang):
        if lang in TRANSLATIONS:
            self.current_lang = lang

    def t(self, text):
        return TRANSLATIONS.get(self.current_lang, {}).get(text, text)

    def toggle(self):
        self.current_lang = 'EN' if self.current_lang == 'CN' else 'CN'
        return self.current_lang

I18N = Translator()
t = I18N.t
