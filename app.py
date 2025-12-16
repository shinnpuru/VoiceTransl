import sys, os

os.chdir(sys._MEIPASS)
import shutil
from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer, QDateTime, QSize
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QFileDialog, QFrame, QMessageBox
from qfluentwidgets import PushButton as QPushButton, TextEdit as QTextEdit, LineEdit as QLineEdit, ComboBox as QComboBox, Slider as QSlider, FluentWindow as QMainWindow, PlainTextEdit as QPlainTextEdit, SplashScreen
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

class Widget(QFrame):

    def __init__(self, text: str, parent=None):
        super().__init__(parent=parent)
        # Set the scroll area as the parent of the widget
        self.vBoxLayout = QVBoxLayout(self)

        # Must set a globally unique object name for the sub-interface
        self.setObjectName(text.replace(' ', '-'))

class ConnectionTestWorker(QThread):
    finished = pyqtSignal(bool, str, int)  # success, message, status_code

    def __init__(self, api_address, headers, data):
        super().__init__()
        self.api_address = api_address
        self.headers = headers
        self.data = data

    def run(self):
        try:
            response = requests.post(self.api_address, headers=self.headers, json=self.data, timeout=15)
            if response.status_code == 200:
                self.finished.emit(True, response.text, response.status_code)
            else:
                self.finished.emit(False, response.text, response.status_code)
        except Exception as e:
            self.finished.emit(False, str(e), 0)

