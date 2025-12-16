import sys, os

os.chdir(sys._MEIPASS)
import shutil
from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer, QDateTime, QSize
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QFileDialog, QFrame, QMessageBox
from qfluentwidgets import PushButton as QPushButton, TextEdit as QTextEdit, LineEdit as QLineEdit, ComboBox as QComboBox, Slider as QSlider, FluentWindow as QMainWindow, PlainTextEdit as QPlainTextEdit, SplashScreen, NavigationAvatarWidget
from qfluentwidgets import FluentIcon, NavigationItemPosition, SubtitleLabel, TitleLabel, BodyLabel

import re
import json
import requests
import subprocess
from time import sleep
from yt_dlp import YoutubeDL
from bilibili_dl.bilibili_dl.Video import Video
from bilibili_dl.bilibili_dl.downloader import download
from bilibili_dl.bilibili_dl.utils import send_request
from bilibili_dl.bilibili_dl.constants import URL_VIDEO_INFO

from prompt2srt import make_srt, make_lrc, merge_lrc_files
from srt2prompt import make_prompt, merge_srt_files
from GalTransl.__main__ import worker
from GalTransl.COpenAI import get_api_address
from i18n import I18N, t

ONLINE_TRANSLATOR_MAPPING = {
    'moonshot': 'https://api.moonshot.cn',
    'glm': 'https://open.bigmodel.cn/api/paas',
    'deepseek': 'https://api.deepseek.com',
    'minimax': 'https://api.minimax.chat',
    'doubao': 'https://ark.cn-beijing.volces.com/api',
    'aliyun': 'https://dashscope.aliyuncs.com/compatible-mode',
    'gemini': 'https://generativelanguage.googleapis.com',
    'ollama': 'http://localhost:11434',
    'llamacpp': 'http://localhost:8989',
}

TRANSLATOR_SUPPORTED = [
    '不进行翻译',
    "gpt-custom",
    "sakura-009",
    "sakura-010",
    "galtransl"
] + list(ONLINE_TRANSLATOR_MAPPING.keys())

# redirect sys.stdout and sys.stderr to one log file
LOG_PATH = 'log.txt'
sys.stdout = open(LOG_PATH, 'w', encoding='utf-8')
sys.stderr = sys.stdout

def get_combo_value(combo):
    data = combo.itemData(combo.currentIndex())
    return data if data is not None else combo.currentText()

def set_combo_value(combo, value):
    index = combo.findData(value)
    if index != -1:
        combo.setCurrentIndex(index)
    else:
        index = combo.findText(value)
        if index != -1:
            combo.setCurrentIndex(index)
        else:
             combo.setCurrentText(value)

class Widget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        # Set the scroll area as the parent of the widget
        self.vBoxLayout = QVBoxLayout(self)

        # Must set a globally unique object name for the sub-interface
        self.setObjectName(text.replace(' ', '-'))

