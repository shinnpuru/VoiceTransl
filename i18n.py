"""i18n module for VoiceTransl - supports zh (default), en, ja."""

_current_lang = "zh"

TRANSLATIONS = {
    "zh": {
        # === Window & Tray ===
        "window_title": "VoiceTransl",
        "tray_tooltip": "VoiceTransl",
        "tray_show": "显示主界面",
        "tray_quit": "退出",
        "tray_minimized": "程序已最小化到托盘",

        # === Tab Names (navigation) ===
        "tab_about": "关于",
        "tab_input_output": "输入输出",
        "tab_clip": "分离工具",
        "tab_synth": "合成工具",
        "tab_summarize": "总结工具",
        "tab_settings": "语音模型",
        "tab_advanced_settings": "语言模型",
        "tab_dict": "字典设置",
        "tab_log": "日志",

        # === About Tab ===
        "about_title": "🎉 感谢使用VoiceTransl！",
        "about_text": (
            "VoiceTrans是一站式离线AI视频字幕生成和翻译软件，功能包括视频下载，音频提取，听写打轴，字幕翻译，视频合成，字幕总结。\n\n"
            "界面介绍：\n"
            "- 关于：查看软件介绍和支持方式。\n"
            "- 输入输出：输入音视频文件路径或视频链接，设置代理和输出格式，运行生成字幕。\n"
            "- 分离工具：分离视频中的人声和伴奏，切分音频文件。\n"
            "- 合成工具：将音频和图片合成为视频，将字幕文件加入视频。\n"
            "- 总结工具：对字幕文件内容进行总结，生成带时间戳的摘要。\n"
            "- 语音模型：选择Whisper或Faster Whisper模型，设置听写语言和参数，选择伴奏分离模型。\n"
            "- 语言模型：选择翻译模型类别，配置在线模型令牌、地址和名称。\n"
            "- 字典设置：配置翻译前、中、后使用的字典，以及额外提示信息。\n"
            "- 日志：实时查看输出信息和日志文件。"
        ),
        "about_wiki_btn": "📖 查看使用说明和更新日志",
        "about_sponsor_title": "🎇 支持昕蒲",
        "about_afdian_btn": "⚡ 爱发电（微信和支付宝）",
        "about_bilibili_btn": "⚡ B站充电（免费B币）",
        "about_kofi_btn": "⚡ Ko-fi（Paypal和信用卡）",
        "about_start_btn": "🚀 开始",

        # === Input/Output Tab ===
        "io_input_label": "📂 拖拽音视频/SRT文件，或输入B站BV号、YouTube及其他视频链接（每行一个）。路径请勿包含非英文和空格。",
        "io_input_placeholder": "例如：C:/video.mp4或https://www.youtube.com/watch?v=...或BV1Lxt5e8EJF",
        "io_proxy_label": "🌐 设置代理地址以便下载视频和翻译。",
        "io_proxy_placeholder": "例如：http://127.0.0.1:7890，留空为不使用",
        "io_output_dir_label": "📁 设置输出目录（下载文件与生成字幕）。",
        "io_browse_dir_btn": "📂 选择目录",
        "io_use_input_dir_checkbox": "输出到音频目录（每个文件输出到其所在目录）",
        "io_format_label": "🎥 选择输出的字幕格式。",
        "io_segment_checkbox": "启用音频分段处理（长音频分段后听写翻译再合并）",
        "io_segment_duration_label": "分段时长（分钟）：",
        "io_run_btn": "🚀 运行",
        "io_cancel_btn": "⛔ 取消任务",
        "io_open_output_btn": "📁 打开输出目录",
        "io_clean_btn": "🧹 清空下载和缓存",
        "io_auto_shutdown_checkbox": "任务完成后自动关机",
        "io_transcription_lang_label": "🎤 听写语言",
        "io_target_lang_label": "🌐 翻译目标语言",
        "target_lang_zh_cn": "简体中文(zh-cn)",
        "target_lang_zh_tw": "繁體中文(zh-tw)",
        "target_lang_en": "English(en)",
        "target_lang_ja": "日本語(ja)",
        "target_lang_ko": "한국어(ko)",
        "target_lang_ru": "Русский(ru)",
        "target_lang_fr": "Français(fr)",
        "status_skip_chinese_target": "[INFO] 听写语言为中文且目标语言为中文变体，跳过翻译步骤...",

        # === Dict Tab ===
        "dict_before_label": "📚 配置翻译前的字典。",
        "dict_before_placeholder": "日文原文(Tab键)日文替换词\n日文原文(Tab键)日文替换词",
        "dict_gpt_label": "📚 配置翻译中的字典。",
        "dict_gpt_placeholder": "日文(Tab键)中文\n日文(Tab键)中文",
        "dict_after_label": "📚 配置翻译后的字典。",
        "dict_after_placeholder": "中文原文(Tab键)中文替换词\n中文原文(Tab键)中文替换词",
        "dict_extra_label": "📕 配置额外提示。",
        "dict_extra_placeholder": "请在这里输入额外的提示信息，例如世界书或台本内容。",
        "dict_prompt_mode_label": "📝 额外提示模式（选择如何处理额外提示）",

        # === Settings Tab (Speech) ===
        "settings_whisper_label": "🗣️ 选择用于语音识别的模型文件。",
        "settings_lang_label": "🌍 选择输入的语言。(ja=日语，en=英语，ko=韩语，ru=俄语，fr=法语，zh=中文，仅听写）",
        "settings_whisper_param_label": "🔧 输入Whisper命令行参数。(CPU，A卡，I卡，Mac，Linux)",
        "settings_whisper_param_placeholder": "每个参数空格隔开，请参考Whisper.cpp文档，不清楚请保持默认。",
        "settings_faster_param_label": "🔧 输入Whisper-Faster命令行参数。(N卡)",
        "settings_faster_param_placeholder": "每个参数空格隔开，请参考Faster Whisper文档，不清楚请保持默认。",
        "settings_open_whisper_btn": "📁 打开Whisper目录",
        "settings_open_faster_btn": "📁 打开Faster Whisper目录",
        "settings_refresh_speech_btn": "🔄 刷新语音模型列表",
        "settings_uvr_label": "🎤 选择用于伴奏分离的模型文件。",
        "settings_open_uvr_btn": "📁 打开UVR模型目录",

        # === Advanced Settings Tab (Language Model) ===
        "adv_translator_label": "🤖 翻译模型类别：",
        "adv_concurrency_label": "最大并发数（0为串行，1以上为并发）：",
        "adv_online_token_label": "🚀 在线模型令牌",
        "adv_online_token_placeholder": "留空为使用上次配置的Token。",
        "adv_online_model_label": "🚀 在线模型名称",
        "adv_online_model_placeholder": "例如：deepseek-chat",
        "adv_online_address_label": "🚀 在线模型API地址，省略/v1/chat/completions（选择自定义模型）",
        "adv_online_address_placeholder": "例如：http://127.0.0.1:11434",
        "adv_offline_model_label": "💻 离线模型文件",
        "adv_offline_gpu_label": "💻 离线模型GPU加载层数",
        "adv_offline_param_label": "💻 离线模型命令行参数。",
        "adv_offline_param_placeholder": "每个参数空格隔开，请参考Llama.cpp文档，不清楚请保持默认。",
        "adv_open_model_btn": "📁 打开离线模型目录",
        "adv_refresh_model_btn": "🔄 刷新离线模型列表",
        "adv_test_api_btn": "🔍 测试模型API并列出可用模型",

        # === Clip Tab ===
        "clip_tool_label": "🔪 切片工具",
        "clip_placeholder": "拖拽视频文件到方框内，并填写开始和结束时间，点击运行即可。",
        "clip_start_label": "开始时间",
        "clip_end_label": "结束时间",
        "clip_start_placeholder": "开始时间（HH:MM:SS.xxx）",
        "clip_end_placeholder": "结束时间（HH:MM:SS.xxx）",
        "clip_run_btn": "🚀 切片",
        "clip_vocal_split_label": "🎤 人声分离工具",
        "clip_vocal_placeholder": "拖拽音频文件到方框内，点击运行即可。输出文件为原文件名_vocal.wav和_no_vocal.wav。",
        "clip_vocal_run_btn": "🚀 人声分离",

        # === Synth Tab ===
        "synth_label": "💾 字幕合成工具",
        "synth_video_label": "🎥 视频文件",
        "synth_browse_video_btn": "📂 浏览视频",
        "synth_video_placeholder": "拖拽视频文件到此处，或点击浏览按钮选择。",
        "synth_srt_label": "📝 字幕文件",
        "synth_browse_srt_btn": "📂 浏览字幕",
        "synth_srt_placeholder": "拖拽字幕文件到此处，或点击浏览按钮选择。字幕文件需要和视频文件一一对应。",
        "synth_subtitle_type_label": "字幕类型",
        "synth_font_label": "字体选择",
        "synth_run_btn": "🚀 字幕合成",
        "synth_audio_label": "🎵 音频合成工具",
        "synth_audio_placeholder": "拖拽音频文件（wav，mp3，flac）和图像（png,jpg,jpeg）到下方框内，点击运行即可。音频和图像文件需要一一对应。",
        "synth_audio_run_btn": "🚀 视频合成",

        # === Summarize Tab ===
        "summarize_prompt_label": "🖋️ 模型提示",
        "summarize_prompt_placeholder": "请为以下内容创建一个带有时间戳（mm:ss格式）的粗略摘要，不多于10个事件。请关注关键事件和重要时刻，并确保所有时间戳都采用分钟:秒钟格式。",
        "summarize_input_label": "📁 输入文件",
        "summarize_input_placeholder": "拖拽文件到方框内，点击运行即可。输出文件为输入文件名.summary.txt。",
        "summarize_run_btn": "🚀 运行",

        # === Log Tab ===
        "log_realtime_label": "🖥️ 实时输出信息",
        "log_realtime_placeholder": "当前无输出信息...",
        "log_file_label": "📜 日志文件",
        "log_open_btn": "📂 打开日志文件",
        "log_file_not_found": "错误: 日志文件 '{path}' 未找到。正在等待文件创建...",
        "log_truncated": "检测到日志文件截断或轮转。从头开始读取...",
        "log_not_found_retry": "错误: 日志文件 '{path}' 再次检查时未找到。",
        "log_io_error": "读取日志文件IO错误: {error}",
        "log_unknown_error": "读取日志文件时发生未知错误: {error}",

        # === File Dialogs ===
        "dialog_select_video": "选择视频文件",
        "dialog_select_subtitle": "选择字幕文件",
        "dialog_select_output_dir": "选择输出目录",

        # === Model Selection Dialog ===
        "dialog_select_model_title": "选择模型",
        "dialog_select_model_label": "请选择要使用的模型：",
        "dialog_ok": "确定",
        "dialog_cancel": "取消",

        # === Language Selector ===
        "lang_selector_label": "界面语言：",
        "lang_zh": "中文",
        "lang_en": "English",
        "lang_ja": "日本語",

        # === Status Messages ===
        "status_cancelling": "[INFO] 正在取消当前任务...",
        "status_cancel_worker_error": "[WARN] 停止worker时出错: {error}",
        "status_cancel_thread_error": "[WARN] 停止线程时出错: {error}",
        "status_cancel_done": "[INFO] 取消任务完成。",
        "status_cleaning_intermediate": "[INFO] 正在清理中间文件...",
        "status_cleaning_output": "[INFO] 正在清理输出...",
        "status_reading_config": "[INFO] 正在读取配置...",
        "status_config_saved": "[INFO] 配置保存完成！",
        "status_config_translating": "[INFO] 正在进行翻译配置...",
        "status_config_read_error": "[ERROR] 无法读取配置文件 project/config.yaml：{error}",
        "status_config_write_error": "[ERROR] 写入配置文件失败：{error}",
        "status_translating_start": "[INFO] [进程{idx}] 开始翻译：{base}",
        "status_translating_with": "[INFO] [进程{idx}] 正在用 {engine} 翻译 {workspace}...",
        "status_translating_error": "[ERROR] [进程{idx}] 翻译 {base} 失败: {error}",
        "status_translating_srt": "[INFO] [进程{idx}] 正在生成字幕文件：{base}...",
        "status_translating_done": "[INFO] [进程{idx}] 文件 {base} 翻译完成！",
        "status_local_model_starting": "[INFO] 正在启动共享本地模型，端口 {port}...",
        "status_local_model_ready": "[INFO] 共享本地模型已就绪，端口 {port}",
        "status_local_model_timeout": "[ERROR] 共享本地模型启动超时",
        "status_local_model_start_error": "[ERROR] 启动共享本地模型失败: {error}",
        "status_local_model_stopping": "[INFO] 正在停止共享本地模型...",
        "status_local_model_start_fail": "[ERROR] 共享本地模型启动失败",
        "status_translation_fail": "[ERROR] 翻译失败: {error}",
        "status_init_project": "[INFO] 正在初始化项目文件夹...",
        "status_use_input_dir": "[INFO] 已启用「输出到音频目录」，将按每个输入文件目录输出。",
        "status_output_dir": "[INFO] 输出目录：{dir}",
        "status_current_input": "[INFO] 当前输入：{files}",
        "status_no_translator_skip": "[INFO] 翻译器未选择，按单文件流程跳过翻译步骤...",
        "status_zh_skip": "[INFO] 听写语言为中文，按单文件流程跳过翻译步骤...",
        "status_downloading_video": "[INFO] 正在下载视频...",
        "status_download_complete": "[INFO] 视频下载完成！",
        "status_download_not_found": "[ERROR] 下载完成但未找到文件：{file}",
        "status_processing_file": "[INFO] 当前处理文件：{file} 第{idx}个，共{total}个",
        "status_file_output_dir": "[INFO] 当前文件输出目录：{dir}",
        "status_srt_converting": "[INFO] 正在进行字幕转换...",
        "status_srt_convert_done": "[INFO] 字幕转换完成！",
        "status_no_transcribe_skip": "[INFO] 不进行听写，跳过听写步骤...",
        "status_existing_srt_found": "[INFO] 检测到已有字幕文件：{file}，跳过听写步骤...",
        "status_asr_done_cached": "[INFO] 语音识别完成！（使用已有字幕）",
        "status_submitting_translation": "[INFO] 正在提交文件进行翻译...",
        "status_extracting_audio": "[INFO] 正在进行音频提取...",
        "status_audio_extract_error": "[ERROR] 音频提取失败，请检查文件格式！",
        "status_segment_threshold": "[INFO] 音频时长 {duration:.2f} 秒超过阈值 {threshold} 秒，启用分段处理...",
        "status_segment_fail": "[ERROR] 音频切分失败",
        "status_segment_processing": "[INFO] 正在处理第 {idx}/{total} 个音频片段的听写...",
        "status_segment_submit_translate": "[INFO] 正在提交第 {idx}/{total} 个片段进行翻译...",
        "status_wait_segments": "[INFO] 等待所有分段翻译完成...",
        "status_merge_segments": "[INFO] 合并分段翻译结果...",
        "status_segment_done": "[INFO] 分段听写完成并合并！",
        "status_asr_in_progress": "[INFO] 正在进行语音识别...",
        "status_asr_done": "[INFO] 语音识别完成！",
        "status_all_transcribed": "[INFO] 所有文件听写完成，等待翻译线程处理剩余文件...",
        "status_all_done": "[INFO] 所有文件处理完成！",
        "status_translate_fail_count": "[WARN] {count} 个文件翻译失败，请检查日志。",
        "status_audio_duration": "[INFO] 音频时长 {duration:.2f} 秒，将分为 {segments} 个片段处理",
        "status_segment_slice_fail": "[ERROR] 切分片段 {idx} 失败",
        "status_segment_slice_fail_detail": "[ERROR] 切分片段 {idx} 失败: {error}",
        "status_audio_duration_fail": "[WARN] 获取音频时长失败: {error}",
        "status_duplicate_proc": "[WARN] 检测到进程 {name} 已在运行，跳过重复启动。",
        "status_vocal_split_label": "[INFO] 正在进行伴奏分离...第{idx}个，共{total}个",
        "status_vocal_processing_done": "[INFO] 文件处理完成！",
        "status_uvr_model_error": "[ERROR] 请选择正确的UVR模型文件！",
        "status_file_not_exist": "[ERROR] {file}文件不存在，请重新选择文件！",
        "status_synth_mismatch": "[ERROR] 字幕文件和视频文件数量不匹配，请重新选择文件！",
        "status_synth_processing": "[INFO] 当前处理文件：{file} 第{idx}个，共{total}个",
        "status_synth_font": "[INFO] 使用字幕字体：{font}",
        "status_synth_hard_sub": "[INFO] 正在合成硬字幕...",
        "status_synth_soft_sub": "[INFO] 正在合成软字幕...",
        "status_synth_done": "[INFO] 视频合成完成！",
        "status_clip_processing": "[INFO] 正在切片...从{start}到{end}...",
        "status_clip_done": "[INFO] 视频切片完成！",
        "status_audio_mismatch": "[ERROR] 音频文件和图像文件数量不匹配，请重新选择文件！",
        "status_summarize_processing": "[INFO] 正在进行文本摘要...第{idx}个，共{total}个",
        "status_api_select_model": "[ERROR] 请选择模型。",
        "status_api_testing": "[INFO] 正在测试API，地址：{url} ...",
        "status_api_complete": "[INFO] API测试完成，发现 {count} 个模型",
        "status_api_complete_body": "[INFO] API测试完成，地址：{url}，响应：{body}",
        "status_api_error": "[ERROR] API测试失败：{error}",
        "status_auto_shutdown": "[INFO] 任务完成，正在执行自动关机...",
        "status_auto_shutdown_error": "[ERROR] 自动关机失败: {error}",
        "status_local_model_closed": "[INFO] 本地模型进程已关闭",
    },
    "en": {
        # === Window & Tray ===
        "window_title": "VoiceTransl",
        "tray_tooltip": "VoiceTransl",
        "tray_show": "Show Main Window",
        "tray_quit": "Quit",
        "tray_minimized": "Program minimized to tray",

        # === Tab Names (navigation) ===
        "tab_about": "About",
        "tab_input_output": "Input/Output",
        "tab_clip": "Separation",
        "tab_synth": "Synthesis",
        "tab_summarize": "Summarize",
        "tab_settings": "Speech Model",
        "tab_advanced_settings": "Language Model",
        "tab_dict": "Dictionary",
        "tab_log": "Log",

        # === About Tab ===
        "about_title": "🎉 Thanks for Using VoiceTransl!",
        "about_text": (
            "VoiceTransl is an all-in-one offline AI video subtitle generation and translation tool. "
            "Features include video downloading, audio extraction, transcription & timing, subtitle translation, "
            "video synthesis, and subtitle summarization.\n\n"
            "Interface Guide:\n"
            "- About: View software info and support options.\n"
            "- Input/Output: Input audio/video file paths or video links, set proxy and output format, run to generate subtitles.\n"
            "- Separation: Separate vocals and accompaniment from video, split audio files.\n"
            "- Synthesis: Combine audio and images into video, add subtitle files to video.\n"
            "- Summarize: Summarize subtitle content and generate timestamped abstracts.\n"
            "- Speech Model: Select Whisper or Faster Whisper model, set transcription language and parameters, select accompaniment separation model.\n"
            "- Language Model: Select translation model type, configure online model token, address and name.\n"
            "- Dictionary: Configure pre/mid/post translation dictionaries and extra prompts.\n"
            "- Log: View real-time output and log files."
        ),
        "about_wiki_btn": "📖 View Guide & Changelog",
        "about_sponsor_title": "🎇 Support XinPu",
        "about_afdian_btn": "⚡ Afdian (WeChat & Alipay)",
        "about_bilibili_btn": "⚡ Bilibili (Free B-coins)",
        "about_kofi_btn": "⚡ Ko-fi (PayPal & Credit Card)",
        "about_start_btn": "🚀 Start",

        # === Input/Output Tab ===
        "io_input_label": "📂 Drag audio/video/SRT files, or enter Bilibili BV number, YouTube and other video links (one per line). Avoid non-English characters and spaces in paths.",
        "io_input_placeholder": "Example: C:/video.mp4 or https://www.youtube.com/watch?v=... or BV1Lxt5e8EJF",
        "io_proxy_label": "🌐 Set proxy address for video download and translation.",
        "io_proxy_placeholder": "Example: http://127.0.0.1:7890, leave empty to disable",
        "io_output_dir_label": "📁 Set output directory (downloaded files and generated subtitles).",
        "io_browse_dir_btn": "📂 Browse Directory",
        "io_use_input_dir_checkbox": "Output to audio directory (each file outputs to its own directory)",
        "io_format_label": "🎥 Select output subtitle format.",
        "io_segment_checkbox": "Enable audio segment processing (split long audio for transcription/translation then merge)",
        "io_segment_duration_label": "Segment duration (minutes):",
        "io_run_btn": "🚀 Run",
        "io_cancel_btn": "⛔ Cancel Task",
        "io_open_output_btn": "📁 Open Output Directory",
        "io_clean_btn": "🧹 Clear Downloads & Cache",
        "io_auto_shutdown_checkbox": "Auto shutdown after task completion",
        "io_transcription_lang_label": "🎤 Transcription Language",
        "io_target_lang_label": "🌐 Target Translation Language",
        "target_lang_zh_cn": "简体中文(zh-cn)",
        "target_lang_zh_tw": "繁體中文(zh-tw)",
        "target_lang_en": "English(en)",
        "target_lang_ja": "日本語(ja)",
        "target_lang_ko": "한국어(ko)",
        "target_lang_ru": "Русский(ru)",
        "target_lang_fr": "Français(fr)",
        "status_skip_chinese_target": "[INFO] Transcription is Chinese and target is a Chinese variant, skipping translation step...",

        # === Dict Tab ===
        "dict_before_label": "📚 Configure pre-translation dictionary.",
        "dict_before_placeholder": "Japanese source(Tab)Japanese replacement\nJapanese source(Tab)Japanese replacement",
        "dict_gpt_label": "📚 Configure mid-translation dictionary.",
        "dict_gpt_placeholder": "Japanese(Tab)Chinese\nJapanese(Tab)Chinese",
        "dict_after_label": "📚 Configure post-translation dictionary.",
        "dict_after_placeholder": "Chinese source(Tab)Chinese replacement\nChinese source(Tab)Chinese replacement",
        "dict_extra_label": "📕 Configure extra prompt.",
        "dict_extra_placeholder": "Enter additional prompt info here, such as world book or script content.",
        "dict_prompt_mode_label": "📝 Extra prompt mode (choose how to handle extra prompts)",

        # === Settings Tab (Speech) ===
        "settings_whisper_label": "🗣️ Select model file for speech recognition.",
        "settings_lang_label": "🌍 Select input language. (ja=Japanese, en=English, ko=Korean, ru=Russian, fr=French, zh=Chinese, transcription only)",
        "settings_whisper_param_label": "🔧 Enter Whisper command line parameters. (CPU, AMD GPU, Intel GPU, Mac, Linux)",
        "settings_whisper_param_placeholder": "Space-separated parameters, see Whisper.cpp docs. Leave default if unsure.",
        "settings_faster_param_label": "🔧 Enter Whisper-Faster command line parameters. (NVIDIA GPU)",
        "settings_faster_param_placeholder": "Space-separated parameters, see Faster Whisper docs. Leave default if unsure.",
        "settings_open_whisper_btn": "📁 Open Whisper Directory",
        "settings_open_faster_btn": "📁 Open Faster Whisper Directory",
        "settings_refresh_speech_btn": "🔄 Refresh Speech Model List",
        "settings_uvr_label": "🎤 Select model file for accompaniment separation.",
        "settings_open_uvr_btn": "📁 Open UVR Model Directory",

        # === Advanced Settings Tab (Language Model) ===
        "adv_translator_label": "🤖 Translation Model Type:",
        "adv_concurrency_label": "Max concurrency (0=serial, 1+=concurrent):",
        "adv_online_token_label": "🚀 Online Model Token",
        "adv_online_token_placeholder": "Leave empty to use last configured token.",
        "adv_online_model_label": "🚀 Online Model Name",
        "adv_online_model_placeholder": "Example: deepseek-chat",
        "adv_online_address_label": "🚀 Online Model API Address (omit /v1/chat/completions, for custom model)",
        "adv_online_address_placeholder": "Example: http://127.0.0.1:11434",
        "adv_offline_model_label": "💻 Offline Model File",
        "adv_offline_gpu_label": "💻 Offline Model GPU Layers",
        "adv_offline_param_label": "💻 Offline Model Command Line Parameters.",
        "adv_offline_param_placeholder": "Space-separated parameters, see Llama.cpp docs. Leave default if unsure.",
        "adv_open_model_btn": "📁 Open Offline Model Directory",
        "adv_refresh_model_btn": "🔄 Refresh Offline Model List",
        "adv_test_api_btn": "🔍 Test Model API & List Available Models",

        # === Clip Tab ===
        "clip_tool_label": "🔪 Clip Tool",
        "clip_placeholder": "Drag video files into the box, fill in start and end times, then click Run.",
        "clip_start_label": "Start Time",
        "clip_end_label": "End Time",
        "clip_start_placeholder": "Start Time (HH:MM:SS.xxx)",
        "clip_end_placeholder": "End Time (HH:MM:SS.xxx)",
        "clip_run_btn": "🚀 Clip",
        "clip_vocal_split_label": "🎤 Vocal Separation Tool",
        "clip_vocal_placeholder": "Drag audio files into the box and click Run. Output files will be original_filename_vocal.wav and _no_vocal.wav.",
        "clip_vocal_run_btn": "🚀 Separate Vocals",

        # === Synth Tab ===
        "synth_label": "💾 Subtitle Synthesis Tool",
        "synth_video_label": "🎥 Video Files",
        "synth_browse_video_btn": "📂 Browse Videos",
        "synth_video_placeholder": "Drag video files here or click Browse to select.",
        "synth_srt_label": "📝 Subtitle Files",
        "synth_browse_srt_btn": "📂 Browse Subtitles",
        "synth_srt_placeholder": "Drag subtitle files here or click Browse to select. Subtitle files must correspond one-to-one with video files.",
        "synth_subtitle_type_label": "Subtitle Type",
        "synth_font_label": "Font Selection",
        "synth_run_btn": "🚀 Synthesize Subtitles",
        "synth_audio_label": "🎵 Audio Synthesis Tool",
        "synth_audio_placeholder": "Drag audio files (wav, mp3, flac) and images (png, jpg, jpeg) into the box and click Run. Audio and image files must correspond one-to-one.",
        "synth_audio_run_btn": "🚀 Synthesize Video",

        # === Summarize Tab ===
        "summarize_prompt_label": "🖋️ Model Prompt",
        "summarize_prompt_placeholder": "Create a rough summary with timestamps (mm:ss format) for the following content, no more than 10 events. Focus on key events and important moments, ensure all timestamps use minutes:seconds format.",
        "summarize_input_label": "📁 Input Files",
        "summarize_input_placeholder": "Drag files into the box and click Run. Output file will be input_filename.summary.txt.",
        "summarize_run_btn": "🚀 Run",

        # === Log Tab ===
        "log_realtime_label": "🖥️ Real-time Output",
        "log_realtime_placeholder": "No output currently...",
        "log_file_label": "📜 Log File",
        "log_open_btn": "📂 Open Log File",
        "log_file_not_found": "Error: Log file '{path}' not found. Waiting for file creation...",
        "log_truncated": "Detected log file truncation or rotation. Reading from beginning...",
        "log_not_found_retry": "Error: Log file '{path}' not found on re-check.",
        "log_io_error": "IO error reading log file: {error}",
        "log_unknown_error": "Unknown error reading log file: {error}",

        # === File Dialogs ===
        "dialog_select_video": "Select Video Files",
        "dialog_select_subtitle": "Select Subtitle Files",
        "dialog_select_output_dir": "Select Output Directory",

        # === Model Selection Dialog ===
        "dialog_select_model_title": "Select Model",
        "dialog_select_model_label": "Please select a model to use:",
        "dialog_ok": "OK",
        "dialog_cancel": "Cancel",

        # === Language Selector ===
        "lang_selector_label": "UI Language:",
        "lang_zh": "中文",
        "lang_en": "English",
        "lang_ja": "日本語",

        # === Status Messages ===
        "status_cancelling": "[INFO] Cancelling current task...",
        "status_cancel_worker_error": "[WARN] Error stopping worker: {error}",
        "status_cancel_thread_error": "[WARN] Error stopping thread: {error}",
        "status_cancel_done": "[INFO] Task cancellation complete.",
        "status_cleaning_intermediate": "[INFO] Cleaning intermediate files...",
        "status_cleaning_output": "[INFO] Cleaning output...",
        "status_reading_config": "[INFO] Reading config...",
        "status_config_saved": "[INFO] Config saved successfully!",
        "status_config_translating": "[INFO] Configuring translation...",
        "status_config_read_error": "[ERROR] Cannot read config file project/config.yaml: {error}",
        "status_config_write_error": "[ERROR] Failed to write config file: {error}",
        "status_translating_start": "[INFO] [Worker {idx}] Starting translation: {base}",
        "status_translating_with": "[INFO] [Worker {idx}] Translating with {engine}: {workspace}...",
        "status_translating_error": "[ERROR] [Worker {idx}] Translation failed for {base}: {error}",
        "status_translating_srt": "[INFO] [Worker {idx}] Generating subtitle file: {base}...",
        "status_translating_done": "[INFO] [Worker {idx}] File {base} translation complete!",
        "status_local_model_starting": "[INFO] Starting shared local model on port {port}...",
        "status_local_model_ready": "[INFO] Shared local model ready on port {port}",
        "status_local_model_timeout": "[ERROR] Shared local model startup timed out",
        "status_local_model_start_error": "[ERROR] Failed to start shared local model: {error}",
        "status_local_model_stopping": "[INFO] Stopping shared local model...",
        "status_local_model_start_fail": "[ERROR] Shared local model failed to start",
        "status_translation_fail": "[ERROR] Translation failed: {error}",
        "status_init_project": "[INFO] Initializing project folder...",
        "status_use_input_dir": '[INFO] "Output to audio directory" enabled, each input file will output to its own directory.',
        "status_output_dir": "[INFO] Output directory: {dir}",
        "status_current_input": "[INFO] Current input: {files}",
        "status_no_translator_skip": "[INFO] No translator selected, skipping translation step (single file mode)...",
        "status_zh_skip": "[INFO] Transcription language is Chinese, skipping translation step (single file mode)...",
        "status_downloading_video": "[INFO] Downloading video...",
        "status_download_complete": "[INFO] Video download complete!",
        "status_download_not_found": "[ERROR] Download complete but file not found: {file}",
        "status_processing_file": "[INFO] Processing file: {file} ({idx}/{total})",
        "status_file_output_dir": "[INFO] File output directory: {dir}",
        "status_srt_converting": "[INFO] Converting subtitles...",
        "status_srt_convert_done": "[INFO] Subtitle conversion complete!",
        "status_no_transcribe_skip": "[INFO] No transcription selected, skipping transcription step...",
        "status_existing_srt_found": "[INFO] Existing subtitle file found: {file}, skipping transcription step...",
        "status_asr_done_cached": "[INFO] Speech recognition complete! (using existing subtitles)",
        "status_submitting_translation": "[INFO] Submitting file for translation...",
        "status_extracting_audio": "[INFO] Extracting audio...",
        "status_audio_extract_error": "[ERROR] Audio extraction failed, please check file format!",
        "status_segment_threshold": "[INFO] Audio duration {duration:.2f}s exceeds threshold {threshold}s, enabling segment processing...",
        "status_segment_fail": "[ERROR] Audio segmentation failed",
        "status_segment_processing": "[INFO] Processing segment {idx}/{total} transcription...",
        "status_segment_submit_translate": "[INFO] Submitting segment {idx}/{total} for translation...",
        "status_wait_segments": "[INFO] Waiting for all segment translations to complete...",
        "status_merge_segments": "[INFO] Merging segment translation results...",
        "status_segment_done": "[INFO] Segment transcription complete and merged!",
        "status_asr_in_progress": "[INFO] Performing speech recognition...",
        "status_asr_done": "[INFO] Speech recognition complete!",
        "status_all_transcribed": "[INFO] All files transcribed, waiting for translation threads to process remaining files...",
        "status_all_done": "[INFO] All files processed successfully!",
        "status_translate_fail_count": "[WARN] {count} file(s) translation failed, check the log.",
        "status_audio_duration": "[INFO] Audio duration {duration:.2f}s, will be split into {segments} segments",
        "status_segment_slice_fail": "[ERROR] Failed to slice segment {idx}",
        "status_segment_slice_fail_detail": "[ERROR] Failed to slice segment {idx}: {error}",
        "status_audio_duration_fail": "[WARN] Failed to get audio duration: {error}",
        "status_duplicate_proc": "[WARN] Process {name} is already running, skipping duplicate start.",
        "status_vocal_split_label": "[INFO] Performing accompaniment separation... ({idx}/{total})",
        "status_vocal_processing_done": "[INFO] File processing complete!",
        "status_uvr_model_error": "[ERROR] Please select a valid UVR model file!",
        "status_file_not_exist": "[ERROR] File {file} does not exist, please re-select!",
        "status_synth_mismatch": "[ERROR] Subtitle and video file counts do not match, please re-select!",
        "status_synth_processing": "[INFO] Processing file: {file} ({idx}/{total})",
        "status_synth_font": "[INFO] Using subtitle font: {font}",
        "status_synth_hard_sub": "[INFO] Synthesizing hard subtitles...",
        "status_synth_soft_sub": "[INFO] Synthesizing soft subtitles...",
        "status_synth_done": "[INFO] Video synthesis complete!",
        "status_clip_processing": "[INFO] Clipping... from {start} to {end}...",
        "status_clip_done": "[INFO] Video clip complete!",
        "status_audio_mismatch": "[ERROR] Audio and image file counts do not match, please re-select!",
        "status_summarize_processing": "[INFO] Summarizing text... ({idx}/{total})",
        "status_api_select_model": "[ERROR] Please select a model.",
        "status_api_testing": "[INFO] Testing API at: {url} ...",
        "status_api_complete": "[INFO] API test complete, found {count} model(s)",
        "status_api_complete_body": "[INFO] API test complete, URL: {url}, response: {body}",
        "status_api_error": "[ERROR] API test failed: {error}",
        "status_auto_shutdown": "[INFO] Task complete, executing auto shutdown...",
        "status_auto_shutdown_error": "[ERROR] Auto shutdown failed: {error}",
        "status_local_model_closed": "[INFO] Local model process closed",
    },
    "ja": {
        # === Window & Tray ===
        "window_title": "VoiceTransl",
        "tray_tooltip": "VoiceTransl",
        "tray_show": "メイン画面を表示",
        "tray_quit": "終了",
        "tray_minimized": "プログラムをトレイに最小化しました",

        # === Tab Names (navigation) ===
        "tab_about": "概要",
        "tab_input_output": "入出力",
        "tab_clip": "分離ツール",
        "tab_synth": "合成ツール",
        "tab_summarize": "要約ツール",
        "tab_settings": "音声モデル",
        "tab_advanced_settings": "言語モデル",
        "tab_dict": "辞書設定",
        "tab_log": "ログ",

        # === About Tab ===
        "about_title": "🎉 VoiceTranslをご利用いただきありがとうございます！",
        "about_text": (
            "VoiceTranslは、オールインワンのオフラインAI動画字幕生成・翻訳ソフトウェアです。"
            "動画ダウンロード、音声抽出、文字起こし・タイミング調整、字幕翻訳、動画合成、字幕要約などの機能があります。\n\n"
            "インターフェース紹介：\n"
            "- 概要：ソフトウェアの紹介とサポート方法を表示。\n"
            "- 入出力：音声/動画ファイルのパスまたは動画リンクを入力し、プロキシと出力形式を設定して字幕を生成。\n"
            "- 分離ツール：動画からボーカルと伴奏を分離し、音声ファイルを分割。\n"
            "- 合成ツール：音声と画像を動画に合成し、字幕ファイルを動画に追加。\n"
            "- 要約ツール：字幕ファイルの内容を要約し、タイムスタンプ付きの概要を生成。\n"
            "- 音声モデル：WhisperまたはFaster Whisperモデルを選択し、文字起こし言語とパラメータを設定、伴奏分離モデルを選択。\n"
            "- 言語モデル：翻訳モデルの種類を選択し、オンラインモデルのトークン、アドレス、名前を設定。\n"
            "- 辞書設定：翻訳前・中・後の辞書と追加プロンプト情報を設定。\n"
            "- ログ：リアルタイムの出力情報とログファイルを表示。"
        ),
        "about_wiki_btn": "📖 ガイドと更新履歴を見る",
        "about_sponsor_title": "🎇 昕蒲をサポート",
        "about_afdian_btn": "⚡ Afdian（WeChat & Alipay）",
        "about_bilibili_btn": "⚡ Bilibili（無料Bコイン）",
        "about_kofi_btn": "⚡ Ko-fi（PayPal & クレジットカード）",
        "about_start_btn": "🚀 開始",

        # === Input/Output Tab ===
        "io_input_label": "📂 音声/動画/SRTファイルをドラッグするか、BilibiliのBV番号、YouTubeなどの動画リンクを入力してください（1行に1つ）。パスに非英語文字やスペースを含めないでください。",
        "io_input_placeholder": "例：C:/video.mp4 または https://www.youtube.com/watch?v=... または BV1Lxt5e8EJF",
        "io_proxy_label": "🌐 動画ダウンロードと翻訳用のプロキシアドレスを設定。",
        "io_proxy_placeholder": "例：http://127.0.0.1:7890、空欄で無効",
        "io_output_dir_label": "📁 出力ディレクトリを設定（ダウンロードファイルと生成字幕）。",
        "io_browse_dir_btn": "📂 ディレクトリを参照",
        "io_use_input_dir_checkbox": "音声ディレクトリに出力（各ファイルをそのディレクトリに出力）",
        "io_format_label": "🎥 出力字幕形式を選択。",
        "io_segment_checkbox": "音声セグメント処理を有効化（長い音声を分割して文字起こし・翻訳後に結合）",
        "io_segment_duration_label": "セグメント長（分）：",
        "io_run_btn": "🚀 実行",
        "io_cancel_btn": "⛔ タスクキャンセル",
        "io_open_output_btn": "📁 出力ディレクトリを開く",
        "io_clean_btn": "🧹 ダウンロードとキャッシュを削除",
        "io_auto_shutdown_checkbox": "タスク完了後に自動シャットダウン",
        "io_transcription_lang_label": "🎤 文字起こし言語",
        "io_target_lang_label": "🌐 翻訳対象言語",
        "target_lang_zh_cn": "简体中文(zh-cn)",
        "target_lang_zh_tw": "繁體中文(zh-tw)",
        "target_lang_en": "English(en)",
        "target_lang_ja": "日本語(ja)",
        "target_lang_ko": "한국어(ko)",
        "target_lang_ru": "Русский(ru)",
        "target_lang_fr": "Français(fr)",
        "status_skip_chinese_target": "[INFO] 文字起こし言語が中国語で、対象言語が中国語変種のため、翻訳ステップをスキップします...",

        # === Dict Tab ===
        "dict_before_label": "📚 翻訳前の辞書を設定。",
        "dict_before_placeholder": "日本語原文(Tab)日本語置換語\n日本語原文(Tab)日本語置換語",
        "dict_gpt_label": "📚 翻訳中の辞書を設定。",
        "dict_gpt_placeholder": "日本語(Tab)中国語\n日本語(Tab)中国語",
        "dict_after_label": "📚 翻訳後の辞書を設定。",
        "dict_after_placeholder": "中国語原文(Tab)中国語置換語\n中国語原文(Tab)中国語置換語",
        "dict_extra_label": "📕 追加プロンプトを設定。",
        "dict_extra_placeholder": "追加のプロンプト情報をここに入力してください（世界観設定や台本内容など）。",
        "dict_prompt_mode_label": "📝 追加プロンプトモード（追加プロンプトの処理方法を選択）",

        # === Settings Tab (Speech) ===
        "settings_whisper_label": "🗣️ 音声認識用のモデルファイルを選択。",
        "settings_lang_label": "🌍 入力言語を選択。（ja=日本語、en=英語、ko=韓国語、ru=ロシア語、fr=フランス語、zh=中国語、文字起こしのみ）",
        "settings_whisper_param_label": "🔧 Whisperコマンドラインパラメータを入力。（CPU、AMD GPU、Intel GPU、Mac、Linux）",
        "settings_whisper_param_placeholder": "スペース区切りのパラメータ。Whisper.cppドキュメントを参照。不明な場合はデフォルトのまま。",
        "settings_faster_param_label": "🔧 Whisper-Fasterコマンドラインパラメータを入力。（NVIDIA GPU）",
        "settings_faster_param_placeholder": "スペース区切りのパラメータ。Faster Whisperドキュメントを参照。不明な場合はデフォルトのまま。",
        "settings_open_whisper_btn": "📁 Whisperディレクトリを開く",
        "settings_open_faster_btn": "📁 Faster Whisperディレクトリを開く",
        "settings_refresh_speech_btn": "🔄 音声モデルリストを更新",
        "settings_uvr_label": "🎤 伴奏分離用のモデルファイルを選択。",
        "settings_open_uvr_btn": "📁 UVRモデルディレクトリを開く",

        # === Advanced Settings Tab (Language Model) ===
        "adv_translator_label": "🤖 翻訳モデルタイプ：",
        "adv_concurrency_label": "最大同時実行数（0=直列、1以上=並列）：",
        "adv_online_token_label": "🚀 オンラインモデルトークン",
        "adv_online_token_placeholder": "空欄で前回設定したトークンを使用。",
        "adv_online_model_label": "🚀 オンラインモデル名",
        "adv_online_model_placeholder": "例：deepseek-chat",
        "adv_online_address_label": "🚀 オンラインモデルAPIアドレス（/v1/chat/completionsを省略、カスタムモデル用）",
        "adv_online_address_placeholder": "例：http://127.0.0.1:11434",
        "adv_offline_model_label": "💻 オフラインモデルファイル",
        "adv_offline_gpu_label": "💻 オフラインモデルGPUレイヤー数",
        "adv_offline_param_label": "💻 オフラインモデルコマンドラインパラメータ。",
        "adv_offline_param_placeholder": "スペース区切りのパラメータ。Llama.cppドキュメントを参照。不明な場合はデフォルトのまま。",
        "adv_open_model_btn": "📁 オフラインモデルディレクトリを開く",
        "adv_refresh_model_btn": "🔄 オフラインモデルリストを更新",
        "adv_test_api_btn": "🔍 モデルAPIをテストして利用可能なモデルを一覧表示",

        # === Clip Tab ===
        "clip_tool_label": "🔪 クリップツール",
        "clip_placeholder": "動画ファイルをボックスにドラッグし、開始時間と終了時間を入力して実行をクリック。",
        "clip_start_label": "開始時間",
        "clip_end_label": "終了時間",
        "clip_start_placeholder": "開始時間（HH:MM:SS.xxx）",
        "clip_end_placeholder": "終了時間（HH:MM:SS.xxx）",
        "clip_run_btn": "🚀 クリップ",
        "clip_vocal_split_label": "🎤 ボーカル分離ツール",
        "clip_vocal_placeholder": "音声ファイルをボックスにドラッグして実行をクリック。出力ファイルは元のファイル名_vocal.wavと_no_vocal.wavになります。",
        "clip_vocal_run_btn": "🚀 ボーカル分離",

        # === Synth Tab ===
        "synth_label": "💾 字幕合成ツール",
        "synth_video_label": "🎥 動画ファイル",
        "synth_browse_video_btn": "📂 動画を参照",
        "synth_video_placeholder": "動画ファイルをここにドラッグするか、参照ボタンをクリックして選択。",
        "synth_srt_label": "📝 字幕ファイル",
        "synth_browse_srt_btn": "📂 字幕を参照",
        "synth_srt_placeholder": "字幕ファイルをここにドラッグするか、参照ボタンをクリックして選択。字幕ファイルは動画ファイルと1対1で対応する必要があります。",
        "synth_subtitle_type_label": "字幕タイプ",
        "synth_font_label": "フォント選択",
        "synth_run_btn": "🚀 字幕合成",
        "synth_audio_label": "🎵 音声合成ツール",
        "synth_audio_placeholder": "音声ファイル（wav、mp3、flac）と画像（png、jpg、jpeg）を下のボックスにドラッグして実行をクリック。音声と画像ファイルは1対1で対応する必要があります。",
        "synth_audio_run_btn": "🚀 動画合成",

        # === Summarize Tab ===
        "summarize_prompt_label": "🖋️ モデルプロンプト",
        "summarize_prompt_placeholder": "以下の内容について、タイムスタンプ（mm:ss形式）付きの大まかな要約を10イベント以内で作成してください。重要なイベントと瞬間に焦点を当て、すべてのタイムスタンプが分:秒形式であることを確認してください。",
        "summarize_input_label": "📁 入力ファイル",
        "summarize_input_placeholder": "ファイルをボックスにドラッグして実行をクリック。出力ファイルは入力ファイル名.summary.txtになります。",
        "summarize_run_btn": "🚀 実行",

        # === Log Tab ===
        "log_realtime_label": "🖥️ リアルタイム出力",
        "log_realtime_placeholder": "現在出力はありません...",
        "log_file_label": "📜 ログファイル",
        "log_open_btn": "📂 ログファイルを開く",
        "log_file_not_found": "エラー: ログファイル '{path}' が見つかりません。ファイル作成を待機中...",
        "log_truncated": "ログファイルの切り詰めまたはローテーションを検出。最初から読み込み中...",
        "log_not_found_retry": "エラー: ログファイル '{path}' が再確認時に見つかりません。",
        "log_io_error": "ログファイル読み込みIOエラー: {error}",
        "log_unknown_error": "ログファイル読み込み中の不明なエラー: {error}",

        # === File Dialogs ===
        "dialog_select_video": "動画ファイルを選択",
        "dialog_select_subtitle": "字幕ファイルを選択",
        "dialog_select_output_dir": "出力ディレクトリを選択",

        # === Model Selection Dialog ===
        "dialog_select_model_title": "モデルを選択",
        "dialog_select_model_label": "使用するモデルを選択してください：",
        "dialog_ok": "OK",
        "dialog_cancel": "キャンセル",

        # === Language Selector ===
        "lang_selector_label": "UI言語：",
        "lang_zh": "中文",
        "lang_en": "English",
        "lang_ja": "日本語",

        # === Status Messages ===
        "status_cancelling": "[INFO] 現在のタスクをキャンセル中...",
        "status_cancel_worker_error": "[WARN] ワーカー停止エラー: {error}",
        "status_cancel_thread_error": "[WARN] スレッド停止エラー: {error}",
        "status_cancel_done": "[INFO] タスクキャンセル完了。",
        "status_cleaning_intermediate": "[INFO] 中間ファイルをクリーンアップ中...",
        "status_cleaning_output": "[INFO] 出力をクリーンアップ中...",
        "status_reading_config": "[INFO] 設定を読み込み中...",
        "status_config_saved": "[INFO] 設定保存完了！",
        "status_config_translating": "[INFO] 翻訳設定中...",
        "status_config_read_error": "[ERROR] 設定ファイル project/config.yaml を読み込めません：{error}",
        "status_config_write_error": "[ERROR] 設定ファイルの書き込みに失敗しました：{error}",
        "status_translating_start": "[INFO] [ワーカー{idx}] 翻訳開始：{base}",
        "status_translating_with": "[INFO] [ワーカー{idx}] {engine} で翻訳中 {workspace}...",
        "status_translating_error": "[ERROR] [ワーカー{idx}] {base} の翻訳に失敗: {error}",
        "status_translating_srt": "[INFO] [ワーカー{idx}] 字幕ファイル生成中：{base}...",
        "status_translating_done": "[INFO] [ワーカー{idx}] ファイル {base} 翻訳完了！",
        "status_local_model_starting": "[INFO] 共有ローカルモデルを起動中、ポート {port}...",
        "status_local_model_ready": "[INFO] 共有ローカルモデルの準備完了、ポート {port}",
        "status_local_model_timeout": "[ERROR] 共有ローカルモデルの起動がタイムアウトしました",
        "status_local_model_start_error": "[ERROR] 共有ローカルモデルの起動に失敗: {error}",
        "status_local_model_stopping": "[INFO] 共有ローカルモデルを停止中...",
        "status_local_model_start_fail": "[ERROR] 共有ローカルモデルの起動に失敗しました",
        "status_translation_fail": "[ERROR] 翻訳に失敗: {error}",
        "status_init_project": "[INFO] プロジェクトフォルダを初期化中...",
        "status_use_input_dir": "[INFO] 「音声ディレクトリに出力」が有効です。各入力ファイルをそのディレクトリに出力します。",
        "status_output_dir": "[INFO] 出力ディレクトリ：{dir}",
        "status_current_input": "[INFO] 現在の入力：{files}",
        "status_no_translator_skip": "[INFO] 翻訳器が選択されていません。単一ファイルモードで翻訳ステップをスキップ...",
        "status_zh_skip": "[INFO] 文字起こし言語が中国語です。単一ファイルモードで翻訳ステップをスキップ...",
        "status_downloading_video": "[INFO] 動画をダウンロード中...",
        "status_download_complete": "[INFO] 動画ダウンロード完了！",
        "status_download_not_found": "[ERROR] ダウンロード完了しましたがファイルが見つかりません：{file}",
        "status_processing_file": "[INFO] 処理中ファイル：{file} （{idx}/{total}）",
        "status_file_output_dir": "[INFO] ファイル出力ディレクトリ：{dir}",
        "status_srt_converting": "[INFO] 字幕を変換中...",
        "status_srt_convert_done": "[INFO] 字幕変換完了！",
        "status_no_transcribe_skip": "[INFO] 文字起こしが選択されていません。文字起こしステップをスキップ...",
        "status_existing_srt_found": "[INFO] 既存の字幕ファイルが見つかりました：{file}、文字起こしステップをスキップ...",
        "status_asr_done_cached": "[INFO] 音声認識完了！（既存の字幕を使用）",
        "status_submitting_translation": "[INFO] 翻訳用にファイルを送信中...",
        "status_extracting_audio": "[INFO] 音声を抽出中...",
        "status_audio_extract_error": "[ERROR] 音声抽出に失敗しました。ファイル形式を確認してください！",
        "status_segment_threshold": "[INFO] 音声長 {duration:.2f}秒が閾値 {threshold}秒を超えています。セグメント処理を有効化...",
        "status_segment_fail": "[ERROR] 音声セグメント分割に失敗",
        "status_segment_processing": "[INFO] セグメント {idx}/{total} の文字起こしを処理中...",
        "status_segment_submit_translate": "[INFO] セグメント {idx}/{total} を翻訳用に送信中...",
        "status_wait_segments": "[INFO] すべてのセグメント翻訳の完了を待機中...",
        "status_merge_segments": "[INFO] セグメント翻訳結果を結合中...",
        "status_segment_done": "[INFO] セグメント文字起こし完了・結合済み！",
        "status_asr_in_progress": "[INFO] 音声認識を実行中...",
        "status_asr_done": "[INFO] 音声認識完了！",
        "status_all_transcribed": "[INFO] すべてのファイルの文字起こしが完了しました。翻訳スレッドが残りのファイルを処理するのを待機中...",
        "status_all_done": "[INFO] すべてのファイル処理が完了しました！",
        "status_translate_fail_count": "[WARN] {count} ファイルの翻訳に失敗しました。ログを確認してください。",
        "status_audio_duration": "[INFO] 音声長 {duration:.2f}秒、{segments} セグメントに分割されます",
        "status_segment_slice_fail": "[ERROR] セグメント {idx} の分割に失敗",
        "status_segment_slice_fail_detail": "[ERROR] セグメント {idx} の分割に失敗: {error}",
        "status_audio_duration_fail": "[WARN] 音声長の取得に失敗: {error}",
        "status_duplicate_proc": "[WARN] プロセス {name} は既に実行中です。重複起動をスキップ。",
        "status_vocal_split_label": "[INFO] 伴奏分離を実行中...（{idx}/{total}）",
        "status_vocal_processing_done": "[INFO] ファイル処理完了！",
        "status_uvr_model_error": "[ERROR] 有効なUVRモデルファイルを選択してください！",
        "status_file_not_exist": "[ERROR] ファイル {file} が存在しません。再選択してください！",
        "status_synth_mismatch": "[ERROR] 字幕ファイルと動画ファイルの数が一致しません。再選択してください！",
        "status_synth_processing": "[INFO] 処理中ファイル：{file} （{idx}/{total}）",
        "status_synth_font": "[INFO] 字幕フォントを使用：{font}",
        "status_synth_hard_sub": "[INFO] ハード字幕を合成中...",
        "status_synth_soft_sub": "[INFO] ソフト字幕を合成中...",
        "status_synth_done": "[INFO] 動画合成完了！",
        "status_clip_processing": "[INFO] クリップ中... {start} から {end} まで...",
        "status_clip_done": "[INFO] 動画クリップ完了！",
        "status_audio_mismatch": "[ERROR] 音声ファイルと画像ファイルの数が一致しません。再選択してください！",
        "status_summarize_processing": "[INFO] テキスト要約中...（{idx}/{total}）",
        "status_api_select_model": "[ERROR] モデルを選択してください。",
        "status_api_testing": "[INFO] APIテスト中、アドレス：{url} ...",
        "status_api_complete": "[INFO] APIテスト完了、{count} モデルが見つかりました",
        "status_api_complete_body": "[INFO] APIテスト完了、URL：{url}、レスポンス：{body}",
        "status_api_error": "[ERROR] APIテスト失敗：{error}",
        "status_auto_shutdown": "[INFO] タスク完了、自動シャットダウンを実行中...",
        "status_auto_shutdown_error": "[ERROR] 自動シャットダウンに失敗: {error}",
        "status_local_model_closed": "[INFO] ローカルモデルプロセスを終了しました",
    },
}


def get_language():
    """Return the current UI language code."""
    return _current_lang


def set_language(lang):
    """Set the UI language."""
    global _current_lang
    if lang in TRANSLATIONS:
        _current_lang = lang


def _(key, **kwargs):
    """Return the translated string for the given key in the current language."""
    translations = TRANSLATIONS.get(_current_lang, TRANSLATIONS["zh"])
    text = translations.get(key, TRANSLATIONS["zh"].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text