class MainWindow(QMainWindow):
    status = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None
        self.setWindowTitle("VoiceTransl")
        self.setWindowIcon(QtGui.QIcon('icon.png'))
        self.status.connect(lambda x: self.setWindowTitle(f"VoiceTransl - {x}"))
        self.resize(800, 600)
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(102, 102))
        self.show()
        self.initUI()
        self.setup_timer()
        self.splashScreen.finish()
        
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

        # load config
        if os.path.exists('config.txt'):
            with open('config.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
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

                if self.whisper_file: self.whisper_file.setCurrentText(whisper_file)
                self.translator_group.setCurrentText(translator)
                self.input_lang.setCurrentText(language)
                self.gpt_token.setText(gpt_token)
                self.gpt_address.setText(gpt_address)
                self.gpt_model.setText(gpt_model)
                if self.sakura_file: self.sakura_file.setCurrentText(sakura_file)
                self.sakura_mode.setValue(sakura_mode)
                self.proxy_address.setText(proxy_address)
                self.summarize_address.setText(summary_address)
                self.summarize_model.setText(summary_model)
                self.summarize_token.setText(summary_token)
                if self.uvr_file: self.uvr_file.setCurrentText(uvr_file)
                self.output_format.setCurrentText(output_format)

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
                    self.log_display.setPlainText(f"[{timestamp}] 错误: 日志文件 '{LOG_PATH}' 未找到。正在等待文件创建...\n")
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
                    self.log_display.appendPlainText(f"\n[{timestamp}] 检测到日志文件截断或轮转。从头开始读取...\n")
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
                self.log_display.setPlainText(f"[{timestamp}] 错误: 日志文件 '{LOG_PATH}' 再次检查时未找到。\n")
                self.file_not_found_message_shown = True
            self.last_read_position = 0
        except IOError as e:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            self.log_display.appendPlainText(f"[{timestamp}] 读取日志文件IO错误: {e}\n")
            # 可以考虑在IO错误时停止timer或做其他处理
        except Exception as e:
            timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
            self.log_display.appendPlainText(f"[{timestamp}] 读取日志文件时发生未知错误: {e}\n")

    def closeEvent(self, event):
        """确保在关闭窗口时停止定时器"""
        self.timer.stop()
        event.accept()

    def initLogTab(self):
        self.log_tab = Widget("Log", self)
        self.log_layout = self.log_tab.vBoxLayout
        self.log_layout.addWidget(BodyLabel("📜 日志文件"))

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
        self.about_layout.addWidget(TitleLabel("🎉 感谢使用VoiceTransl！"))
        self.introduce_text = QTextEdit()
        self.introduce_text.setReadOnly(True)
        self.introduce_text.setPlainText(
"""
VoiceTransl（原Galtransl for ASMR）是一个开源免费的离线AI视频字幕生成和翻译软件，您可以使用本程序从外语音视频文件/字幕文件生成中文字幕文件。

项目地址及使用说明: https://github.com/shinnpuru/VoiceTransl。
B站教程：https://space.bilibili.com/36464441/lists/3239068。
""")
        self.about_layout.addWidget(self.introduce_text)

        # mode
        self.about_layout.addWidget(TitleLabel("🔧 模式说明"))
        self.mode_text = QTextEdit()
        self.mode_text.setReadOnly(True)
        self.mode_text.setPlainText(
"""
（1）仅下载模式：选择不进行听写和不进行翻译；
（2）仅听写模式：选择听写模型，选择不进行翻译；
（3）仅翻译模式：上传SRT文件，并且选择翻译模型；  
（4）完整模式：选择所有功能。
""")
        self.about_layout.addWidget(self.mode_text)

        # disclaimer
        self.about_layout.addWidget(TitleLabel("🎇 支持昕蒲"))
        self.disclaimer_text = QTextEdit()
        self.disclaimer_text.setReadOnly(True)
        self.disclaimer_text.setPlainText(
"""
如果您喜欢这个项目并希望支持开发，欢迎通过以下方式赞助：
1. 爱发电: https://afdian.com/a/shinnpuru（微信和支付宝）
2. B站充电: https://space.bilibili.com/36464441（大会员可用免费B币）
3. Ko-fi: https://ko-fi.com/U7U018MISY（PayPal及信用卡）
您的支持将帮助昕蒲持续改进和维护这个项目！
""")
        self.about_layout.addWidget(self.disclaimer_text)

        # start
        self.start_button = QPushButton("🚀 开始")
        self.start_button.clicked.connect(lambda: self.switchTo(self.input_output_tab))
        self.about_layout.addWidget(self.start_button)

        self.addSubInterface(self.about_tab, FluentIcon.HEART, "关于", NavigationItemPosition.TOP)
        
    def initInputOutputTab(self):
        self.input_output_tab = Widget("Home", self)
        self.input_output_layout = self.input_output_tab.vBoxLayout
        
        # Input Section
        self.input_output_layout.addWidget(BodyLabel("📂 请拖拽音视频文件/SRT文件到这里，可多选，路径请勿包含非英文和空格。"))
        self.input_files_list = QTextEdit()
        self.input_files_list.setAcceptDrops(True)
        self.input_files_list.dropEvent = lambda e: self.input_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.input_files_list.setPlaceholderText("当前未选择本地文件...")
        self.input_output_layout.addWidget(self.input_files_list)

        # YouTube URL Section
        self.input_output_layout.addWidget(BodyLabel("🔗 或者输入B站视频BV号或者YouTube及其他视频链接（每行一个）。"))
        self.yt_url = QTextEdit()
        self.yt_url.setAcceptDrops(False)
        self.yt_url.setPlaceholderText("例如：https://www.youtube.com/watch?v=...\n例如：BV1Lxt5e8EJF")
        self.input_output_layout.addWidget(self.yt_url)

        # Proxy Section
        self.input_output_layout.addWidget(BodyLabel("🌐 设置代理地址以便下载视频和翻译。"))
        self.proxy_address = QLineEdit()
        self.proxy_address.setPlaceholderText("例如：http://127.0.0.1:7890，留空为不使用")
        self.input_output_layout.addWidget(self.proxy_address)

        # Format Section
        self.input_output_layout.addWidget(BodyLabel("🎥 选择输出的字幕格式。"))
        self.output_format = QComboBox()
        self.output_format.addItems(['原文SRT', '原文LRC', '中文LRC', '双语LRC', '中文SRT', '双语SRT'])
        self.output_format.setCurrentText('中文SRT')
        self.input_output_layout.addWidget(self.output_format)

        self.run_button = QPushButton("🚀 运行")
        self.run_button.clicked.connect(self.run_worker)
        self.input_output_layout.addWidget(self.run_button)

        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.output_text_edit.setPlaceholderText("当前无输出信息...")
        self.status.connect(self.output_text_edit.append)
        self.input_output_layout.addWidget(self.output_text_edit)

        self.open_output_button = QPushButton("📁 打开下载和缓存文件夹")
        self.open_output_button.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'project/cache')))
        self.input_output_layout.addWidget(self.open_output_button)
        
        self.clean_button = QPushButton("🧹 清空下载和缓存")
        self.clean_button.clicked.connect(self.cleaner)
        self.input_output_layout.addWidget(self.clean_button)
        
        self.addSubInterface(self.input_output_tab, FluentIcon.HOME, "主页", NavigationItemPosition.TOP)

    def initDictTab(self):
        self.dict_tab = Widget("Dict", self)
        self.dict_layout = self.dict_tab.vBoxLayout

        self.dict_layout.addWidget(BodyLabel("📚 配置翻译前的字典。"))
        self.before_dict = QTextEdit()
        self.before_dict.setPlaceholderText("日文原文(Tab键)日文替换词\n日文原文(Tab键)日文替换词")
        self.dict_layout.addWidget(self.before_dict)
        
        self.dict_layout.addWidget(BodyLabel("📚 配置翻译中的字典。"))
        self.gpt_dict = QTextEdit()
        self.gpt_dict.setPlaceholderText("日文(Tab键)中文\n日文(Tab键)中文")
        self.dict_layout.addWidget(self.gpt_dict)
        
        self.dict_layout.addWidget(BodyLabel("📚 配置翻译后的字典。"))
        self.after_dict = QTextEdit()
        self.after_dict.setPlaceholderText("中文原文(Tab键)中文替换词\n中文原文(Tab键)中文替换词")
        self.dict_layout.addWidget(self.after_dict)

        self.dict_layout.addWidget(BodyLabel("📕 配置额外提示。"))
        self.extra_prompt = QTextEdit()
        self.extra_prompt.setPlaceholderText("请在这里输入额外的提示信息，例如世界书或台本内容。")
        self.dict_layout.addWidget(self.extra_prompt)

        self.addSubInterface(self.dict_tab, FluentIcon.DICTIONARY, "字典设置", NavigationItemPosition.TOP)
        
    def initSettingsTab(self):
        self.settings_tab = Widget("Settings", self)
        self.settings_layout = self.settings_tab.vBoxLayout
        
        # Whisper Section
        self.settings_layout.addWidget(BodyLabel("🗣️ 选择用于语音识别的模型文件。"))
        self.whisper_file = QComboBox()
        whisper_lst = [i for i in os.listdir('whisper') if i.startswith('ggml') and i.endswith('bin') and not 'silero' in i] + [i for i in os.listdir('whisper-faster') if i.startswith('faster-whisper')] + ['不进行听写']
        self.whisper_file.addItems(whisper_lst)
        self.settings_layout.addWidget(self.whisper_file)

        self.settings_layout.addWidget(BodyLabel("🌍 选择输入的语言。(ja=日语，en=英语，ko=韩语，ru=俄语，fr=法语，zh=中文，仅听写）"))
        self.input_lang = QComboBox()
        self.input_lang.addItems(['ja','en','ko','ru','fr','zh'])
        self.settings_layout.addWidget(self.input_lang)

        self.open_whisper_dir = QPushButton("📁 打开Whisper目录")
        self.open_whisper_dir.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'whisper')))
        self.open_faster_dir = QPushButton("📁 打开Faster Whisper目录")
        self.open_faster_dir.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'whisper-faster')))
        self.settings_layout.addWidget(self.open_whisper_dir)
        self.settings_layout.addWidget(self.open_faster_dir)

        self.settings_layout.addWidget(BodyLabel("🔧 输入Whisper命令行参数。"))
        self.param_whisper = QTextEdit()
        self.param_whisper.setPlaceholderText("每个参数空格隔开，请参考Whisper.cpp，不清楚请保持默认。")
        self.settings_layout.addWidget(self.param_whisper)

        self.settings_layout.addWidget(BodyLabel("🔧 输入Whisper-Faster命令行参数。"))
        self.param_whisper_faster = QTextEdit()
        self.param_whisper_faster.setPlaceholderText("每个参数空格隔开，请参考Faster Whisper文档，不清楚请保持默认。")
        self.settings_layout.addWidget(self.param_whisper_faster)

        self.addSubInterface(self.settings_tab, FluentIcon.MUSIC, "听写设置", NavigationItemPosition.TOP)

    def initAdvancedSettingTab(self):
        self.advanced_settings_tab = Widget("AdvancedSettings", self)
        self.advanced_settings_layout = self.advanced_settings_tab.vBoxLayout

        # Translator Section
        self.advanced_settings_layout.addWidget(BodyLabel("🚀 选择用于翻译的模型类别。"))
        self.translator_group = QComboBox()
        self.translator_group.addItems(TRANSLATOR_SUPPORTED)
        self.advanced_settings_layout.addWidget(self.translator_group)
        
        self.advanced_settings_layout.addWidget(BodyLabel("🚀 在线模型令牌"))
        self.gpt_token = QLineEdit()
        self.gpt_token.setPlaceholderText("留空为使用上次配置的Token。")
        self.advanced_settings_layout.addWidget(self.gpt_token)

        self.advanced_settings_layout.addWidget(BodyLabel("🚀 在线模型名称"))
        self.gpt_model = QLineEdit()
        self.gpt_model.setPlaceholderText("例如：deepseek-chat")
        self.advanced_settings_layout.addWidget(self.gpt_model)

        self.advanced_settings_layout.addWidget(BodyLabel("🚀 自定义API地址（gpt-custom）"))
        self.gpt_address = QLineEdit()
        self.gpt_address.setPlaceholderText("例如：http://127.0.0.1:11434")
        self.advanced_settings_layout.addWidget(self.gpt_address)

        self.test_connection_btn = QPushButton("📶 测试连接")
        self.test_connection_btn.clicked.connect(self.test_connection)
        self.advanced_settings_layout.addWidget(self.test_connection_btn)
        
        self.advanced_settings_layout.addWidget(BodyLabel("💻 离线模型文件（galtransl， sakura，llamacpp）"))
        self.sakura_file = QComboBox()
        sakura_lst = [i for i in os.listdir('llama') if i.endswith('gguf')]
        self.sakura_file.addItems(sakura_lst)
        self.advanced_settings_layout.addWidget(self.sakura_file)
        
        self.advanced_settings_layout.addWidget(BodyLabel("💻 离线模型参数（galtransl， sakura，llamacpp）"))
        self.sakura_value = QLineEdit()
        self.sakura_value.setPlaceholderText("100")
        self.sakura_value.setReadOnly(True)
        self.advanced_settings_layout.addWidget(self.sakura_value)
        self.sakura_mode = QSlider(Qt.Horizontal)
        self.sakura_mode.setRange(0, 100)
        self.sakura_mode.setValue(100)
        self.sakura_mode.valueChanged.connect(lambda: self.sakura_value.setText(str(self.sakura_mode.value())))
        self.advanced_settings_layout.addWidget(self.sakura_mode)

        self.open_model_dir = QPushButton("📁 打开离线模型目录")
        self.open_model_dir.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'llama')))
        self.advanced_settings_layout.addWidget(self.open_model_dir)

        self.advanced_settings_layout.addWidget(BodyLabel("🔧 输入Llama.cpp命令行参数。"))
        self.param_llama = QTextEdit()
        self.param_llama.setPlaceholderText("每个参数空格隔开，请参考Llama.cpp文档，不清楚请保持默认。")
        self.advanced_settings_layout.addWidget(self.param_llama)

        self.addSubInterface(self.advanced_settings_tab, FluentIcon.BOOK_SHELF, "翻译设置", NavigationItemPosition.TOP)

    def initClipTab(self):
        self.clip_tab = Widget("Clip", self)
        self.clip_layout = self.clip_tab.vBoxLayout

        # Split Section
        self.clip_layout.addWidget(BodyLabel("🔪 分割合并工具"))
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
        self.split_files_list.setPlaceholderText("拖拽文件到方框内，点击运行即可，每个文件生成一个文件夹，滑动条数字代表切割每段音频的长度（秒）。")
        self.clip_layout.addWidget(self.split_files_list)
        self.run_split_button = QPushButton("🚀 分割")
        self.run_split_button.clicked.connect(self.run_split)
        self.clip_layout.addWidget(self.run_split_button)

        self.merge_files_list = QTextEdit()
        self.merge_files_list.setAcceptDrops(True)
        self.merge_files_list.dropEvent = lambda e: self.merge_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.merge_files_list.setPlaceholderText("拖拽多个字幕文件到方框内，点击运行即可，每次合并成一个文件。时间戳按照上面滑动条分割的时间累加。")
        self.clip_layout.addWidget(self.merge_files_list)
        self.run_merge_button = QPushButton("🚀 合并")
        self.run_merge_button.clicked.connect(self.run_merge)
        self.clip_layout.addWidget(self.run_merge_button)

        # Clip Section
        self.clip_layout.addWidget(BodyLabel("✂️ 切片工具"))
        self.clip_files_list = QTextEdit()
        self.clip_files_list.setAcceptDrops(True)
        self.clip_files_list.dropEvent = lambda e: self.clip_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.clip_files_list.setPlaceholderText("拖拽视频文件到方框内，并填写开始和结束时间，点击运行即可。")
        self.clip_layout.addWidget(self.clip_files_list)
        self.clip_start_time = QLineEdit()
        self.clip_start_time.setPlaceholderText("开始时间（HH:MM:SS.xxx）")
        self.clip_layout.addWidget(self.clip_start_time)
        self.clip_end_time = QLineEdit()
        self.clip_end_time.setPlaceholderText("结束时间（HH:MM:SS.xxx）")
        self.clip_layout.addWidget(self.clip_end_time)
        self.run_clip_button = QPushButton("🚀 切片")
        self.run_clip_button.clicked.connect(self.run_clip)
        self.clip_layout.addWidget(self.run_clip_button)
        
        self.addSubInterface(self.clip_tab, FluentIcon.TILES, "分割工具", NavigationItemPosition.TOP)

    def initSynthTab(self):
        self.synth_tab = Widget("Synth", self)
        self.synth_layout = self.synth_tab.vBoxLayout

        # Vocal Split
        self.synth_layout.addWidget(BodyLabel("🎤 人声分离工具"))
        self.synth_layout.addWidget(BodyLabel("选择用于伴奏分离的模型文件。"))
        self.uvr_file = QComboBox()
        uvr_lst = [i for i in os.listdir('uvr') if i.endswith('onnx')]
        self.uvr_file.addItems(uvr_lst)
        self.synth_layout.addWidget(self.uvr_file)
        self.open_uvr_dir = QPushButton("📁 打开UVR模型目录")
        self.open_uvr_dir.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'uvr')))
        self.synth_layout.addWidget(self.open_uvr_dir)


        self.uvr_file_list = QTextEdit()
        self.uvr_file_list.setAcceptDrops(True)
        self.uvr_file_list.dropEvent = lambda e: self.uvr_file_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.uvr_file_list.setPlaceholderText("拖拽音频文件到方框内，点击运行即可。输出文件为原文件名_vocal.wav和_no_vocal.wav。")
        self.synth_layout.addWidget(self.uvr_file_list)

        self.run_uvr_button = QPushButton("🚀 人声分离")
        self.run_uvr_button.clicked.connect(self.run_vocal_split)
        self.synth_layout.addWidget(self.run_uvr_button)

        # Video Synth
        self.synth_layout.addWidget(BodyLabel("💾 字幕合成工具"))
        self.synth_files_list = QTextEdit()
        self.synth_files_list.setAcceptDrops(True)
        self.synth_files_list.dropEvent = lambda e: self.synth_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.synth_files_list.setPlaceholderText("拖拽字幕文件和视频文件到下方框内，点击运行即可。字幕和视频文件需要一一对应，例如output.mp4和output.mp4.srt。")
        self.synth_layout.addWidget(self.synth_files_list)
        self.run_synth_button = QPushButton("🚀 字幕合成")
        self.run_synth_button.clicked.connect(self.run_synth)
        self.synth_layout.addWidget(self.run_synth_button)

        # Audio Synth
        self.synth_layout.addWidget(BodyLabel("🎵 音频合成工具"))
        self.synth_audio_files_list = QTextEdit()
        self.synth_audio_files_list.setAcceptDrops(True)
        self.synth_audio_files_list.dropEvent = lambda e: self.synth_audio_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.synth_audio_files_list.setPlaceholderText("拖拽音频文件（wav，mp3，flac）和图像（png,jpg,jpeg）到下方框内，点击运行即可。音频和图像文件需要一一对应。")
        self.synth_layout.addWidget(self.synth_audio_files_list)
        self.run_synth_audio_button = QPushButton("🚀 视频合成")
        self.run_synth_audio_button.clicked.connect(self.run_synth_audio)
        self.synth_layout.addWidget(self.run_synth_audio_button)

        self.addSubInterface(self.synth_tab, FluentIcon.DEVELOPER_TOOLS, "合成工具", NavigationItemPosition.TOP)

    def initSummarizeTab(self):
        self.summarize_tab = Widget("Summarize", self)
        self.summarize_layout = self.summarize_tab.vBoxLayout

        self.summarize_layout.addWidget(BodyLabel("🌍 OpenAI兼容地址"))
        self.summarize_address = QLineEdit()
        self.summarize_address.setPlaceholderText("例如：https://api.deepseek.com/v1")
        self.summarize_layout.addWidget(self.summarize_address)

        self.summarize_layout.addWidget(BodyLabel("🚩 模型名称"))
        self.summarize_model = QLineEdit()
        self.summarize_model.setPlaceholderText("例如：deepseek-chat")
        self.summarize_layout.addWidget(self.summarize_model)

        self.summarize_layout.addWidget(BodyLabel("📛 模型令牌"))
        self.summarize_token = QLineEdit()
        self.summarize_layout.addWidget(self.summarize_token)

        self.summarize_layout.addWidget(BodyLabel("🖋️ 模型提示"))
        self.summarize_prompt = QTextEdit()
        self.summarize_prompt.setPlaceholderText("请为以下内容创建一个带有时间戳（mm:ss格式）的粗略摘要，不多于10个事件。请关注关键事件和重要时刻，并确保所有时间戳都采用分钟:秒钟格式。")
        self.summarize_layout.addWidget(self.summarize_prompt)

        self.summarize_layout.addWidget(BodyLabel("📁 输入文件"))
        self.summarize_files_list = QTextEdit()
        self.summarize_files_list.setAcceptDrops(True)
        self.summarize_files_list.dropEvent = lambda e: self.summarize_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.summarize_files_list.setPlaceholderText("拖拽文件到方框内，点击运行即可。输出文件为输入文件名.summary.txt。")
        self.summarize_layout.addWidget(self.summarize_files_list)

        self.run_summarize_button = QPushButton("🚀 运行")
        self.run_summarize_button.clicked.connect(self.run_summarize)
        self.summarize_layout.addWidget(self.run_summarize_button)

        self.addSubInterface(self.summarize_tab, FluentIcon.EDUCATION, "字幕总结", NavigationItemPosition.TOP)
        
    def select_input(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(self, "选择音视频文件/SRT文件", "", "All Files (*);;Video Files (*.mp4 *.webm, *.flv);;SRT Files (*.srt);;Audio Files (*.wav, *.mp3, *.flac)", options=options)
        if files:
            self.input_files_list.setPlainText('\n'.join(files))

    def test_connection(self):
        translator = self.translator_group.currentText()
        token = self.gpt_token.text()
        model = self.gpt_model.text()

        # Helper to show message
        def show_msg(title, text, icon):
            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setText(text)
            msg.setIcon(icon)
            msg.exec_()

        if translator in ['不进行翻译', 'sakura-009', 'sakura-010', 'galtransl']:
             show_msg("提示", "当前选中的模型不支持在线连接测试。", QMessageBox.Information)
             return

        if translator == 'gpt-custom':
            base_url = self.gpt_address.text()
            if not base_url:
                 show_msg("错误", "请输入自定义API地址。", QMessageBox.Warning)
                 return
        else:
            base_url = ONLINE_TRANSLATOR_MAPPING.get(translator)
            if not base_url:
                 show_msg("错误", "未知的在线模型。", QMessageBox.Warning)
                 return

        if not token:
             # Only warn if it's not a custom (local) endpoint which might not need a token
             if translator != 'gpt-custom':
                 show_msg("警告", "Token为空，可能导致连接失败。", QMessageBox.Warning)

        try:
            # Construct URL based on logic in GalTransl/COpenAI.py
            api_address = base_url.rstrip('/') + "/v1/chat/completions"
            if 'bigmodel' in api_address:
                api_address = api_address.replace('v1', 'v4')
            if 'minimax' in api_address:
                api_address = api_address.replace('/chat/completions', '/text/chatcompletion_v2')
            if 'ark.cn' in api_address:
                api_address = api_address.replace('v1', 'v3')
            if 'google' in api_address:
                api_address = api_address.replace('v1', 'v1beta/openai')

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

            self.status.emit(f"[INFO] 正在测试连接... URL: {api_address}")
            self.test_connection_btn.setEnabled(False)
            self.test_connection_btn.setText("正在连接...")

            self.connection_worker = ConnectionTestWorker(api_address, headers, data)

            def on_finished(success, message, status_code):
                self.test_connection_btn.setEnabled(True)
                self.test_connection_btn.setText("📶 测试连接")
                if success:
                    show_msg("成功", f"连接成功！\n响应状态码: {status_code}", QMessageBox.Information)
                    self.status.emit("[INFO] 连接测试成功！")
                else:
                    if status_code == 0: # Exception
                         show_msg("错误", f"连接发生错误: {message}", QMessageBox.Critical)
                         self.status.emit(f"[ERROR] 连接测试错误: {message}")
                    else:
                         show_msg("失败", f"连接失败。\n状态码: {status_code}\n响应: {message}", QMessageBox.Warning)
                         self.status.emit(f"[ERROR] 连接测试失败: {status_code} {message}")

            self.connection_worker.finished.connect(on_finished)
            self.connection_worker.start()

        except Exception as e:
            self.test_connection_btn.setEnabled(True)
            self.test_connection_btn.setText("📶 测试连接")
            show_msg("错误", f"发生错误: {str(e)}", QMessageBox.Critical)
            self.status.emit(f"[ERROR] 连接测试错误: {str(e)}")

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
        self.status.emit("[INFO] 正在清理中间文件...")
        if os.path.exists('project/gt_input'):
            shutil.rmtree('project/gt_input')
        if os.path.exists('project/gt_output'):
            shutil.rmtree('project/gt_output')
        if os.path.exists('project/transl_cache'):
            shutil.rmtree('project/transl_cache')
        self.status.emit("[INFO] 正在清理输出...")
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

    def __init__(self, master):
        super().__init__()
        self.master = master
        self.status = master.status

    @error_handler
    def save_config(self):
        self.status.emit("[INFO] 正在读取配置...")
        whisper_file = self.master.whisper_file.currentText()
        translator = self.master.translator_group.currentText()
        language = self.master.input_lang.currentText()
        gpt_token = self.master.gpt_token.text()
        gpt_address = self.master.gpt_address.text()
        gpt_model = self.master.gpt_model.text()
        sakura_file = self.master.sakura_file.currentText()
        sakura_mode = self.master.sakura_mode.value()
        proxy_address = self.master.proxy_address.text()
        summary_address = self.master.summarize_address.text()
        summary_model = self.master.summarize_model.text()
        summary_token = self.master.summarize_token.text()
        uvr_file = self.master.uvr_file.currentText()
        output_format = self.master.output_format.currentText()

        # save config
        with open('config.txt', 'w', encoding='utf-8') as f:
            f.write(f"{whisper_file}\n{translator}\n{language}\n{gpt_token}\n{gpt_address}\n{gpt_model}\n{sakura_file}\n{sakura_mode}\n{proxy_address}\n{summary_address}\n{summary_model}\n{summary_token}\n{uvr_file}\n{output_format}\n")

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

        self.status.emit("[INFO] 配置保存完成！")

    @error_handler
    def vocal_split(self):
        self.save_config()
        uvr_file = self.master.uvr_file.currentText()
        if not uvr_file.endswith('.onnx'):
            self.status.emit("[ERROR] 请选择正确的UVR模型文件！")
            self.finished.emit()
            return

        input_files = self.master.uvr_file_list.toPlainText()
        if input_files:
            input_files = input_files.strip().split('\n')
            for idx, input_file in enumerate(input_files):
                if not os.path.exists(input_file):
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()

                self.status.emit(f"[INFO] 正在进行伴奏分离...第{idx+1}个，共{len(input_files)}个")
                self.pid = subprocess.Popen(['uvr/separate.exe', '-m', os.path.join('uvr',uvr_file), input_file], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()

            self.status.emit("[INFO] 文件处理完成！")
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
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()

                from summarize import summarize
                self.status.emit(f"[INFO] 正在进行文本摘要...第{idx+1}个，共{len(input_files)}个")
                summarize(input_file, address, model, token, prompt)
            self.status.emit("[INFO] 文件处理完成！")
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
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()

                self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{idx+1}个，共{len(input_files)}个")
                os.makedirs(os.path.join(*(input_file.split('.')[:-1])), exist_ok=True)

                self.status.emit(f"[INFO] 正在进行音频提取...每{split_mode}秒分割一次")
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-i', input_file,  '-f', 'segment', '-segment_time', str(split_mode), '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', os.path.join(*(input_file.split('.')[:-1]+['%04d.wav']))], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()
                self.status.emit("[INFO] 音频分割完成！")
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
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()

                self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{idx+1}个，共{len(input_files)}个")
                prompt = make_prompt(input_file)

                for i in prompt:
                    i['start'] += idx * split_mode
                    i['end'] += idx * split_mode
                    merged_prompt.append(i)

            with open(input_files[0].replace('.srt','_merged.json'), 'w', encoding='utf-8') as f:
                json.dump(merged_prompt, f, ensure_ascii=False, indent=4)
            make_srt(input_files[0].replace('.srt','_merged.json'), input_files[0].replace('.srt','_merged.srt'))
            self.status.emit("[INFO] 所有文件处理完成！")
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
                self.status.emit("[ERROR] 字幕文件和视频文件数量不匹配，请重新选择文件！")
                self.finished.emit()
            
            for idx, (input_file, input_srt) in enumerate(zip(video_files, srt_files)):
                if not os.path.exists(input_file):
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()

                if not os.path.exists(input_srt):
                    self.status.emit(f"[ERROR] {input_srt}文件不存在，请重新选择文件！")
                    self.finished.emit()

                input_srt = shutil.copy(input_srt, 'project/cache/')

                self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{idx+1}个，共{len(video_files)}个")
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-i', input_file,  '-vf', f'subtitles={input_srt}', '-vcodec', 'libx264', '-acodec', 'aac', input_file+'_synth.mp4'], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()
                self.status.emit("[INFO] 视频合成完成！")
            
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
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()

                self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{idx+1}个，共{len(input_files)}个")
                self.status.emit(f"[INFO] 正在进行切片...从{clip_start}到{clip_end}...")
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-i', input_file, '-ss', clip_start, '-to', clip_end, '-vcodec', 'libx264', '-acodec', 'aac', os.path.join(*(input_file.split('.')[:-1]))+'_clip.'+input_file.split('.')[-1]], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()
                self.status.emit("[INFO] 视频切片完成！")
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
                self.status.emit("[ERROR] 音频文件和图像文件数量不匹配，请重新选择文件！")
                self.finished.emit()
            
            for idx, (audio_input, image_input) in enumerate(zip(audio_files, image_files)):
                if not os.path.exists(audio_input):
                    self.status.emit(f"[ERROR] {audio_input}文件不存在，请重新选择文件！")
                    self.finished.emit()

                if not os.path.exists(image_input):
                    self.status.emit(f"[ERROR] {image_input}文件不存在，请重新选择文件！")
                    self.finished.emit()

                self.status.emit(f"[INFO] 当前处理文件：{audio_input} 第{idx+1}个，共{len(image_files)}个")
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-loop', '1', '-r', '1', '-f', 'image2', '-i', image_input, '-i', audio_input, '-shortest', '-vcodec', 'libx264', '-acodec', 'aac', audio_input+'_synth.mp4'], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()
                self.status.emit("[INFO] 视频合成完成！")
            
        self.finished.emit()

    @error_handler
    def run(self):
        self.save_config()
        input_files = self.master.input_files_list.toPlainText()
        yt_url = self.master.yt_url.toPlainText()
        whisper_file = self.master.whisper_file.currentText()
        translator = self.master.translator_group.currentText()
        language = self.master.input_lang.currentText()
        gpt_token = self.master.gpt_token.text()
        gpt_address = self.master.gpt_address.text()
        gpt_model = self.master.gpt_model.text()
        sakura_file = self.master.sakura_file.currentText()
        sakura_mode = self.master.sakura_mode.value()
        proxy_address = self.master.proxy_address.text()
        before_dict = self.master.before_dict.toPlainText()
        gpt_dict = self.master.gpt_dict.toPlainText()
        after_dict = self.master.after_dict.toPlainText()
        extra_prompt = self.master.extra_prompt.toPlainText()
        param_whisper = self.master.param_whisper.toPlainText()
        param_whisper_faster = self.master.param_whisper_faster.toPlainText()
        param_llama = self.master.param_llama.toPlainText()
        output_format = self.master.output_format.currentText()

        if not gpt_token:
            gpt_token = 'sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

        with open('whisper/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_whisper)

        with open('whisper-faster/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_whisper_faster)

        with open('llama/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_llama)

        self.status.emit("[INFO] 正在初始化项目文件夹...")

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

        self.status.emit(f"[INFO] 当前输入文件：{input_files}, 当前视频链接：{yt_url}")

        if input_files:
            input_files = input_files.split('\n')
        else:
            input_files = []

        if yt_url:
            input_files.extend(yt_url.split('\n'))

        os.makedirs('project/cache', exist_ok=True)

        self.status.emit("[INFO] 正在进行翻译配置...")
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
                    self.status.emit("[INFO] 正在下载视频...")
                    res = send_request(URL_VIDEO_INFO, params={'bvid': input_file})
                    download([Video(
                        bvid=res['bvid'],
                        cid=res['cid'] if res['videos'] == 1 else res['pages'][0]['cid'],
                        title=res['title'] if res['videos'] == 1 else res['pages'][0]['part'],
                        up_name=res['owner']['name'],
                        cover_url=res['pic'] if res['videos'] == 1 else res['pages'][0]['pic'],
                    )], False)
                    self.status.emit("[INFO] 视频下载完成！")
                    title = res['title'] if res['videos'] == 1 else res['pages'][0]['part']
                    title = re.sub(r'[.:?/\\]', ' ', title).strip()
                    title = re.sub(r'\s+', ' ', title)
                    input_file = f'{title}.mp4'

                else:
                    if os.path.exists('YoutubeDL.webm'):
                        os.remove('YoutubeDL.webm')
                    with YoutubeDL({'proxy': proxy_address,'outtmpl': 'YoutubeDL.webm'}) as ydl:
                        self.status.emit("[INFO] 正在下载视频...")
                        results = ydl.download([input_file])
                        self.status.emit("[INFO] 视频下载完成！")
                    input_file = 'YoutubeDL.webm'

                if os.path.exists(os.path.join('project/cache', os.path.basename(input_file))):
                    os.remove(os.path.join('project/cache', os.path.basename(input_file)))
                input_file = shutil.move(input_file, 'project/cache/')

            self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{idx+1}个，共{len(input_files)}个")

            os.makedirs('project/gt_input', exist_ok=True)
            if input_file.endswith('.srt'):
                self.status.emit("[INFO] 正在进行字幕转换...")
                output_file_path = os.path.join('project/gt_input', os.path.basename(input_file).replace('.srt','.json'))
                make_prompt(input_file, output_file_path)
                self.status.emit("[INFO] 字幕转换完成！")
                input_file = input_file[:-4]
            else:
                if whisper_file == '不进行听写':
                    self.status.emit("[INFO] 不进行听写，跳过听写步骤...")
                    continue

                wav_file = '.'.join(input_file.split('.')[:-1]) + '.16k.wav'
                self.status.emit("[INFO] 正在进行音频提取...")
                self.pid = subprocess.Popen(['ffmpeg', '-y', '-i', input_file, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', wav_file], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                self.pid.wait()
                self.pid.kill()
                self.pid.terminate()

                if not os.path.exists(wav_file):
                    self.status.emit("[ERROR] 音频提取失败，请检查文件格式！")
                    break

                self.status.emit("[INFO] 正在进行语音识别...")

                if whisper_file.startswith('ggml'):
                    print(param_whisper)
                    self.pid = subprocess.Popen([param.replace('$whisper_file',whisper_file).replace('$input_file',wav_file[:-4]).replace('$language',language) for param in param_whisper.split()], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                elif whisper_file.startswith('faster-whisper'):
                    print(param_whisper_faster)
                    self.pid = subprocess.Popen([param.replace('$whisper_file',whisper_file[15:]).replace('$input_file',wav_file[:-4]).replace('$language',language).replace('$output_dir',os.path.dirname(input_file)) for param in param_whisper_faster.split()], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                else:
                    self.status.emit("[INFO] 不进行听写，跳过听写步骤...")
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
                self.status.emit("[INFO] 语音识别完成！")

            if translator == '不进行翻译':
                self.status.emit("[INFO] 翻译器未选择，跳过翻译步骤...")
                continue

            if language == 'zh':
                self.status.emit("[INFO] 听写语言为中文，跳过翻译步骤...")
                continue

            if 'sakura' in translator or 'llamacpp' in translator or 'galtransl' in translator:
                self.status.emit("[INFO] 正在启动Llamacpp翻译器...")
                if not sakura_file:
                    self.status.emit("[INFO] 未选择模型文件，跳过翻译步骤...")
                    continue
                
                print(param_llama)
                self.pid = subprocess.Popen([param.replace('$model_file',sakura_file).replace('$num_layers',str(sakura_mode)).replace('$port', '8989') for param in param_llama.split()], stdout=sys.stdout, stderr=sys.stdout, creationflags=0x08000000)
                
                self.status.emit("[INFO] 正在等待Sakura翻译器启动...")
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

            self.status.emit("[INFO] 正在进行翻译...")
            worker('project', 'config.yaml', worker_trans, show_banner=False)

            self.status.emit("[INFO] 正在生成字幕文件...")
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

            self.status.emit("[INFO] 字幕文件生成完成！")

            if 'sakura' in translator or 'llamacpp' in translator or 'galtransl' in translator:
                self.status.emit("[INFO] 正在关闭Llamacpp翻译器...")
                self.pid.kill()
                self.pid.terminate()

        self.status.emit("[INFO] 所有文件处理完成！")
        self.finished.emit()

if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