class MainWindow(QMainWindow):
    status = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None
        self.update_window_title()
        self.setWindowIcon(QtGui.QIcon('icon.png'))
        self.status.connect(lambda x: self.update_window_title(x))
        self.resize(800, 600)
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(102, 102))
        self.show()
        self.initUI()
        self.setup_timer()
        self.splashScreen.finish()

    def update_window_title(self, status=None):
        if status:
            self.setWindowTitle(t("VoiceTransl - {x}").format(x=status))
        else:
            self.setWindowTitle(t("VoiceTransl"))

    def initUI(self):
        self.initAboutTab()
        self.initInputOutputTab()
        self.initLogTab()
        self.initSettingsTab()
        self.initAdvancedSettingTab()
        self.initDictTab()
        self.initClipTab()
        self.initSynthTab()
        self.initSummarizeTab()
        self.initLanguageSwitch()

        # load config
        if os.path.exists('config.txt'):
            with open('config.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) >= 14:
                    whisper_file = lines[0].strip()
                    translator = lines[1].strip()
                    language = lines[2].strip()
                    gpt_token = lines[3].strip()
                    gpt_address = lines[4].strip()
                    gpt_model = lines[5].strip()
                    sakura_file = lines[6].strip()
                    sakura_mode = int(lines[7].strip())
                    proxy_address = lines[8].strip()
                    summary_address = lines[9].strip()
                    summary_model = lines[10].strip()
                    summary_token = lines[11].strip()
                    uvr_file = lines[12].strip()
                    output_format = lines[13].strip()

                    if self.whisper_file: set_combo_value(self.whisper_file, whisper_file)
                    set_combo_value(self.translator_group, translator)
                    set_combo_value(self.input_lang, language)
                    self.gpt_token.setText(gpt_token)
                    self.gpt_address.setText(gpt_address)
                    self.gpt_model.setText(gpt_model)
                    if self.sakura_file: set_combo_value(self.sakura_file, sakura_file)
                    self.sakura_mode.setValue(sakura_mode)
                    self.proxy_address.setText(proxy_address)
                    self.summarize_address.setText(summary_address)
                    self.summarize_model.setText(summary_model)
                    self.summarize_token.setText(summary_token)
                    if self.uvr_file: set_combo_value(self.uvr_file, uvr_file)
                    set_combo_value(self.output_format, output_format)

                if len(lines) >= 15:
                    app_lang = lines[14].strip()
                    I18N.set_language(app_lang)
                    self.update_texts()

        if os.path.exists('whisper/param.txt'):
            with open('whisper/param.txt', 'r', encoding='utf-8') as f:
                self.param_whisper.setPlainText(f.read())

        if os.path.exists('whisper-faster/param.txt'):
            with open('whisper-faster/param.txt', 'r', encoding='utf-8') as f:
                self.param_whisper_faster.setPlainText(f.read())

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

        if os.path.exists('project/extra_prompt.txt'):
            with open('project/extra_prompt.txt', 'r', encoding='utf-8') as f:
                self.extra_prompt.setPlainText(f.read())

    def initLanguageSwitch(self):
        # We use a custom widget or reuse navigation avatar widget as a button
        self.language_btn = NavigationAvatarWidget(t("lang_name"), 'icon.png')
        # We need to disconnect the default clicked behavior if any, but NavigationAvatarWidget usually expects usage.
        # Actually, let's just use a regular item or hack the widget.
        # NavigationAvatarWidget(name, avatarPath)
        # It displays name and avatar.

        # We can also add a custom widget.
        # Let's add a button to the bottom.
        self.navigationInterface.addWidget(
            routeKey='language_switch',
            widget=self.language_btn,
            onClick=self.toggle_language,
            position=NavigationItemPosition.BOTTOM
        )

    def toggle_language(self):
        I18N.toggle()
        self.update_texts()

    def update_texts(self):
        self.update_window_title()
        self.update_navigation_texts()

        # About Tab
        self.label_about_title.setText(t("🎉 感谢使用VoiceTransl！"))
        self.introduce_text.setPlainText(t("""
VoiceTransl（原Galtransl for ASMR）是一个开源免费的离线AI视频字幕生成和翻译软件，您可以使用本程序从外语音视频文件/字幕文件生成中文字幕文件。

项目地址及使用说明: https://github.com/shinnpuru/VoiceTransl。
B站教程：https://space.bilibili.com/36464441/lists/3239068。
"""))
        self.label_mode_title.setText(t("🔧 模式说明"))
        self.mode_text.setPlainText(t("""
（1）仅下载模式：选择不进行听写和不进行翻译；
（2）仅听写模式：选择听写模型，选择不进行翻译；
（3）仅翻译模式：上传SRT文件，并且选择翻译模型；
（4）完整模式：选择所有功能。
"""))
        self.label_disclaimer_title.setText(t("🎇 支持昕蒲"))
        self.disclaimer_text.setPlainText(t("""
如果您喜欢这个项目并希望支持开发，欢迎通过以下方式赞助：
1. 爱发电: https://afdian.com/a/shinnpuru（微信和支付宝）
2. B站充电: https://space.bilibili.com/36464441（大会员可用免费B币）
3. Ko-fi: https://ko-fi.com/U7U018MISY（PayPal及信用卡）
您的支持将帮助昕蒲持续改进和维护这个项目！
"""))
        self.start_button.setText(t("🚀 开始"))

        # Home Tab
        self.label_input_desc.setText(t("📂 请拖拽音视频文件/SRT文件到这里，可多选，路径请勿包含非英文和空格。"))
        self.input_files_list.setPlaceholderText(t("当前未选择本地文件..."))
        self.label_yt_desc.setText(t("🔗 或者输入B站视频BV号或者YouTube及其他视频链接（每行一个）。"))
        self.yt_url.setPlaceholderText(t("例如：https://www.youtube.com/watch?v=...\n例如：BV1Lxt5e8EJF"))
        self.label_proxy_desc.setText(t("🌐 设置代理地址以便下载视频和翻译。"))
        self.proxy_address.setPlaceholderText(t("例如：http://127.0.0.1:7890，留空为不使用"))
        self.label_output_desc.setText(t("🎥 选择输出的字幕格式。"))

        # Refresh Output Format Combo
        current_format = get_combo_value(self.output_format)
        self.output_format.clear()
        formats = ['原文SRT', '原文LRC', '中文LRC', '双语LRC', '中文SRT', '双语SRT']
        for fmt in formats:
            self.output_format.addItem(t(fmt), fmt)
        set_combo_value(self.output_format, current_format)

        self.run_button.setText(t("🚀 运行"))
        self.output_text_edit.setPlaceholderText(t("当前无输出信息..."))
        self.open_output_button.setText(t("📁 打开下载和缓存文件夹"))
        self.clean_button.setText(t("🧹 清空下载和缓存"))

        # Log Tab
        self.label_log_title.setText(t("📜 日志文件"))

        # Settings Tab
        self.label_whisper_desc.setText(t("🗣️ 选择用于语音识别的模型文件。"))

        # Refresh Whisper Combo
        current_whisper = get_combo_value(self.whisper_file)
        self.whisper_file.clear()
        whisper_lst = [i for i in os.listdir('whisper') if i.startswith('ggml') and i.endswith('bin') and not 'silero' in i] + [i for i in os.listdir('whisper-faster') if i.startswith('faster-whisper')] + ['不进行听写']
        for i in whisper_lst:
            if i == '不进行听写':
                self.whisper_file.addItem(t(i), i)
            else:
                self.whisper_file.addItem(i)
        set_combo_value(self.whisper_file, current_whisper)

        self.label_lang_desc.setText(t("🌍 选择输入的语言。(ja=日语，en=英语，ko=韩语，ru=俄语，fr=法语，zh=中文，仅听写）"))
        # Refresh Lang Combo
        # Items are codes, no change needed in combo, but label changed.

        self.open_whisper_dir.setText(t("📁 打开Whisper目录"))
        self.open_faster_dir.setText(t("📁 打开Faster Whisper目录"))
        self.label_whisper_param.setText(t("🔧 输入Whisper命令行参数。"))
        self.param_whisper.setPlaceholderText(t("每个参数空格隔开，请参考Whisper.cpp，不清楚请保持默认。"))
        self.label_whisper_faster_param.setText(t("🔧 输入Whisper-Faster命令行参数。"))
        self.param_whisper_faster.setPlaceholderText(t("每个参数空格隔开，请参考Faster Whisper文档，不清楚请保持默认。"))

        # Advanced Settings Tab
        self.label_trans_desc.setText(t("🚀 选择用于翻译的模型类别。"))

        # Refresh Translator Group
        current_trans = get_combo_value(self.translator_group)
        self.translator_group.clear()
        for i in TRANSLATOR_SUPPORTED:
            if i == '不进行翻译':
                self.translator_group.addItem(t(i), i)
            else:
                self.translator_group.addItem(i)
        set_combo_value(self.translator_group, current_trans)

        self.label_gpt_token.setText(t("🚀 在线模型令牌"))
        self.gpt_token.setPlaceholderText(t("留空为使用上次配置的Token。"))
        self.label_gpt_model.setText(t("🚀 在线模型名称"))
        self.gpt_model.setPlaceholderText(t("例如：deepseek-chat"))
        self.label_gpt_address.setText(t("🚀 自定义API地址（gpt-custom）"))
        self.gpt_address.setPlaceholderText(t("例如：http://127.0.0.1:11434"))
        self.test_connection_btn.setText(t("📶 测试连接"))
        self.label_offline_model.setText(t("💻 离线模型文件（galtransl， sakura，llamacpp）"))
        self.label_offline_params.setText(t("💻 离线模型参数（galtransl， sakura，llamacpp）"))
        self.open_model_dir.setText(t("📁 打开离线模型目录"))
        self.label_llama_param.setText(t("🔧 输入Llama.cpp命令行参数。"))
        self.param_llama.setPlaceholderText(t("每个参数空格隔开，请参考Llama.cpp文档，不清楚请保持默认。"))

        # Dict Tab
        self.label_dict_pre.setText(t("📚 配置翻译前的字典。"))
        self.before_dict.setPlaceholderText(t("日文原文(Tab键)日文替换词\n日文原文(Tab键)日文替换词"))
        self.label_dict_gpt.setText(t("📚 配置翻译中的字典。"))
        self.gpt_dict.setPlaceholderText(t("日文(Tab键)中文\n日文(Tab键)中文"))
        self.label_dict_after.setText(t("📚 配置翻译后的字典。"))
        self.after_dict.setPlaceholderText(t("中文原文(Tab键)中文替换词\n中文原文(Tab键)中文替换词"))
        self.label_extra_prompt.setText(t("📕 配置额外提示。"))
        self.extra_prompt.setPlaceholderText(t("请在这里输入额外的提示信息，例如世界书或台本内容。"))

        # Clip Tab
        self.label_split_tool.setText(t("🔪 分割合并工具"))
        self.split_files_list.setPlaceholderText(t("拖拽文件到方框内，点击运行即可，每个文件生成一个文件夹，滑动条数字代表切割每段音频的长度（秒）。"))
        self.run_split_button.setText(t("🚀 分割"))
        self.merge_files_list.setPlaceholderText(t("拖拽多个字幕文件到方框内，点击运行即可，每次合并成一个文件。时间戳按照上面滑动条分割的时间累加。"))
        self.run_merge_button.setText(t("🚀 合并"))
        self.label_clip_tool.setText(t("✂️ 切片工具"))
        self.clip_files_list.setPlaceholderText(t("拖拽视频文件到方框内，并填写开始和结束时间，点击运行即可。"))
        self.clip_start_time.setPlaceholderText(t("开始时间（HH:MM:SS.xxx）"))
        self.clip_end_time.setPlaceholderText(t("结束时间（HH:MM:SS.xxx）"))
        self.run_clip_button.setText(t("🚀 切片"))

        # Synth Tab
        self.label_vocal_sep.setText(t("🎤 人声分离工具"))
        self.label_vocal_model_desc.setText(t("选择用于伴奏分离的模型文件。"))
        self.open_uvr_dir.setText(t("📁 打开UVR模型目录"))
        self.uvr_file_list.setPlaceholderText(t("拖拽音频文件到方框内，点击运行即可。输出文件为原文件名_vocal.wav和_no_vocal.wav。"))
        self.run_uvr_button.setText(t("🚀 人声分离"))
        self.label_sub_synth.setText(t("💾 字幕合成工具"))
        self.synth_files_list.setPlaceholderText(t("拖拽字幕文件和视频文件到下方框内，点击运行即可。字幕和视频文件需要一一对应，例如output.mp4和output.mp4.srt。"))
        self.run_synth_button.setText(t("🚀 字幕合成"))
        self.label_audio_synth.setText(t("🎵 音频合成工具"))
        self.synth_audio_files_list.setPlaceholderText(t("拖拽音频文件（wav，mp3，flac）和图像（png,jpg,jpeg）到下方框内，点击运行即可。音频和图像文件需要一一对应。"))
        self.run_synth_audio_button.setText(t("🚀 视频合成"))

        # Summarize Tab
        self.label_sum_addr.setText(t("🌍 OpenAI兼容地址"))
        self.summarize_address.setPlaceholderText(t("例如：https://api.deepseek.com/v1"))
        self.label_sum_model.setText(t("🚩 模型名称"))
        self.summarize_model.setPlaceholderText(t("例如：deepseek-chat"))
        self.label_sum_token.setText(t("📛 模型令牌"))
        self.label_sum_prompt.setText(t("🖋️ 模型提示"))
        self.summarize_prompt.setPlaceholderText(t("请为以下内容创建一个带有时间戳（mm:ss格式）的粗略摘要，不多于10个事件。请关注关键事件和重要时刻，并确保所有时间戳都采用分钟:秒钟格式。"))
        self.label_sum_files.setText(t("📁 输入文件"))
        self.summarize_files_list.setPlaceholderText(t("拖拽文件到方框内，点击运行即可。输出文件为输入文件名.summary.txt。"))
        self.run_summarize_button.setText(t("🚀 运行"))

        # Language Button Text
        try:
            if hasattr(self.language_btn, 'setName'):
                self.language_btn.setName(t("lang_name"))
            elif hasattr(self.language_btn, 'setText'):
                self.language_btn.setText(t("lang_name"))
        except AttributeError:
            pass

    def update_navigation_texts(self):
        # Map route keys to translation keys
        key_map = {
            "Log": "日志",
            "About": "关于",
            "Home": "主页",
            "Dict": "字典设置",
            "Settings": "听写设置",
            "AdvancedSettings": "翻译设置",
            "Clip": "分割工具",
            "Synth": "合成工具",
            "Summarize": "字幕总结"
        }

        try:
            # Try to access items dict from NavigationInterface
            if hasattr(self.navigationInterface, 'items'):
                items = self.navigationInterface.items
                for route_key, item in items.items():
                    if route_key in key_map:
                        if hasattr(item, 'setText'):
                            item.setText(t(key_map[route_key]))
        except Exception:
            pass

    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_log_file)
        self.timer.start(1000)
        self.last_read_position = 0
        self.file_not_found_message_shown = False

    def read_log_file(self):
        """读取日志文件并更新显示"""
        try:
            # 检查文件是否存在
            if not os.path.exists(LOG_PATH):
                if not self.file_not_found_message_shown:
                    timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                    self.log_display.setPlainText(t("[{timestamp}] 错误: 日志文件 '{LOG_PATH}' 未找到。正在等待文件创建...\n").format(timestamp=timestamp, LOG_PATH=LOG_PATH))
                    self.file_not_found_message_shown = True
                self.last_read_position = 0 # 如果文件消失了，重置读取位置
                return

            # 如果文件之前未找到但现在找到了
            if self.file_not_found_message_shown:
                self.log_display.clear() # 清除之前的错误信息
                self.file_not_found_message_shown = False
                self.last_read_position = 0 # 从头开始读

            with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
                # 检查文件是否被截断或替换 (例如日志轮转)
                # 通过 seek(0, 2) 获取当前文件大小
                current_file_size = f.seek(0, os.SEEK_END)
                if current_file_size < self.last_read_position:
                    # 文件变小了，意味着文件被截断或替换了
                    timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                    self.log_display.appendPlainText(t("\n[{timestamp}] 检测到日志文件截断或轮转。从头开始读取...\n").format(timestamp=timestamp))
                    self.last_read_position = 0
                    # 可以选择清空显示: self.log_display.clear()
                    # 但通常追加提示然后从头读新内容更好

                f.seek(self.last_read_position)
                new_content = f.read()
                if new_content:
                    self.log_display.appendPlainText(new_content) # appendPlainText 会自动处理换行
                    # 自动滚动到底部
                    scrollbar = self.log_display.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())

                self.last_read_position = f.tell() # 更新下次读取的起始位置

        except FileNotFoundError: # 这个理论上在上面的 os.path.exists 检查后不应频繁触发
            if not self.file_not_found_message_shown:
                timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
                self.log_display.setPlainText(t("[{timestamp}] 错误: 日志文件 '{LOG_PATH}' 再次检查时未找到。\n").format(timestamp=timestamp, LOG_PATH=LOG_PATH))
                self.file_not_found_message_shown = True
            self.last_read_position = 0
        except IOError as e:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            self.log_display.appendPlainText(t("[{timestamp}] 读取日志文件IO错误: {e}\n").format(timestamp=timestamp, e=e))
            # 可以考虑在IO错误时停止timer或做其他处理
        except Exception as e:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            self.log_display.appendPlainText(t("[{timestamp}] 读取日志文件时发生未知错误: {e}\n").format(timestamp=timestamp, e=e))

    def closeEvent(self, event):
        """确保在关闭窗口时停止定时器"""
        self.timer.stop()
        event.accept()

    def initLogTab(self):
        self.log_tab = Widget("Log", self)
        self.log_layout = self.log_tab.vBoxLayout
        self.label_log_title = BodyLabel(t("📜 日志文件"))
        self.log_layout.addWidget(self.label_log_title)

        # log
        self.log_display = QPlainTextEdit(self)
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("font-family: Consolas, Monospace; font-size: 10pt;") # 设置等宽字体
        self.log_layout.addWidget(self.log_display)

        self.addSubInterface(self.log_tab, FluentIcon.INFO, "日志", NavigationItemPosition.TOP)

    def initAboutTab(self):
        self.about_tab = Widget("About", self)
        self.about_layout = self.about_tab.vBoxLayout

        # introduce
        self.label_about_title = TitleLabel(t("🎉 感谢使用VoiceTransl！"))
        self.about_layout.addWidget(self.label_about_title)
        self.introduce_text = QTextEdit()
        self.introduce_text.setReadOnly(True)
        self.introduce_text.setPlainText(t(
"""
VoiceTransl（原Galtransl for ASMR）是一个开源免费的离线AI视频字幕生成和翻译软件，您可以使用本程序从外语音视频文件/字幕文件生成中文字幕文件。

项目地址及使用说明: https://github.com/shinnpuru/VoiceTransl。
B站教程：https://space.bilibili.com/36464441/lists/3239068。
"""))
        self.about_layout.addWidget(self.introduce_text)

        # mode
        self.label_mode_title = TitleLabel(t("🔧 模式说明"))
        self.about_layout.addWidget(self.label_mode_title)
        self.mode_text = QTextEdit()
        self.mode_text.setReadOnly(True)
        self.mode_text.setPlainText(t(
"""
（1）仅下载模式：选择不进行听写和不进行翻译；
（2）仅听写模式：选择听写模型，选择不进行翻译；
（3）仅翻译模式：上传SRT文件，并且选择翻译模型；  
（4）完整模式：选择所有功能。
"""))
        self.about_layout.addWidget(self.mode_text)

        # disclaimer
        self.label_disclaimer_title = TitleLabel(t("🎇 支持昕蒲"))
        self.about_layout.addWidget(self.label_disclaimer_title)
        self.disclaimer_text = QTextEdit()
        self.disclaimer_text.setReadOnly(True)
        self.disclaimer_text.setPlainText(t(
"""
如果您喜欢这个项目并希望支持开发，欢迎通过以下方式赞助：
1. 爱发电: https://afdian.com/a/shinnpuru（微信和支付宝）
2. B站充电: https://space.bilibili.com/36464441（大会员可用免费B币）
3. Ko-fi: https://ko-fi.com/U7U018MISY（PayPal及信用卡）
您的支持将帮助昕蒲持续改进和维护这个项目！
"""))
        self.about_layout.addWidget(self.disclaimer_text)

        # start
        self.start_button = QPushButton(t("🚀 开始"))
        self.start_button.clicked.connect(lambda: self.switchTo(self.input_output_tab))
        self.about_layout.addWidget(self.start_button)

        self.addSubInterface(self.about_tab, FluentIcon.HEART, "关于", NavigationItemPosition.TOP)
        
    def initInputOutputTab(self):
        self.input_output_tab = Widget("Home", self)
        self.input_output_layout = self.input_output_tab.vBoxLayout
        
        # Input Section
        self.label_input_desc = BodyLabel(t("📂 请拖拽音视频文件/SRT文件到这里，可多选，路径请勿包含非英文和空格。"))
        self.input_output_layout.addWidget(self.label_input_desc)
        self.input_files_list = QTextEdit()
        self.input_files_list.setAcceptDrops(True)
        self.input_files_list.dropEvent = lambda e: self.input_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.input_files_list.setPlaceholderText(t("当前未选择本地文件..."))
        self.input_output_layout.addWidget(self.input_files_list)

        # YouTube URL Section
        self.label_yt_desc = BodyLabel(t("🔗 或者输入B站视频BV号或者YouTube及其他视频链接（每行一个）。"))
        self.input_output_layout.addWidget(self.label_yt_desc)
        self.yt_url = QTextEdit()
        self.yt_url.setAcceptDrops(False)
        self.yt_url.setPlaceholderText(t("例如：https://www.youtube.com/watch?v=...\n例如：BV1Lxt5e8EJF"))
        self.input_output_layout.addWidget(self.yt_url)

        # Proxy Section
        self.label_proxy_desc = BodyLabel(t("🌐 设置代理地址以便下载视频和翻译。"))
        self.input_output_layout.addWidget(self.label_proxy_desc)
        self.proxy_address = QLineEdit()
        self.proxy_address.setPlaceholderText(t("例如：http://127.0.0.1:7890，留空为不使用"))
        self.input_output_layout.addWidget(self.proxy_address)

        # Format Section
        self.label_output_desc = BodyLabel(t("🎥 选择输出的字幕格式。"))
        self.input_output_layout.addWidget(self.label_output_desc)
        self.output_format = QComboBox()
        formats = ['原文SRT', '原文LRC', '中文LRC', '双语LRC', '中文SRT', '双语SRT']
        for fmt in formats:
            self.output_format.addItem(t(fmt), fmt)
        set_combo_value(self.output_format, '中文SRT')
        self.input_output_layout.addWidget(self.output_format)

        self.run_button = QPushButton(t("🚀 运行"))
        self.run_button.clicked.connect(self.run_worker)
        self.input_output_layout.addWidget(self.run_button)

        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.output_text_edit.setPlaceholderText(t("当前无输出信息..."))
        self.status.connect(self.output_text_edit.append)
        self.input_output_layout.addWidget(self.output_text_edit)

        self.open_output_button = QPushButton(t("📁 打开下载和缓存文件夹"))
        self.open_output_button.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'project/cache')))
        self.input_output_layout.addWidget(self.open_output_button)
        
        self.clean_button = QPushButton(t("🧹 清空下载和缓存"))
        self.clean_button.clicked.connect(self.cleaner)
        self.input_output_layout.addWidget(self.clean_button)
        
        self.addSubInterface(self.input_output_tab, FluentIcon.HOME, "主页", NavigationItemPosition.TOP)

    def initDictTab(self):
        self.dict_tab = Widget("Dict", self)
        self.dict_layout = self.dict_tab.vBoxLayout

        self.label_dict_pre = BodyLabel(t("📚 配置翻译前的字典。"))
        self.dict_layout.addWidget(self.label_dict_pre)
        self.before_dict = QTextEdit()
        self.before_dict.setPlaceholderText(t("日文原文(Tab键)日文替换词\n日文原文(Tab键)日文替换词"))
        self.dict_layout.addWidget(self.before_dict)
        
        self.label_dict_gpt = BodyLabel(t("📚 配置翻译中的字典。"))
        self.dict_layout.addWidget(self.label_dict_gpt)
        self.gpt_dict = QTextEdit()
        self.gpt_dict.setPlaceholderText(t("日文(Tab键)中文\n日文(Tab键)中文"))
        self.dict_layout.addWidget(self.gpt_dict)
        
        self.label_dict_after = BodyLabel(t("📚 配置翻译后的字典。"))
        self.dict_layout.addWidget(self.label_dict_after)
        self.after_dict = QTextEdit()
        self.after_dict.setPlaceholderText(t("中文原文(Tab键)中文替换词\n中文原文(Tab键)中文替换词"))
        self.dict_layout.addWidget(self.after_dict)

        self.label_extra_prompt = BodyLabel(t("📕 配置额外提示。"))
        self.dict_layout.addWidget(self.label_extra_prompt)
        self.extra_prompt = QTextEdit()
        self.extra_prompt.setPlaceholderText(t("请在这里输入额外的提示信息，例如世界书或台本内容。"))
        self.dict_layout.addWidget(self.extra_prompt)

        self.addSubInterface(self.dict_tab, FluentIcon.DICTIONARY, "字典设置", NavigationItemPosition.TOP)
        
    def initSettingsTab(self):
        self.settings_tab = Widget("Settings", self)
        self.settings_layout = self.settings_tab.vBoxLayout
        
        # Whisper Section
        self.label_whisper_desc = BodyLabel(t("🗣️ 选择用于语音识别的模型文件。"))
        self.settings_layout.addWidget(self.label_whisper_desc)
        self.whisper_file = QComboBox()
        whisper_lst = [i for i in os.listdir('whisper') if i.startswith('ggml') and i.endswith('bin') and not 'silero' in i] + [i for i in os.listdir('whisper-faster') if i.startswith('faster-whisper')] + ['不进行听写']
        for i in whisper_lst:
            if i == '不进行听写':
                self.whisper_file.addItem(t(i), i)
            else:
                self.whisper_file.addItem(i)
        self.settings_layout.addWidget(self.whisper_file)

        self.label_lang_desc = BodyLabel(t("🌍 选择输入的语言。(ja=日语，en=英语，ko=韩语，ru=俄语，fr=法语，zh=中文，仅听写）"))
        self.settings_layout.addWidget(self.label_lang_desc)
        self.input_lang = QComboBox()
        self.input_lang.addItems(['ja','en','ko','ru','fr','zh'])
        self.settings_layout.addWidget(self.input_lang)

        self.open_whisper_dir = QPushButton(t("📁 打开Whisper目录"))
        self.open_whisper_dir.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'whisper')))
        self.open_faster_dir = QPushButton(t("📁 打开Faster Whisper目录"))
        self.open_faster_dir.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'whisper-faster')))
        self.settings_layout.addWidget(self.open_whisper_dir)
        self.settings_layout.addWidget(self.open_faster_dir)

        self.label_whisper_param = BodyLabel(t("🔧 输入Whisper命令行参数。"))
        self.settings_layout.addWidget(self.label_whisper_param)
        self.param_whisper = QTextEdit()
        self.param_whisper.setPlaceholderText(t("每个参数空格隔开，请参考Whisper.cpp，不清楚请保持默认。"))
        self.settings_layout.addWidget(self.param_whisper)

        self.label_whisper_faster_param = BodyLabel(t("🔧 输入Whisper-Faster命令行参数。"))
        self.settings_layout.addWidget(self.label_whisper_faster_param)
        self.param_whisper_faster = QTextEdit()
        self.param_whisper_faster.setPlaceholderText(t("每个参数空格隔开，请参考Faster Whisper文档，不清楚请保持默认。"))
        self.settings_layout.addWidget(self.param_whisper_faster)

        self.addSubInterface(self.settings_tab, FluentIcon.MUSIC, "听写设置", NavigationItemPosition.TOP)

    def initAdvancedSettingTab(self):
        self.advanced_settings_tab = Widget("AdvancedSettings", self)
        self.advanced_settings_layout = self.advanced_settings_tab.vBoxLayout

        # Translator Section
        self.label_trans_desc = BodyLabel(t("🚀 选择用于翻译的模型类别。"))
        self.advanced_settings_layout.addWidget(self.label_trans_desc)
        self.translator_group = QComboBox()
        for i in TRANSLATOR_SUPPORTED:
            if i == '不进行翻译':
                self.translator_group.addItem(t(i), i)
            else:
                self.translator_group.addItem(i)
        self.advanced_settings_layout.addWidget(self.translator_group)
        
        self.label_gpt_token = BodyLabel(t("🚀 在线模型令牌"))
        self.advanced_settings_layout.addWidget(self.label_gpt_token)
        self.gpt_token = QLineEdit()
        self.gpt_token.setPlaceholderText(t("留空为使用上次配置的Token。"))
        self.advanced_settings_layout.addWidget(self.gpt_token)

        self.label_gpt_model = BodyLabel(t("🚀 在线模型名称"))
        self.advanced_settings_layout.addWidget(self.label_gpt_model)
        self.gpt_model = QLineEdit()
        self.gpt_model.setPlaceholderText(t("例如：deepseek-chat"))
        self.advanced_settings_layout.addWidget(self.gpt_model)

        self.label_gpt_address = BodyLabel(t("🚀 自定义API地址（gpt-custom）"))
        self.advanced_settings_layout.addWidget(self.label_gpt_address)
        self.gpt_address = QLineEdit()
        self.gpt_address.setPlaceholderText(t("例如：http://127.0.0.1:11434"))
        self.advanced_settings_layout.addWidget(self.gpt_address)

        self.test_connection_btn = QPushButton(t("📶 测试连接"))
        self.test_connection_btn.clicked.connect(self.test_connection)
        self.advanced_settings_layout.addWidget(self.test_connection_btn)
        
        self.label_offline_model = BodyLabel(t("💻 离线模型文件（galtransl， sakura，llamacpp）"))
        self.advanced_settings_layout.addWidget(self.label_offline_model)
        self.sakura_file = QComboBox()
        sakura_lst = [i for i in os.listdir('llama') if i.endswith('gguf')]
        self.sakura_file.addItems(sakura_lst)
        self.advanced_settings_layout.addWidget(self.sakura_file)
        
        self.label_offline_params = BodyLabel(t("💻 离线模型参数（galtransl， sakura，llamacpp）"))
        self.advanced_settings_layout.addWidget(self.label_offline_params)
        self.sakura_value = QLineEdit()
        self.sakura_value.setPlaceholderText("100")
        self.sakura_value.setReadOnly(True)
        self.advanced_settings_layout.addWidget(self.sakura_value)
        self.sakura_mode = QSlider(Qt.Horizontal)
        self.sakura_mode.setRange(0, 100)
        self.sakura_mode.setValue(100)
        self.sakura_mode.valueChanged.connect(lambda: self.sakura_value.setText(str(self.sakura_mode.value())))
        self.advanced_settings_layout.addWidget(self.sakura_mode)

        self.open_model_dir = QPushButton(t("📁 打开离线模型目录"))
        self.open_model_dir.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'llama')))
        self.advanced_settings_layout.addWidget(self.open_model_dir)

        self.label_llama_param = BodyLabel(t("🔧 输入Llama.cpp命令行参数。"))
        self.advanced_settings_layout.addWidget(self.label_llama_param)
        self.param_llama = QTextEdit()
        self.param_llama.setPlaceholderText(t("每个参数空格隔开，请参考Llama.cpp文档，不清楚请保持默认。"))
        self.advanced_settings_layout.addWidget(self.param_llama)

        self.addSubInterface(self.advanced_settings_tab, FluentIcon.BOOK_SHELF, "翻译设置", NavigationItemPosition.TOP)

    def initClipTab(self):
        self.clip_tab = Widget("Clip", self)
        self.clip_layout = self.clip_tab.vBoxLayout

        # Split Section
        self.label_split_tool = BodyLabel(t("🔪 分割合并工具"))
        self.clip_layout.addWidget(self.label_split_tool)
        self.split_value = QLineEdit()
        self.split_value.setPlaceholderText("600")
        self.split_value.setReadOnly(True)
        self.clip_layout.addWidget(self.split_value)
        self.split_mode = QSlider(Qt.Horizontal)
        self.split_mode.setRange(0, 3600)
        self.split_mode.setValue(600)
        self.split_mode.valueChanged.connect(lambda: self.split_value.setText(str(self.split_mode.value())))
        self.clip_layout.addWidget(self.split_mode)

        self.split_files_list = QTextEdit()
        self.split_files_list.setAcceptDrops(True)
        self.split_files_list.dropEvent = lambda e: self.split_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.split_files_list.setPlaceholderText(t("拖拽文件到方框内，点击运行即可，每个文件生成一个文件夹，滑动条数字代表切割每段音频的长度（秒）。"))
        self.clip_layout.addWidget(self.split_files_list)
        self.run_split_button = QPushButton(t("🚀 分割"))
        self.run_split_button.clicked.connect(self.run_split)
        self.clip_layout.addWidget(self.run_split_button)

        self.merge_files_list = QTextEdit()
        self.merge_files_list.setAcceptDrops(True)
        self.merge_files_list.dropEvent = lambda e: self.merge_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.merge_files_list.setPlaceholderText(t("拖拽多个字幕文件到方框内，点击运行即可，每次合并成一个文件。时间戳按照上面滑动条分割的时间累加。"))
        self.clip_layout.addWidget(self.merge_files_list)
        self.run_merge_button = QPushButton(t("🚀 合并"))
        self.run_merge_button.clicked.connect(self.run_merge)
        self.clip_layout.addWidget(self.run_merge_button)

        # Clip Section
        self.label_clip_tool = BodyLabel(t("✂️ 切片工具"))
        self.clip_layout.addWidget(self.label_clip_tool)
        self.clip_files_list = QTextEdit()
        self.clip_files_list.setAcceptDrops(True)
        self.clip_files_list.dropEvent = lambda e: self.clip_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.clip_files_list.setPlaceholderText(t("拖拽视频文件到方框内，并填写开始和结束时间，点击运行即可。"))
        self.clip_layout.addWidget(self.clip_files_list)
        self.clip_start_time = QLineEdit()
        self.clip_start_time.setPlaceholderText(t("开始时间（HH:MM:SS.xxx）"))
        self.clip_layout.addWidget(self.clip_start_time)
        self.clip_end_time = QLineEdit()
        self.clip_end_time.setPlaceholderText(t("结束时间（HH:MM:SS.xxx）"))
        self.clip_layout.addWidget(self.clip_end_time)
        self.run_clip_button = QPushButton(t("🚀 切片"))
        self.run_clip_button.clicked.connect(self.run_clip)
        self.clip_layout.addWidget(self.run_clip_button)
        
        self.addSubInterface(self.clip_tab, FluentIcon.TILES, "分割工具", NavigationItemPosition.TOP)

    def initSynthTab(self):
        self.synth_tab = Widget("Synth", self)
        self.synth_layout = self.synth_tab.vBoxLayout

        # Vocal Split
        self.label_vocal_sep = BodyLabel(t("🎤 人声分离工具"))
        self.synth_layout.addWidget(self.label_vocal_sep)
        self.label_vocal_model_desc = BodyLabel(t("选择用于伴奏分离的模型文件。"))
        self.synth_layout.addWidget(self.label_vocal_model_desc)
        self.uvr_file = QComboBox()
        uvr_lst = [i for i in os.listdir('uvr') if i.endswith('onnx')]
        self.uvr_file.addItems(uvr_lst)
        self.synth_layout.addWidget(self.uvr_file)
        self.open_uvr_dir = QPushButton(t("📁 打开UVR模型目录"))
        self.open_uvr_dir.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'uvr')))
        self.synth_layout.addWidget(self.open_uvr_dir)


        self.uvr_file_list = QTextEdit()
        self.uvr_file_list.setAcceptDrops(True)
        self.uvr_file_list.dropEvent = lambda e: self.uvr_file_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.uvr_file_list.setPlaceholderText(t("拖拽音频文件到方框内，点击运行即可。输出文件为原文件名_vocal.wav和_no_vocal.wav。"))
        self.synth_layout.addWidget(self.uvr_file_list)

        self.run_uvr_button = QPushButton(t("🚀 人声分离"))
        self.run_uvr_button.clicked.connect(self.run_vocal_split)
        self.synth_layout.addWidget(self.run_uvr_button)

        # Video Synth
        self.label_sub_synth = BodyLabel(t("💾 字幕合成工具"))
        self.synth_layout.addWidget(self.label_sub_synth)
        self.synth_files_list = QTextEdit()
        self.synth_files_list.setAcceptDrops(True)
        self.synth_files_list.dropEvent = lambda e: self.synth_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.synth_files_list.setPlaceholderText(t("拖拽字幕文件和视频文件到下方框内，点击运行即可。字幕和视频文件需要一一对应，例如output.mp4和output.mp4.srt。"))
        self.synth_layout.addWidget(self.synth_files_list)
        self.run_synth_button = QPushButton(t("🚀 字幕合成"))
        self.run_synth_button.clicked.connect(self.run_synth)
        self.synth_layout.addWidget(self.run_synth_button)

        # Audio Synth
        self.label_audio_synth = BodyLabel(t("🎵 音频合成工具"))
        self.synth_layout.addWidget(self.label_audio_synth)
        self.synth_audio_files_list = QTextEdit()
        self.synth_audio_files_list.setAcceptDrops(True)
        self.synth_audio_files_list.dropEvent = lambda e: self.synth_audio_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.synth_audio_files_list.setPlaceholderText(t("拖拽音频文件（wav，mp3，flac）和图像（png,jpg,jpeg）到下方框内，点击运行即可。音频和图像文件需要一一对应。"))
        self.synth_layout.addWidget(self.synth_audio_files_list)
        self.run_synth_audio_button = QPushButton(t("🚀 视频合成"))
        self.run_synth_audio_button.clicked.connect(self.run_synth_audio)
        self.synth_layout.addWidget(self.run_synth_audio_button)

        self.addSubInterface(self.synth_tab, FluentIcon.DEVELOPER_TOOLS, "合成工具", NavigationItemPosition.TOP)

    def initSummarizeTab(self):
        self.summarize_tab = Widget("Summarize", self)
        self.summarize_layout = self.summarize_tab.vBoxLayout

        self.label_sum_addr = BodyLabel(t("🌍 OpenAI兼容地址"))
        self.summarize_layout.addWidget(self.label_sum_addr)
        self.summarize_address = QLineEdit()
        self.summarize_address.setPlaceholderText(t("例如：https://api.deepseek.com/v1"))
        self.summarize_layout.addWidget(self.summarize_address)

        self.label_sum_model = BodyLabel(t("🚩 模型名称"))
        self.summarize_layout.addWidget(self.label_sum_model)
        self.summarize_model = QLineEdit()
        self.summarize_model.setPlaceholderText(t("例如：deepseek-chat"))
        self.summarize_layout.addWidget(self.summarize_model)

        self.label_sum_token = BodyLabel(t("📛 模型令牌"))
        self.summarize_layout.addWidget(self.label_sum_token)
        self.summarize_token = QLineEdit()
        self.summarize_layout.addWidget(self.summarize_token)

        self.label_sum_prompt = BodyLabel(t("🖋️ 模型提示"))
        self.summarize_layout.addWidget(self.label_sum_prompt)
        self.summarize_prompt = QTextEdit()
        self.summarize_prompt.setPlaceholderText(t("请为以下内容创建一个带有时间戳（mm:ss格式）的粗略摘要，不多于10个事件。请关注关键事件和重要时刻，并确保所有时间戳都采用分钟:秒钟格式。"))
        self.summarize_layout.addWidget(self.summarize_prompt)

        self.label_sum_files = BodyLabel(t("📁 输入文件"))
        self.summarize_layout.addWidget(self.label_sum_files)
        self.summarize_files_list = QTextEdit()
        self.summarize_files_list.setAcceptDrops(True)
        self.summarize_files_list.dropEvent = lambda e: self.summarize_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.summarize_files_list.setPlaceholderText(t("拖拽文件到方框内，点击运行即可。输出文件为输入文件名.summary.txt。"))
        self.summarize_layout.addWidget(self.summarize_files_list)

        self.run_summarize_button = QPushButton(t("🚀 运行"))
        self.run_summarize_button.clicked.connect(self.run_summarize)
        self.summarize_layout.addWidget(self.run_summarize_button)

        self.addSubInterface(self.summarize_tab, FluentIcon.EDUCATION, "字幕总结", NavigationItemPosition.TOP)
        
    def select_input(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(self, t("选择音视频文件/SRT文件"), "", "All Files (*);;Video Files (*.mp4 *.webm, *.flv);;SRT Files (*.srt);;Audio Files (*.wav, *.mp3, *.flac)", options=options)
        if files:
            self.input_files_list.setPlainText('\n'.join(files))

    def on_connection_result(self, success, message, status_code):
        self.test_connection_btn.setEnabled(True)
        self.test_connection_btn.setText(t("📶 测试连接"))

        msg = QMessageBox(self)
        if success:
            msg.setWindowTitle(t("成功"))
            msg.setText(t("连接成功！\n响应状态码: {status_code}").format(status_code=status_code))
            msg.setIcon(QMessageBox.Information)
            self.status.emit(t("[INFO] 连接测试成功！"))
        else:
            if status_code == 0: # Exception
                msg.setWindowTitle(t("错误"))
                msg.setText(t("连接发生错误: {message}").format(message=message))
                msg.setIcon(QMessageBox.Critical)
                self.status.emit(t("[ERROR] 连接测试错误: {message}").format(message=message))
            else:
                msg.setWindowTitle(t("失败"))
                msg.setText(t("连接失败。\n状态码: {status_code}\n响应: {message}").format(status_code=status_code, message=message))
                msg.setIcon(QMessageBox.Warning)
                self.status.emit(t("[ERROR] 连接测试失败: {status_code} {message}").format(status_code=status_code, message=message))
        msg.exec_()

    def test_connection(self):
        translator = get_combo_value(self.translator_group)
        if translator in ['不进行翻译', 'sakura-009', 'sakura-010', 'galtransl']:
             msg = QMessageBox(self)
             msg.setWindowTitle(t("提示"))
             msg.setText(t("当前选中的模型不支持在线连接测试。"))
             msg.setIcon(QMessageBox.Information)
             msg.exec_()
             return

        self.test_connection_btn.setEnabled(False)
        self.test_connection_btn.setText(t("正在连接..."))

        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)

        self.worker.connection_tested.connect(self.on_connection_result)
        self.thread.started.connect(self.worker.test_connection)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def run_worker(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def run_split(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.split)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def run_merge(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.merge)
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
    
    def cleaner(self):
        self.status.emit(t("[INFO] 正在清理中间文件..."))
        if os.path.exists('project/gt_input'):
            shutil.rmtree('project/gt_input')
        if os.path.exists('project/gt_output'):
            shutil.rmtree('project/gt_output')
        if os.path.exists('project/transl_cache'):
            shutil.rmtree('project/transl_cache')
        self.status.emit(t("[INFO] 正在清理输出..."))
        if os.path.exists('project/cache'):
            shutil.rmtree('project/cache')
        os.makedirs('project/cache', exist_ok=True)

def error_handler(func):
    def wrapper(self):
        try:
            func(self)
        except Exception as e:
            self.status.emit(f"[ERROR] {e}")
            self.finished.emit()
    return wrapper
class MainWorker(QObject):
    finished = pyqtSignal()
    connection_tested = pyqtSignal(bool, str, int)

    def __init__(self, master):
        super().__init__()
        self.master = master
        self.status = master.status

    def test_connection(self):
        translator = get_combo_value(self.master.translator_group)
        token = self.master.gpt_token.text()
        model = self.master.gpt_model.text()

        if translator == 'gpt-custom':
            base_url = self.master.gpt_address.text()
        else:
            base_url = ONLINE_TRANSLATOR_MAPPING.get(translator)

        try:
            # Construct URL using logic from GalTransl/COpenAI.py
            api_address = get_api_address(base_url.rstrip('/'))

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Simple test message
            data = {
                "model": model if model else "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5
            }

            self.status.emit(t("[INFO] 正在测试连接... URL: {api_address}").format(api_address=api_address))
            response = requests.post(api_address, headers=headers, json=data, timeout=15)

            if response.status_code == 200:
                self.connection_tested.emit(True, response.text, response.status_code)
            else:
                self.connection_tested.emit(False, response.text, response.status_code)
        except Exception as e:
            self.connection_tested.emit(False, str(e), 0)
        finally:
            self.finished.emit()

    @error_handler
    def save_config(self):
        self.status.emit(t("[INFO] 正在读取配置..."))
        whisper_file = get_combo_value(self.master.whisper_file)
        translator = get_combo_value(self.master.translator_group)
        language = get_combo_value(self.master.input_lang)
        gpt_token = self.master.gpt_token.text()
        gpt_address = self.master.gpt_address.text()
        gpt_model = self.master.gpt_model.text()
        sakura_file = get_combo_value(self.master.sakura_file)
        sakura_mode = self.master.sakura_mode.value()
        proxy_address = self.master.proxy_address.text()
        summary_address = self.master.summarize_address.text()
        summary_model = self.master.summarize_model.text()
        summary_token = self.master.summarize_token.text()
        uvr_file = get_combo_value(self.master.uvr_file)
        output_format = get_combo_value(self.master.output_format)
        app_lang = I18N.current_lang

        # save config
        with open('config.txt', 'w', encoding='utf-8') as f:
            f.write(f"{whisper_file}\n{translator}\n{language}\n{gpt_token}\n{gpt_address}\n{gpt_model}\n{sakura_file}\n{sakura_mode}\n{proxy_address}\n{summary_address}\n{summary_model}\n{summary_token}\n{uvr_file}\n{output_format}\n{app_lang}\n")

        # save whisper param
        with open('whisper/param.txt', 'w', encoding='utf-8') as f:
            f.write(self.master.param_whisper.toPlainText())

        # save llama param
        with open('llama/param.txt', 'w', encoding='utf-8') as f:
            f.write(self.master.param_llama.toPlainText())

        # save before dict
        with open('project/dict_pre.txt', 'w', encoding='utf-8') as f:
            f.write(self.master.before_dict.toPlainText())

        # save gpt dict
        with open('project/dict_gpt.txt', 'w', encoding='utf-8') as f:
            f.write(self.master.gpt_dict.toPlainText())

        # save after dict
        with open('project/dict_after.txt', 'w', encoding='utf-8') as f:
            f.write(self.master.after_dict.toPlainText())

        self.status.emit(t("[INFO] 配置保存完成！"))

    @error_handler
    def vocal_split(self):
        self.save_config()
        uvr_file = get_combo_value(self.master.uvr_file)
        if not uvr_file.endswith('.onnx'):
            self.status.emit(t("[ERROR] 请选择正确的UVR模型文件！"))
            self.finished.emit()
            return

        input_files = self.master.uvr_file_list.toPlainText()
        if input_files:
            input_files = input_files.strip().split('\n')
            for idx, input_file in enumerate(input_files):
                if not os.path.exists(input_file):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=input_file))
                    self.finished.emit()

                self.status.emit(t("[INFO] 正在进行伴奏分离...第{idx}个，共{total}个").format(idx=idx+1, total=len(input_files)))
                self.pid = subprocess.Popen(['uvr/separate.exe', '-m', os.path.join('uvr',uvr_file), input_file], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()

            self.status.emit(t("[INFO] 文件处理完成！"))
        self.finished.emit()

    @error_handler
    def summarize(self):
        self.save_config()
        input_files = self.master.summarize_files_list.toPlainText()
        address = self.master.summarize_address.text()
        model = self.master.summarize_model.text()
        token = self.master.summarize_token.text()
        prompt = self.master.summarize_prompt.toPlainText()
        if input_files:
            input_files = input_files.strip().split('\n')
            for idx, input_file in enumerate(input_files):
                if not os.path.exists(input_file):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=input_file))
                    self.finished.emit()

                from summarize import summarize
                self.status.emit(t("[INFO] 正在进行文本摘要...第{idx}个，共{total}个").format(idx=idx+1, total=len(input_files)))
                summarize(input_file, address, model, token, prompt)
            self.status.emit(t("[INFO] 文件处理完成！"))
        self.finished.emit()

    @error_handler
    def split(self):
        self.save_config()
        input_files = self.master.split_files_list.toPlainText()
        split_mode = self.master.split_mode.value()
        if input_files:
            input_files = input_files.strip().split('\n')
            for idx, input_file in enumerate(input_files):
                if not os.path.exists(input_file):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=input_file))
                    self.finished.emit()

                self.status.emit(t("[INFO] 当前处理文件：{input_file} 第{idx}个，共{total}个").format(input_file=input_file, idx=idx+1, total=len(input_files)))
                os.makedirs(os.path.join(*(input_file.split('.')[:-1])), exist_ok=True)

                self.status.emit(t("[INFO] 正在进行音频提取...每{split_mode}秒分割一次").format(split_mode=split_mode))
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-i', input_file,  '-f', 'segment', '-segment_time', str(split_mode), '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', os.path.join(*(input_file.split('.')[:-1]+['%04d.wav']))], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()
                self.status.emit(t("[INFO] 音频分割完成！"))
        self.finished.emit()

    @error_handler
    def merge(self):
        self.save_config()
        input_files = self.master.merge_files_list.toPlainText()
        split_mode = self.master.split_mode.value()
        if input_files:
            input_files = sorted(input_files.strip().split('\n'))
            merged_prompt = []
            for idx, input_file in enumerate(input_files):
                if not os.path.exists(input_file):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=input_file))
                    self.finished.emit()

                self.status.emit(t("[INFO] 当前处理文件：{input_file} 第{idx}个，共{total}个").format(input_file=input_file, idx=idx+1, total=len(input_files)))
                prompt = make_prompt(input_file)

                for i in prompt:
                    i['start'] += idx * split_mode
                    i['end'] += idx * split_mode
                    merged_prompt.append(i)

            with open(input_files[0].replace('.srt','_merged.json'), 'w', encoding='utf-8') as f:
                json.dump(merged_prompt, f, ensure_ascii=False, indent=4)
            make_srt(input_files[0].replace('.srt','_merged.json'), input_files[0].replace('.srt','_merged.srt'))
            self.status.emit(t("[INFO] 所有文件处理完成！"))
        self.finished.emit()

    @error_handler
    def synth(self):
        self.save_config()
        input_files = self.master.synth_files_list.toPlainText()
        if input_files:
            input_files = input_files.strip().split('\n')
            srt_files = sorted([i for i in input_files if i.endswith('.srt')])
            video_files = sorted([i for i in input_files if not i.endswith('.srt')])
            if len(srt_files) != len(video_files):
                self.status.emit(t("[ERROR] 字幕文件和视频文件数量不匹配，请重新选择文件！"))
                self.finished.emit()
            
            for idx, (input_file, input_srt) in enumerate(zip(video_files, srt_files)):
                if not os.path.exists(input_file):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=input_file))
                    self.finished.emit()

                if not os.path.exists(input_srt):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=input_srt))
                    self.finished.emit()

                input_srt = shutil.copy(input_srt, 'project/cache/')

                self.status.emit(t("[INFO] 当前处理文件：{input_file} 第{idx}个，共{total}个").format(input_file=input_file, idx=idx+1, total=len(video_files)))
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-i', input_file,  '-vf', f'subtitles={input_srt}', '-vcodec', 'libx264', '-acodec', 'aac', input_file+'_synth.mp4'], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()
                self.status.emit(t("[INFO] 视频合成完成！"))
            
        self.finished.emit()

    @error_handler
    def clip(self):
        self.save_config()
        input_files = self.master.clip_files_list.toPlainText()
        clip_start = self.master.clip_start_time.text()
        clip_end = self.master.clip_end_time.text()
        if input_files:
            input_files = input_files.strip().split('\n')
            for idx, input_file in enumerate(input_files):
                if not os.path.exists(input_file):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=input_file))
                    self.finished.emit()

                self.status.emit(t("[INFO] 当前处理文件：{input_file} 第{idx}个，共{total}个").format(input_file=input_file, idx=idx+1, total=len(input_files)))
                self.status.emit(t("[INFO] 正在进行切片...从{clip_start}到{clip_end}...").format(clip_start=clip_start, clip_end=clip_end))
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-i', input_file, '-ss', clip_start, '-to', clip_end, '-vcodec', 'libx264', '-acodec', 'aac', os.path.join(*(input_file.split('.')[:-1]))+'_clip.'+input_file.split('.')[-1]], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()
                self.status.emit(t("[INFO] 视频切片完成！"))
        self.finished.emit()

    @error_handler
    def audiosynth(self):
        self.save_config()
        input_files = self.master.synth_audio_files_list.toPlainText()
        if input_files:
            input_files = input_files.strip().split('\n')
            audio_files = sorted([i for i in input_files if i.endswith('.wav') or i.endswith('.mp3') or i.endswith('.flac')])
            image_files = sorted([i for i in input_files if i.endswith('.png') or i.endswith('.jpg') or i.endswith('.jpeg')])
            if len(audio_files) != len(image_files):
                self.status.emit(t("[ERROR] 音频文件和图像文件数量不匹配，请重新选择文件！"))
                self.finished.emit()
            
            for idx, (audio_input, image_input) in enumerate(zip(audio_files, image_files)):
                if not os.path.exists(audio_input):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=audio_input))
                    self.finished.emit()

                if not os.path.exists(image_input):
                    self.status.emit(t("[ERROR] {input_file}文件不存在，请重新选择文件！").format(input_file=image_input))
                    self.finished.emit()

                self.status.emit(t("[INFO] 当前处理文件：{input_file} 第{idx}个，共{total}个").format(input_file=audio_input, idx=idx+1, total=len(image_files)))
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-loop', '1', '-r', '1', '-f', 'image2', '-i', image_input, '-i', audio_input, '-shortest', '-vcodec', 'libx264', '-acodec', 'aac', audio_input+'_synth.mp4'], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()
                self.status.emit(t("[INFO] 视频合成完成！"))
            
        self.finished.emit()

    @error_handler
    def run(self):
        self.save_config()
        input_files = self.master.input_files_list.toPlainText()
        yt_url = self.master.yt_url.toPlainText()
        whisper_file = get_combo_value(self.master.whisper_file)
        translator = get_combo_value(self.master.translator_group)
        language = get_combo_value(self.master.input_lang)
        gpt_token = self.master.gpt_token.text()
        gpt_address = self.master.gpt_address.text()
        gpt_model = self.master.gpt_model.text()
        sakura_file = get_combo_value(self.master.sakura_file)
        sakura_mode = self.master.sakura_mode.value()
        proxy_address = self.master.proxy_address.text()
        before_dict = self.master.before_dict.toPlainText()
        gpt_dict = self.master.gpt_dict.toPlainText()
        after_dict = self.master.after_dict.toPlainText()
        extra_prompt = self.master.extra_prompt.toPlainText()
        param_whisper = self.master.param_whisper.toPlainText()
        param_whisper_faster = self.master.param_whisper_faster.toPlainText()
        param_llama = self.master.param_llama.toPlainText()
        output_format = get_combo_value(self.master.output_format)

        if not gpt_token:
            gpt_token = 'sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

        with open('whisper/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_whisper)

        with open('whisper-faster/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_whisper_faster)

        with open('llama/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_llama)

        self.status.emit(t("[INFO] 正在初始化项目文件夹..."))

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
        if extra_prompt:
            with open('project/extra_prompt.txt', 'w', encoding='utf-8') as f:
                f.write(extra_prompt)
        else:
            if os.path.exists('project/extra_prompt.txt'):
                os.remove('project/extra_prompt.txt')

        self.status.emit(t("[INFO] 当前输入文件：{input_files}, 当前视频链接：{yt_url}").format(input_files=input_files, yt_url=yt_url))

        if input_files:
            input_files = input_files.split('\n')
        else:
            input_files = []

        if yt_url:
            input_files.extend(yt_url.split('\n'))

        os.makedirs('project/cache', exist_ok=True)

        self.status.emit(t("[INFO] 正在进行翻译配置..."))
        with open('project/config.yaml', 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for idx, line in enumerate(lines):
            if 'language' in line:
                lines[idx] = f'  language: "{language}2zh-cn"\n'
            if 'gpt' in translator:
                if not gpt_address:
                    gpt_address = 'https://api.openai.com'
                if not gpt_model:
                    gpt_model = ''
                if 'GPT35:' in line:
                    lines[idx+2] = f"      - token: {gpt_token}\n"
                    lines[idx+4] = f"    defaultEndpoint: {gpt_address}\n"
                    lines[idx+5] = f'    rewriteModelName: "{gpt_model}"\n'
            for name, api in ONLINE_TRANSLATOR_MAPPING.items():
                if name == translator:
                    if 'llamacpp' in translator:
                        gpt_model = sakura_file
                    if 'GPT35:' in line:
                        lines[idx+2] = f"      - token: {gpt_token}\n"
                        lines[idx+4] = f"    defaultEndpoint: {api}\n"
                        lines[idx+5] = f'    rewriteModelName: "{gpt_model}"\n'
            if proxy_address:
                if 'proxy' in line:
                    lines[idx+1] = f"  enableProxy: true\n"
                    lines[idx+3] = f"    - address: {proxy_address}\n"
            else:
                if 'proxy' in line:
                    lines[idx+1] = f"  enableProxy: false\n"

        with open('project/config.yaml', 'w', encoding='utf-8') as f:
            f.writelines(lines)

        for idx, input_file in enumerate(input_files):
            if not os.path.exists(input_file):
                if input_file.startswith('BV'):
                    self.status.emit(t("[INFO] 正在下载视频..."))
                    res = send_request(URL_VIDEO_INFO, params={'bvid': input_file})
                    download([Video(
                        bvid=res['bvid'],
                        cid=res['cid'] if res['videos'] == 1 else res['pages'][0]['cid'],
                        title=res['title'] if res['videos'] == 1 else res['pages'][0]['part'],
                        up_name=res['owner']['name'],
                        cover_url=res['pic'] if res['videos'] == 1 else res['pages'][0]['pic'],
                    )], False)
                    self.status.emit(t("[INFO] 视频下载完成！"))
                    title = res['title'] if res['videos'] == 1 else res['pages'][0]['part']
                    title = re.sub(r'[.:?/\\]', ' ', title).strip()
                    title = re.sub(r'\s+', ' ', title)
                    input_file = f'{title}.mp4'

                else:
                    if os.path.exists('YoutubeDL.webm'):
                        os.remove('YoutubeDL.webm')
                    with YoutubeDL({'proxy': proxy_address,'outtmpl': 'YoutubeDL.webm'}) as ydl:
                        self.status.emit(t("[INFO] 正在下载视频..."))
                        results = ydl.download([input_file])
                        self.status.emit(t("[INFO] 视频下载完成！"))
                    input_file = 'YoutubeDL.webm'

                if os.path.exists(os.path.join('project/cache', os.path.basename(input_file))):
                    os.remove(os.path.join('project/cache', os.path.basename(input_file)))
                input_file = shutil.move(input_file, 'project/cache/')

            self.status.emit(t("[INFO] 当前处理文件：{input_file} 第{idx}个，共{total}个").format(input_file=input_file, idx=idx+1, total=len(input_files)))

            os.makedirs('project/gt_input', exist_ok=True)
            if input_file.endswith('.srt'):
                self.status.emit(t("[INFO] 正在进行字幕转换..."))
                output_file_path = os.path.join('project/gt_input', os.path.basename(input_file).replace('.srt','.json'))
                make_prompt(input_file, output_file_path)
                self.status.emit(t("[INFO] 字幕转换完成！"))
                input_file = input_file[:-4]
            else:
                if whisper_file == '不进行听写':
                    self.status.emit(t("[INFO] 不进行听写，跳过听写步骤..."))
                    continue

                wav_file = '.'.join(input_file.split('.')[:-1]) + '.16k.wav'
                self.status.emit(t("[INFO] 正在进行音频提取..."))
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-i', input_file, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', wav_file], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()

                if not os.path.exists(wav_file):
                    self.status.emit(t("[ERROR] 音频提取失败，请检查文件格式！"))
                    break

                self.status.emit(t("[INFO] 正在进行语音识别..."))

                if whisper_file.startswith('ggml'):
                    print(param_whisper)
                    self.pid = subprocess.Popen([param.replace('$whisper_file',whisper_file).replace('$input_file',wav_file[:-4]).replace('$language',language) for param in param_whisper.split()], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                elif whisper_file.startswith('faster-whisper'):
                    print(param_whisper_faster)
                    self.pid = subprocess.Popen([param.replace('$whisper_file',whisper_file[15:]).replace('$input_file',wav_file[:-4]).replace('$language',language).replace('$output_dir',os.path.dirname(input_file)) for param in param_whisper_faster.split()], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                else:
                    self.status.emit(t("[INFO] 不进行听写，跳过听写步骤..."))
                    continue
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()

                input_file = wav_file[:-8]
                output_file_path = os.path.join('project/gt_input', os.path.basename(input_file)+'.json')
                make_prompt(wav_file[:-4]+'.srt', output_file_path)

                if output_format == '原文SRT' or output_format == '双语SRT':
                    make_srt(output_file_path, input_file+'.srt')

                if output_format == '原文LRC' or output_format == '双语LRC':
                    lrc_path = input_file + '.lrc'
                    if output_format == '双语LRC':
                        lrc_path = input_file + '.orig.lrc'
                    make_lrc(output_file_path, lrc_path)

                if os.path.exists(wav_file):
                    os.remove(wav_file)

                if os.path.exists(wav_file[:-4]+'.srt'):
                    os.remove(wav_file[:-4]+'.srt')
                self.status.emit(t("[INFO] 语音识别完成！"))

            if translator == '不进行翻译':
                self.status.emit(t("[INFO] 翻译器未选择，跳过翻译步骤..."))
                continue

            if language == 'zh':
                self.status.emit(t("[INFO] 听写语言为中文，跳过翻译步骤..."))
                continue

            if 'sakura' in translator or 'llamacpp' in translator or 'galtransl' in translator:
                self.status.emit(t("[INFO] 正在启动Llamacpp翻译器..."))
                if not sakura_file:
                    self.status.emit(t("[INFO] 未选择模型文件，跳过翻译步骤..."))
                    continue
                
                print(param_llama)
                self.pid = subprocess.Popen([param.replace('$model_file',sakura_file).replace('$num_layers',str(sakura_mode)).replace('$port', '8989') for param in param_llama.split()], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                
                self.status.emit(t("[INFO] 正在等待Sakura翻译器启动..."))
                while True:
                    try:
                        response = requests.get("http://localhost:8989")
                        if response.status_code == 200:
                            break
                    except requests.exceptions.RequestException:
                        pass
                    sleep(1)

            if 'galtransl' in translator:
                worker_trans = 'sakura-010'
            elif 'sakura' not in translator:
                worker_trans = 'gpt35-1106'
            else:
                worker_trans = translator

            self.status.emit(t("[INFO] 正在进行翻译..."))
            worker('project', 'config.yaml', worker_trans, show_banner=False)

            self.status.emit(t("[INFO] 正在生成字幕文件..."))
            if output_format == '中文SRT' or output_format == '双语SRT':
                make_srt(output_file_path.replace('gt_input','gt_output'), input_file+'.zh.srt')

            if output_format == '中文LRC' or output_format == '双语LRC':
                lrc_path = input_file + '.lrc'
                if output_format == '双语LRC':
                    lrc_path = input_file + '.zh.lrc'
                make_lrc(output_file_path.replace('gt_input','gt_output'), lrc_path)

            if output_format == '双语SRT':
                merge_srt_files([input_file+'.srt',input_file+'.zh.srt'], input_file+'.combine.srt')

            if output_format == '双语LRC':
                merge_lrc_files([input_file+'.orig.lrc', input_file+'.zh.lrc'], input_file+'.combine.lrc')

            self.status.emit(t("[INFO] 字幕文件生成完成！"))

            if 'sakura' in translator or 'llamacpp' in translator or 'galtransl' in translator:
                self.status.emit(t("[INFO] 正在关闭Llamacpp翻译器..."))
                self.pid.kill()
                self.pid.terminate()

        self.status.emit(t("[INFO] 所有文件处理完成！"))
        self.finished.emit()

if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
