import sys, os

os.chdir(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else os.chdir(os.path.dirname(os.path.abspath(__file__)))
import shutil
from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer, QDateTime, QSize
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QFileDialog, QFrame, QSystemTrayIcon, QMenu, QAction, QHBoxLayout, QCheckBox
from qfluentwidgets import PushButton as QPushButton, TextEdit as QTextEdit, LineEdit as QLineEdit, ComboBox as QComboBox, Slider as QSlider, FluentWindow as QMainWindow, PlainTextEdit as QPlainTextEdit, SplashScreen
from qfluentwidgets import FluentIcon, NavigationItemPosition, SubtitleLabel, TitleLabel, BodyLabel

import re
import asyncio
import json
import yaml
import requests
import httpx
from openai import OpenAI
import subprocess
from time import sleep, time
from yt_dlp import YoutubeDL
from bilibili_dl.bilibili_dl.Video import Video
from bilibili_dl.bilibili_dl.downloader import download
from bilibili_dl.bilibili_dl.utils import send_request
from bilibili_dl.bilibili_dl.constants import URL_VIDEO_INFO
from pathlib import Path


def open_path(path_value: str):
    target = os.path.abspath(path_value)
    QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(target))

from prompt2srt import make_srt, make_lrc, merge_lrc_files
from srt2prompt import make_prompt, merge_srt_files
from GalTransl.ConfigHelper import CProjectConfig
from GalTransl.Runner import run_galtransl
from GalTransl.Backend.V3 import handle_special_api

ONLINE_TRANSLATOR_MAPPING = {
    'moonshot': 'https://api.moonshot.cn',
    'moonshot (international)': 'https://api.moonshot.ai',
    'glm': 'https://open.bigmodel.cn/api/paas',
    'glm (international)': 'https://api.z.ai/api/paas',
    'deepseek': 'https://api.deepseek.com',
    'minimax': 'https://api.minimaxi.com',
    'minimax (international)': 'https://api.minimaxi.io',
    'doubao': 'https://ark.cn-beijing.volces.com/api',
    'aliyun': 'https://dashscope.aliyuncs.com/compatible-mode',
    'gemini': 'https://generativelanguage.googleapis.com',
    'grok': 'https://api.grok.ai',
    'openai': 'https://api.openai.com',
    'ollama': 'http://localhost:11434',
    'llamacpp': 'http://localhost:8989',
}

TRANSLATOR_SUPPORTED = [
    '不进行翻译',
    "gpt-custom",
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

class MainWindow(QMainWindow):
    status = pyqtSignal(str)

    @staticmethod
    def default_output_dir() -> str:
        return str(Path.cwd() / 'project' / 'cache')

    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None
        self.setWindowTitle("VoiceTransl")
        self.setWindowIcon(QtGui.QIcon('icon.png'))
        self.init_system_tray()
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
        self.initClipTab()
        self.initSynthTab()
        self.initSummarizeTab()
        self.initSettingsTab()
        self.initAdvancedSettingTab()
        self.initDictTab()
        self.initLogTab()
        self.load_config()

    def browse_synth_video(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择视频文件", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.flv);;All Files (*)")
        if files:
            current_text = self.synth_video_files_list.toPlainText().strip()
            new_text = "\n".join(files)
            if current_text:
                self.synth_video_files_list.setText(current_text + "\n" + new_text)
            else:
                self.synth_video_files_list.setText(new_text)

    def browse_synth_srt(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择字幕文件", "", "Subtitle Files (*.srt *.ass *.vtt);;All Files (*)")
        if files:
            current_text = self.synth_srt_files_list.toPlainText().strip()
            new_text = "\n".join(files)
            if current_text:
                self.synth_srt_files_list.setText(current_text + "\n" + new_text)
            else:
                self.synth_srt_files_list.setText(new_text)

    def browse_output_dir(self):
        current_dir = self.output_dir_edit.text().strip() or self.default_output_dir()
        selected = QFileDialog.getExistingDirectory(self, "选择输出目录", current_dir)
        if selected:
            self.output_dir_edit.setText(selected)

    def update_output_dir_controls(self):
        use_input_dir = self.use_input_dir_checkbox.isChecked() if hasattr(self, 'use_input_dir_checkbox') else False
        self.output_dir_edit.setEnabled(not use_input_dir)
        self.output_dir_button.setEnabled(not use_input_dir)

    def _normalize_drop_paths(self, mime_data):
        paths = []
        try:
            urls = mime_data.urls()
        except Exception:
            urls = []

        if urls:
            for url in urls:
                if url.isLocalFile():
                    local_path = url.toLocalFile()
                    if local_path:
                        paths.append(local_path)
            return paths

        raw_text = mime_data.text() or ""
        if not raw_text:
            return paths

        for item in raw_text.splitlines():
            item = item.strip()
            if not item:
                continue
            if item.startswith("file://"):
                url = QtCore.QUrl(item)
                local_path = url.toLocalFile()
                if local_path:
                    paths.append(local_path)
                continue
            paths.append(item)
        return paths

    def _bind_drop_event(self, text_edit):
        def _on_drop(event):
            paths = self._normalize_drop_paths(event.mimeData())
            if paths:
                text_edit.setPlainText("\n".join(paths))
        text_edit.dropEvent = _on_drop

    def collect_font_candidates(self):
        # Scan ./font and common system font dirs for ttf/ttc/otf files
        candidates = []
        exts = {'.ttf', '.ttc', '.otf'}
        search_dirs = []
        # Windows fonts
        win_font_dir = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
        search_dirs.append(win_font_dir)
        # macOS
        search_dirs.extend([Path('/Library/Fonts'), Path.home() / 'Library/Fonts'])
        # Linux common
        search_dirs.extend([Path('/usr/share/fonts'), Path('/usr/local/share/fonts'), Path.home() / '.fonts'])

        for d in search_dirs:
            if not d.exists():
                continue
            for p in d.rglob('*'):
                if p.suffix.lower() in exts:
                    candidates.append(p.stem)  # also add family name guess

        # de-duplicate while preserving order
        seen = set()
        unique = []
        for item in candidates:
            if item in seen:
                continue
            seen.add(item)
            unique.append(item)
        return unique

    def load_config(self):
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
                sakura_mode = lines[7].strip()
                proxy_address = lines[8].strip()
                uvr_file = lines[9].strip()
                output_format = lines[10].strip()
                subtitle_font = lines[11].strip() if len(lines) > 11 else ""
                output_dir = lines[12].strip() if len(lines) > 12 else self.default_output_dir()
                use_input_dir = (lines[13].strip().lower() == 'true') if len(lines) > 13 else False

                if self.whisper_file: self.whisper_file.setCurrentText(whisper_file)
                self.translator_group.setCurrentText(translator)
                self.input_lang.setCurrentText(language)
                self.gpt_token.setText(gpt_token)
                self.gpt_address.setText(gpt_address)
                self.gpt_model.setText(gpt_model)
                if self.sakura_file: self.sakura_file.setCurrentText(sakura_file)
                self.sakura_mode.setText(sakura_mode)
                self.proxy_address.setText(proxy_address)
                if self.uvr_file: self.uvr_file.setCurrentText(uvr_file)
                self.output_format.setCurrentText(output_format)
                if subtitle_font:
                    self.subtitle_font_combo.setCurrentText(subtitle_font)
                self.output_dir_edit.setText(output_dir)
                self.use_input_dir_checkbox.setChecked(use_input_dir)

        if not self.output_dir_edit.text().strip():
            self.output_dir_edit.setText(self.default_output_dir())

        self.update_output_dir_controls()

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

    def init_system_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = None
            return

        self.tray_icon = QSystemTrayIcon(self.windowIcon(), self)
        self.tray_icon.setToolTip("VoiceTransl")

        tray_menu = QMenu(self)
        action_restore = QAction("显示主界面", self)
        action_quit = QAction("退出", self)
        action_restore.triggered.connect(self.restore_from_tray)
        action_quit.triggered.connect(QApplication.instance().quit)

        tray_menu.addAction(action_restore)
        tray_menu.addSeparator()
        tray_menu.addAction(action_quit)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def restore_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.restore_from_tray()

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
        """确保在关闭窗口时停止定时器并关闭子进程"""
        self.timer.stop()
        self.shutdown_children()
        if getattr(self, 'tray_icon', None):
            self.tray_icon.hide()
        event.accept()

    def shutdown_children(self):
        """关闭后台线程和子进程"""
        try:
            if self.worker:
                self.worker.stop()
        except Exception:
            pass

        try:
            if self.thread and self.thread.isRunning():
                self.thread.quit()
                if not self.thread.wait(2000):
                    self.thread.terminate()
                    self.thread.wait(2000)
        except Exception:
            pass

    def changeEvent(self, event):
        # Hide window instead of cluttering the taskbar when minimized
        super().changeEvent(event)
        if event.type() == QtCore.QEvent.WindowStateChange and self.isMinimized():
            if getattr(self, 'tray_icon', None):
                QTimer.singleShot(0, self.hide)
                self.tray_icon.showMessage("VoiceTransl", "程序已最小化到托盘", QSystemTrayIcon.Information, 2000)

    def initLogTab(self):
        self.log_tab = Widget("Log", self)
        self.log_layout = self.log_tab.vBoxLayout

        self.log_layout.addWidget(BodyLabel("🖥️ 实时输出信息"))

        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.output_text_edit.setPlaceholderText("当前无输出信息...")
        self.status.connect(self.output_text_edit.append)
        self.log_layout.addWidget(self.output_text_edit)

        self.log_layout.addWidget(BodyLabel("📜 日志文件"))

        # log
        self.log_display = QPlainTextEdit(self)
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("font-family: Consolas, Monospace; font-size: 10pt;") # 设置等宽字体
        self.log_layout.addWidget(self.log_display)

        # open log file button
        self.open_log_button = QPushButton("📂 打开日志文件")
        self.open_log_button.clicked.connect(lambda: open_path(LOG_PATH))
        self.log_layout.addWidget(self.open_log_button)

        self.addSubInterface(self.log_tab, FluentIcon.INFO, "日志", NavigationItemPosition.TOP)

    def initAboutTab(self):
        self.about_tab = Widget("About", self)
        self.about_layout = self.about_tab.vBoxLayout

        # introduce
        self.about_layout.addWidget(TitleLabel("🎉 感谢使用VoiceTransl！"))

        # mode
        self.mode_text = QTextEdit()
        self.mode_text.setReadOnly(True)
        self.mode_text.setPlainText(
"""
VoiceTrans是一站式离线AI视频字幕生成和翻译软件，功能包括视频下载，音频提取，听写打轴，字幕翻译，视频合成，字幕总结。

界面介绍：
- 关于：查看软件介绍和支持方式。
- 输入输出：输入音视频文件路径或视频链接，设置代理和输出格式，运行生成字幕。
- 分离工具：分离视频中的人声和伴奏，切分音频文件。
- 合成工具：将音频和图片合成为视频，将字幕文件加入视频。
- 总结工具：对字幕文件内容进行总结，生成带时间戳的摘要。
- 语音模型：选择Whisper或Faster Whisper模型，设置听写语言和参数，选择伴奏分离模型。
- 语言模型：选择翻译模型类别，配置在线模型令牌、地址和名称。
- 字典设置：配置翻译前、中、后使用的字典，以及额外提示信息。
- 日志：实时查看输出信息和日志文件。
""")
        self.about_layout.addWidget(self.mode_text)

        # wiki button
        self.btn_wiki = QPushButton("📖 查看使用说明和更新日志")
        self.btn_wiki.clicked.connect(lambda: open_url("https://github.com/shinnpuru/VoiceTransl/wiki"))
        self.about_layout.addWidget(self.btn_wiki)

        # sponsorship buttons
        self.about_layout.addWidget(TitleLabel("🎇 支持昕蒲"))
        btn_layout = QHBoxLayout()
        self.btn_afdian = QPushButton("⚡ 爱发电（微信和支付宝）")
        self.btn_bilibili = QPushButton("⚡ B站充电（免费B币）")
        self.btn_kofi = QPushButton("⚡ Ko-fi（Paypal和信用卡）")

        def open_url(url):
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

        self.btn_afdian.clicked.connect(lambda: open_url("https://afdian.com/a/shinnpuru"))
        self.btn_bilibili.clicked.connect(lambda: open_url("https://space.bilibili.com/36464441"))
        self.btn_kofi.clicked.connect(lambda: open_url("https://ko-fi.com/U7U018MISY"))

        btn_layout.addWidget(self.btn_afdian)
        btn_layout.addWidget(self.btn_bilibili)
        btn_layout.addWidget(self.btn_kofi)
        self.about_layout.addLayout(btn_layout)

        # start
        self.start_button = QPushButton("🚀 开始")
        self.start_button.clicked.connect(lambda: self.switchTo(self.input_output_tab))
        self.about_layout.addWidget(self.start_button)

        self.addSubInterface(self.about_tab, FluentIcon.HEART, "关于", NavigationItemPosition.TOP)
        
    def initInputOutputTab(self):
        self.input_output_tab = Widget("Home", self)
        self.input_output_layout = self.input_output_tab.vBoxLayout
        
        # Input Section (local files or URLs)
        self.input_output_layout.addWidget(BodyLabel("📂 拖拽音视频/SRT文件，或输入B站BV号、YouTube及其他视频链接（每行一个）。路径请勿包含非英文和空格。"))
        self.input_files_list = QTextEdit()
        self.input_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.input_files_list)
        self.input_files_list.setPlaceholderText("例如：C:/video.mp4或https://www.youtube.com/watch?v=...或BV1Lxt5e8EJF")
        self.input_output_layout.addWidget(self.input_files_list)

        # Proxy Section
        self.input_output_layout.addWidget(BodyLabel("🌐 设置代理地址以便下载视频和翻译。"))
        self.proxy_address = QLineEdit()
        self.proxy_address.setPlaceholderText("例如：http://127.0.0.1:7890，留空为不使用")
        self.input_output_layout.addWidget(self.proxy_address)

        # Output Directory Section
        self.input_output_layout.addWidget(BodyLabel("📁 设置输出目录（下载文件与生成字幕）。"))
        output_dir_layout = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(self.default_output_dir())
        self.output_dir_edit.setText(self.default_output_dir())
        output_dir_layout.addWidget(self.output_dir_edit)
        self.output_dir_button = QPushButton("📂 选择目录")
        self.output_dir_button.clicked.connect(self.browse_output_dir)
        output_dir_layout.addWidget(self.output_dir_button)
        self.input_output_layout.addLayout(output_dir_layout)

        self.use_input_dir_checkbox = QCheckBox("输出到音频目录（每个文件输出到其所在目录）")
        self.use_input_dir_checkbox.stateChanged.connect(self.update_output_dir_controls)
        self.input_output_layout.addWidget(self.use_input_dir_checkbox)

        # Format Section
        self.input_output_layout.addWidget(BodyLabel("🎥 选择输出的字幕格式。"))
        self.output_format = QComboBox()
        self.output_format.addItems(['原文SRT', '原文LRC', '中文LRC', '双语LRC', '中文SRT', '双语SRT'])
        self.output_format.setCurrentText('中文SRT')
        self.input_output_layout.addWidget(self.output_format)

        button_layout = QHBoxLayout()
        self.run_button = QPushButton("🚀 运行")
        self.run_button.clicked.connect(self.run_worker)
        button_layout.addWidget(self.run_button)

        self.open_output_button = QPushButton("📁 打开输出目录")
        self.open_output_button.clicked.connect(lambda: open_path(self.output_dir_edit.text().strip() or self.default_output_dir()))
        button_layout.addWidget(self.open_output_button)

        self.clean_button = QPushButton("🧹 清空下载和缓存")
        self.clean_button.clicked.connect(self.cleaner)
        button_layout.addWidget(self.clean_button)

        # Add the button row layout to the input output layout
        self.input_output_layout.addLayout(button_layout)
        
        self.addSubInterface(self.input_output_tab, FluentIcon.HOME, "输入输出", NavigationItemPosition.TOP)

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

        self.addSubInterface(self.dict_tab, FluentIcon.SETTING, "字典设置", NavigationItemPosition.TOP)
        
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

        self.settings_layout.addWidget(BodyLabel("🔧 输入Whisper命令行参数。(CPU，A卡，I卡，Mac，Linux)"))
        self.param_whisper = QTextEdit()
        self.param_whisper.setPlaceholderText("每个参数空格隔开，请参考Whisper.cpp，不清楚请保持默认。")
        self.settings_layout.addWidget(self.param_whisper)

        self.settings_layout.addWidget(BodyLabel("🔧 输入Whisper-Faster命令行参数。(N卡)"))
        self.param_whisper_faster = QTextEdit()
        self.param_whisper_faster.setPlaceholderText("每个参数空格隔开，请参考Faster Whisper文档，不清楚请保持默认。")
        self.settings_layout.addWidget(self.param_whisper_faster)

        self.open_whisper_dir = QPushButton("📁 打开Whisper目录")
        self.open_whisper_dir.clicked.connect(lambda: open_path(os.path.join(os.getcwd(),'whisper')))
        self.open_faster_dir = QPushButton("📁 打开Faster Whisper目录")
        self.open_faster_dir.clicked.connect(lambda: open_path(os.path.join(os.getcwd(),'whisper-faster')))
        self.settings_layout.addWidget(self.open_whisper_dir)
        self.settings_layout.addWidget(self.open_faster_dir)

        # UVR models move into speech settings for consistency
        self.settings_layout.addWidget(BodyLabel("🎤 选择用于伴奏分离的模型文件。"))
        self.uvr_file = QComboBox()
        uvr_lst = [i for i in os.listdir('uvr') if i.endswith('onnx')]
        self.uvr_file.addItems(uvr_lst)
        self.settings_layout.addWidget(self.uvr_file)
        self.open_uvr_dir = QPushButton("📁 打开UVR模型目录")
        self.open_uvr_dir.clicked.connect(lambda: open_path(os.path.join(os.getcwd(),'uvr')))
        self.settings_layout.addWidget(self.open_uvr_dir)

        self.addSubInterface(self.settings_tab, FluentIcon.SETTING, "语音模型", NavigationItemPosition.TOP)

    def initAdvancedSettingTab(self):
        self.advanced_settings_tab = Widget("AdvancedSettings", self)
        self.advanced_settings_layout = self.advanced_settings_tab.vBoxLayout

        # Translator Section
        self.advanced_settings_layout.addWidget(BodyLabel("🤖 选择用于翻译的模型类别。"))
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

        self.advanced_settings_layout.addWidget(BodyLabel("🚀 在线模型API地址，省略/v1/chat/completions（gpt-custom）"))
        self.gpt_address = QLineEdit()
        self.gpt_address.setPlaceholderText("例如：http://127.0.0.1:11434")
        self.advanced_settings_layout.addWidget(self.gpt_address)
        
        self.advanced_settings_layout.addWidget(BodyLabel("💻 离线模型文件（galtransl， sakura，llamacpp）"))
        self.sakura_file = QComboBox()
        sakura_lst = [i for i in os.listdir('llama') if i.endswith('gguf')]
        self.sakura_file.addItems(sakura_lst)
        self.advanced_settings_layout.addWidget(self.sakura_file)
        
        self.advanced_settings_layout.addWidget(BodyLabel("💻 离线模型GPU加载层数（galtransl， sakura，llamacpp）"))
        self.sakura_mode = QLineEdit()
        self.sakura_mode.setText("100")
        self.advanced_settings_layout.addWidget(self.sakura_mode)

        self.advanced_settings_layout.addWidget(BodyLabel("💻 离线模型命令行参数。"))
        self.param_llama = QTextEdit()
        self.param_llama.setPlaceholderText("每个参数空格隔开，请参考Llama.cpp文档，不清楚请保持默认。")
        self.advanced_settings_layout.addWidget(self.param_llama)

        self.open_model_dir = QPushButton("📁 打开离线模型目录")
        self.open_model_dir.clicked.connect(lambda: open_path(os.path.join(os.getcwd(),'llama')))
        self.advanced_settings_layout.addWidget(self.open_model_dir)

        self.test_online_button = QPushButton("🔍 测试模型API并列出可用模型")
        self.test_online_button.clicked.connect(self.run_test_online_api)
        self.advanced_settings_layout.addWidget(self.test_online_button)

        self.addSubInterface(self.advanced_settings_tab, FluentIcon.SETTING, "语言模型", NavigationItemPosition.TOP)

    def initClipTab(self):
        self.clip_tab = Widget("Clip", self)
        self.clip_layout = self.clip_tab.vBoxLayout

        # Clip Section
        self.clip_layout.addWidget(BodyLabel("🔪 切片工具"))
        self.clip_files_list = QTextEdit()
        self.clip_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.clip_files_list)
        self.clip_files_list.setPlaceholderText("拖拽视频文件到方框内，并填写开始和结束时间，点击运行即可。")
        self.clip_layout.addWidget(self.clip_files_list)

        hbox = QHBoxLayout()
        left_v = QVBoxLayout()
        right_v = QVBoxLayout()

        self.clip_start_time = QLineEdit()
        self.clip_start_time.setPlaceholderText("开始时间（HH:MM:SS.xxx）")
        left_v.addWidget(BodyLabel("开始时间"))
        left_v.addWidget(self.clip_start_time)

        self.clip_end_time = QLineEdit()
        self.clip_end_time.setPlaceholderText("结束时间（HH:MM:SS.xxx）")
        right_v.addWidget(BodyLabel("结束时间"))
        right_v.addWidget(self.clip_end_time)

        hbox.addLayout(left_v)
        hbox.addLayout(right_v)
        self.clip_layout.addLayout(hbox)

        self.run_clip_button = QPushButton("🚀 切片")
        self.run_clip_button.clicked.connect(self.run_clip)
        self.clip_layout.addWidget(self.run_clip_button)

        # Vocal Split
        self.clip_layout.addWidget(BodyLabel("🎤 人声分离工具"))
        self.uvr_file_list = QTextEdit()
        self.uvr_file_list.setAcceptDrops(True)
        self._bind_drop_event(self.uvr_file_list)
        self.uvr_file_list.setPlaceholderText("拖拽音频文件到方框内，点击运行即可。输出文件为原文件名_vocal.wav和_no_vocal.wav。")
        self.clip_layout.addWidget(self.uvr_file_list)

        self.run_uvr_button = QPushButton("🚀 人声分离")
        self.run_uvr_button.clicked.connect(self.run_vocal_split)
        self.clip_layout.addWidget(self.run_uvr_button)
        
        self.addSubInterface(self.clip_tab, FluentIcon.DEVELOPER_TOOLS, "分离工具", NavigationItemPosition.TOP)

    def initSynthTab(self):
        self.synth_tab = Widget("Synth", self)
        self.synth_layout = self.synth_tab.vBoxLayout

        # Video Synth
        self.synth_layout.addWidget(BodyLabel("💾 字幕合成工具"))

        # Video Files
        vbox_video = QHBoxLayout()
        vbox_video.addWidget(BodyLabel("🎥 视频文件"))
        self.synth_video_browse_btn = QPushButton("📂 浏览视频")
        self.synth_video_browse_btn.clicked.connect(self.browse_synth_video)
        vbox_video.addWidget(self.synth_video_browse_btn)
        self.synth_layout.addLayout(vbox_video)

        self.synth_video_files_list = QTextEdit()
        self.synth_video_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.synth_video_files_list)
        self.synth_video_files_list.setPlaceholderText("拖拽视频文件到此处，或点击浏览按钮选择。")
        self.synth_layout.addWidget(self.synth_video_files_list)

        # Subtitle Files
        vbox_srt = QHBoxLayout()
        vbox_srt.addWidget(BodyLabel("📝 字幕文件"))
        self.synth_srt_browse_btn = QPushButton("📂 浏览字幕")
        self.synth_srt_browse_btn.clicked.connect(self.browse_synth_srt)
        vbox_srt.addWidget(self.synth_srt_browse_btn)
        self.synth_layout.addLayout(vbox_srt)

        self.synth_srt_files_list = QTextEdit()
        self.synth_srt_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.synth_srt_files_list)
        self.synth_srt_files_list.setPlaceholderText("拖拽字幕文件到此处，或点击浏览按钮选择。字幕文件需要和视频文件一一对应。")
        self.synth_layout.addWidget(self.synth_srt_files_list)

        hbox = QHBoxLayout()

        hbox.addWidget(BodyLabel("字幕类型"))
        self.subtitle_type_combo = QComboBox()
        self.subtitle_type_combo.addItem("硬字幕")
        self.subtitle_type_combo.addItem("软字幕")
        hbox.addWidget(self.subtitle_type_combo)

        hbox.addWidget(BodyLabel("字体选择"))

        self.subtitle_font_combo = QComboBox()
        for font_item in self.collect_font_candidates():
            self.subtitle_font_combo.addItem(font_item)
        hbox.addWidget(self.subtitle_font_combo)

        self.run_synth_button = QPushButton("🚀 字幕合成")
        self.run_synth_button.clicked.connect(self.run_synth)
        hbox.addWidget(self.run_synth_button)
        self.synth_layout.addLayout(hbox)

        # Audio Synth
        self.synth_layout.addWidget(BodyLabel("🎵 音频合成工具"))
        self.synth_audio_files_list = QTextEdit()
        self.synth_audio_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.synth_audio_files_list)
        self.synth_audio_files_list.setPlaceholderText("拖拽音频文件（wav，mp3，flac）和图像（png,jpg,jpeg）到下方框内，点击运行即可。音频和图像文件需要一一对应。")
        self.synth_layout.addWidget(self.synth_audio_files_list)
        self.run_synth_audio_button = QPushButton("🚀 视频合成")
        self.run_synth_audio_button.clicked.connect(self.run_synth_audio)
        self.synth_layout.addWidget(self.run_synth_audio_button)

        self.addSubInterface(self.synth_tab, FluentIcon.DEVELOPER_TOOLS, "合成工具", NavigationItemPosition.TOP)

    def initSummarizeTab(self):
        self.summarize_tab = Widget("Summarize", self)
        self.summarize_layout = self.summarize_tab.vBoxLayout

        self.summarize_layout.addWidget(BodyLabel("🖋️ 模型提示"))
        self.summarize_prompt = QTextEdit()
        self.summarize_prompt.setPlaceholderText("请为以下内容创建一个带有时间戳（mm:ss格式）的粗略摘要，不多于10个事件。请关注关键事件和重要时刻，并确保所有时间戳都采用分钟:秒钟格式。")
        self.summarize_layout.addWidget(self.summarize_prompt)

        self.summarize_layout.addWidget(BodyLabel("📁 输入文件"))
        self.summarize_files_list = QTextEdit()
        self.summarize_files_list.setAcceptDrops(True)
        self._bind_drop_event(self.summarize_files_list)
        self.summarize_files_list.setPlaceholderText("拖拽文件到方框内，点击运行即可。输出文件为输入文件名.summary.txt。")
        self.summarize_layout.addWidget(self.summarize_files_list)

        self.run_summarize_button = QPushButton("🚀 运行")
        self.run_summarize_button.clicked.connect(self.run_summarize)
        self.summarize_layout.addWidget(self.run_summarize_button)

        self.addSubInterface(self.summarize_tab, FluentIcon.DEVELOPER_TOOLS, "总结工具", NavigationItemPosition.TOP)

    def run_worker(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()
        self.switchTo(self.log_tab)

    def run_clip(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.clip)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()
        self.switchTo(self.log_tab)

    def run_synth(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.synth)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()
        self.switchTo(self.log_tab)

    def run_synth_audio(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.audiosynth)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()
        self.switchTo(self.log_tab)

    def run_vocal_split(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.vocal_split)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()
        self.switchTo(self.log_tab)

    def run_summarize(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.summarize)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()
        self.switchTo(self.log_tab)

    def run_test_online_api(self):
        self.thread = QThread()
        self.worker = MainWorker(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.test_online_api)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()
        self.switchTo(self.log_tab)
    
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
            # Ensure all child processes are terminated on error
            self.stop()

    return wrapper
class MainWorker(QObject):
    finished = pyqtSignal()

    def __init__(self, master):
        super().__init__()
        self.master = master
        self.status = master.status
        self.child_processes = []
        self._stop_requested = False

    def _start_process(self, args):
        creationflags = 0x08000000 if os.name == 'nt' else 0
        proc = subprocess.Popen(args, stdout=sys.stdout, stderr=sys.stdout, creationflags=creationflags)
        self.child_processes.append(proc)
        self.pid = proc
        return proc

    def _cleanup_process(self, proc):
        if not proc:
            return
        try:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        finally:
            if proc in self.child_processes:
                self.child_processes.remove(proc)

    def _terminate_all_children(self):
        for proc in list(self.child_processes):
            self._cleanup_process(proc)

    def stop(self):
        self._stop_requested = True
        self._terminate_all_children()

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
        sakura_mode = self.master.sakura_mode.text()
        proxy_address = self.master.proxy_address.text()
        uvr_file = self.master.uvr_file.currentText()
        output_format = self.master.output_format.currentText()
        subtitle_font = self.master.subtitle_font_combo.currentText()
        output_dir = self.master.output_dir_edit.text().strip() or self.master.default_output_dir()
        use_input_dir = self.master.use_input_dir_checkbox.isChecked()
        output_dir = os.path.abspath(os.path.expanduser(output_dir))
        os.makedirs(output_dir, exist_ok=True)

        # save config
        with open('config.txt', 'w', encoding='utf-8') as f:
            f.write(f"{whisper_file}\n{translator}\n{language}\n{gpt_token}\n{gpt_address}\n{gpt_model}\n{sakura_file}\n{sakura_mode}\n{proxy_address}\n{uvr_file}\n{output_format}\n{subtitle_font}\n{output_dir}\n{use_input_dir}\n")

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
    def update_translation_config(self):
        self.status.emit("[INFO] 正在进行翻译配置...")
        translator = self.master.translator_group.currentText()
        language = self.master.input_lang.currentText()
        gpt_token = self.master.gpt_token.text()
        gpt_address = self.master.gpt_address.text()
        gpt_model = self.master.gpt_model.text()
        sakura_file = self.master.sakura_file.currentText()
        proxy_address = self.master.proxy_address.text()

        if not gpt_token:
            gpt_token = 'sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

        try:
            with open('project/config.yaml', 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self.status.emit(f"[ERROR] 无法读取配置文件 project/config.yaml：{e}")
            return

        for idx, line in enumerate(lines):
            if 'language:' in line:
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
                if 'proxy:' in line:
                    lines[idx+1] = f"  enableProxy: true\n"
                    lines[idx+3] = f"    - address: {proxy_address}\n"
            else:
                if 'proxy:' in line:
                    lines[idx+1] = f"  enableProxy: false\n"

        try:
            with open('project/config.yaml', 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except Exception as e:
            self.status.emit(f"[ERROR] 写入配置文件失败：{e}")

    @error_handler
    def test_online_api(self):
        self.save_config()
        translator = self.master.translator_group.currentText()
        gpt_token = self.master.gpt_token.text()
        gpt_address = self.master.gpt_address.text()
        gpt_model = self.master.gpt_model.text()
        proxy_address = self.master.proxy_address.text()

        base_url = None
        if translator == 'gpt-custom' and gpt_address:
            base_url = gpt_address
        else:
            base_url = ONLINE_TRANSLATOR_MAPPING.get(translator)

        if not base_url:
            self.status.emit("[ERROR] 请选择模型。")
            self.finished.emit()
            return

        base_url = base_url.rstrip('/') + '/v1/models'
        base_url = handle_special_api(base_url)

        self.status.emit(f"[INFO] 正在测试API，地址：{base_url} ...")
        try:
            if proxy_address:
                os.environ['HTTP_PROXY'] = proxy_address
                os.environ['HTTPS_PROXY'] = proxy_address
            else:
                os.environ.pop('HTTP_PROXY', None)
                os.environ.pop('HTTPS_PROXY', None)

            headers = {
                'Authorization': f'Bearer {gpt_token}',
                'Content-Type': 'application/json'
            }

            resp = requests.get(base_url, headers=headers, timeout=20)
            resp.raise_for_status()

            try:
                body = resp.text[:500].replace('\n', ' ')
            except Exception:
                body = str(resp)[:500].replace('\n', ' ')

            self.status.emit(f"[INFO] API测试完成，地址：{base_url}，响应：{body}")
        except Exception as e:
            self.status.emit(f"[ERROR] API测试失败：{e}")

        self.finished.emit()

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
                if self._stop_requested:
                    break
                if not os.path.exists(input_file):
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()

                self.status.emit(f"[INFO] 正在进行伴奏分离...第{idx+1}个，共{len(input_files)}个")
                proc = self._start_process(['uvr/separate', '-m', os.path.join('uvr',uvr_file), input_file])
                proc.wait()
                self._cleanup_process(proc)

            self.status.emit("[INFO] 文件处理完成！")
        self.finished.emit()

    @error_handler
    def summarize(self):
        self.save_config()
        # 统一刷新翻译配置，供摘要复用
        self.update_translation_config()
        input_files = self.master.summarize_files_list.toPlainText()
        # 使用与主程序相同的配置：从 project/config.yaml 读取 GPT 配置与代理
        try:
            with open('project/config.yaml', 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)
        except Exception as e:
            self.status.emit(f"[ERROR] 无法读取配置文件 project/config.yaml：{e}")
            self.finished.emit()
            return

        backend = (cfg or {}).get('backendSpecific', {})
        gpt35 = backend.get('GPT35', {})
        tokens = gpt35.get('tokens', []) or []
        token = tokens[0].get('token') if tokens else ''
        address = gpt35.get('defaultEndpoint', '')
        model = gpt35.get('rewriteModelName', '')

        # 代理设置同步
        proxy_cfg = (cfg or {}).get('proxy', {})
        if proxy_cfg.get('enableProxy'):
            proxies = proxy_cfg.get('proxies') or []
            if proxies and isinstance(proxies[0], dict):
                proxy_address = proxies[0].get('address')
                if proxy_address:
                    os.environ['HTTP_PROXY'] = proxy_address
                    os.environ['HTTPS_PROXY'] = proxy_address
        else:
            # 清理可能遗留的代理环境变量
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)

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
    def synth(self):
        self.save_config()
        subtitle_font = self.master.subtitle_font_combo.currentText().strip()
        subtitle_type = self.master.subtitle_type_combo.currentText().strip()

        video_files_text = self.master.synth_video_files_list.toPlainText().strip()
        srt_files_text = self.master.synth_srt_files_list.toPlainText().strip()

        def escape_sub_path(path_str: str) -> str:
            # ffmpeg subtitles filter needs windows drive colon escaped
            return path_str.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")

        def build_subtitle_filter(srt_path: str, font_value: str) -> str:
            srt_abs = escape_sub_path(str(Path(srt_path).resolve()))
            parts = [f"subtitles='{srt_abs}'"]
            if font_value:
                font_path = Path(font_value)
                if font_path.exists():
                    fonts_dir = escape_sub_path(str(font_path.parent.resolve()))
                    font_name = font_path.name.replace("'", "\\'")
                    parts.append(f"fontsdir='{fonts_dir}'")
                    parts.append(f"force_style='FontName={font_name}'")
                else:
                    font_name = font_value.replace("'", "\\'")
                    parts.append(f"force_style='FontName={font_name}'")
            return ':'.join(parts)

        if video_files_text and srt_files_text:
            video_files = video_files_text.split('\n')
            srt_files = srt_files_text.split('\n')

            if len(srt_files) != len(video_files):
                self.status.emit("[ERROR] 字幕文件和视频文件数量不匹配，请重新选择文件！")
                self.finished.emit()
                return
            
            for idx, (input_file, input_srt) in enumerate(zip(video_files, srt_files)):
                if self._stop_requested:
                    break
                if not os.path.exists(input_file):
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()
                    return

                if not os.path.exists(input_srt):
                    self.status.emit(f"[ERROR] {input_srt}文件不存在，请重新选择文件！")
                    self.finished.emit()
                    return

                self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{idx+1}个，共{len(video_files)}个")

                output_file = input_file + '_synth.mp4'

                if subtitle_type == "硬字幕":
                    input_srt_cache = shutil.copy(input_srt, 'project/cache/')
                    subtitle_filter = build_subtitle_filter(input_srt_cache, subtitle_font)
                    if subtitle_font:
                        self.status.emit(f"[INFO] 使用字幕字体：{subtitle_font}")
                    self.status.emit(f"[INFO] 正在合成硬字幕...")
                    proc = self._start_process(['ffmpeg/ffmpeg', '-y', '-i', input_file, '-vf', subtitle_filter, '-vcodec', 'libx264', '-acodec', 'aac', output_file])
                else:
                    self.status.emit(f"[INFO] 正在合成软字幕...")
                    # For soft subtitles, we just map the streams.
                    # Depending on the container and subtitle format, -c:s mov_text works for mp4.
                    proc = self._start_process(['ffmpeg/ffmpeg', '-y', '-i', input_file, '-i', input_srt, '-c:v', 'copy', '-c:a', 'copy', '-c:s', 'mov_text', output_file])

                proc.wait()
                self._cleanup_process(proc)
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
                if self._stop_requested:
                    break
                if not os.path.exists(input_file):
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    self.finished.emit()

                self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{idx+1}个，共{len(input_files)}个")
                self.status.emit(f"[INFO] 正在进行切片...从{clip_start}到{clip_end}...")
                proc = self._start_process(['ffmpeg/ffmpeg', '-y', '-i', input_file, '-ss', clip_start, '-to', clip_end, '-vcodec', 'libx264', '-acodec', 'aac', os.path.join(*(input_file.split('.')[:-1]))+'_clip.'+input_file.split('.')[-1]])
                proc.wait()
                self._cleanup_process(proc)
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
                if self._stop_requested:
                    break
                if not os.path.exists(audio_input):
                    self.status.emit(f"[ERROR] {audio_input}文件不存在，请重新选择文件！")
                    self.finished.emit()

                if not os.path.exists(image_input):
                    self.status.emit(f"[ERROR] {image_input}文件不存在，请重新选择文件！")
                    self.finished.emit()

                self.status.emit(f"[INFO] 当前处理文件：{audio_input} 第{idx+1}个，共{len(image_files)}个")
                proc = self._start_process(['ffmpeg/ffmpeg', '-y', '-loop', '1', '-r', '1', '-f', 'image2', '-i', image_input, '-i', audio_input, '-shortest', '-vcodec', 'libx264', '-acodec', 'aac', audio_input+'_synth.mp4'])
                proc.wait()
                self._cleanup_process(proc)
                self.status.emit("[INFO] 视频合成完成！")
            
        self.finished.emit()

    @error_handler
    def run(self):
        self.save_config()
        input_files = self.master.input_files_list.toPlainText()
        whisper_file = self.master.whisper_file.currentText()
        translator = self.master.translator_group.currentText()
        language = self.master.input_lang.currentText()
        sakura_file = self.master.sakura_file.currentText()
        sakura_mode = self.master.sakura_mode.text()
        proxy_address = self.master.proxy_address.text()
        before_dict = self.master.before_dict.toPlainText()
        gpt_dict = self.master.gpt_dict.toPlainText()
        after_dict = self.master.after_dict.toPlainText()
        extra_prompt = self.master.extra_prompt.toPlainText()
        param_whisper = self.master.param_whisper.toPlainText()
        param_whisper_faster = self.master.param_whisper_faster.toPlainText()
        param_llama = self.master.param_llama.toPlainText()
        output_format = self.master.output_format.currentText()
        output_dir = self.master.output_dir_edit.text().strip() or self.master.default_output_dir()
        use_input_dir = self.master.use_input_dir_checkbox.isChecked()

        with open('whisper/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_whisper)

        with open('whisper-faster/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_whisper_faster)

        with open('llama/param.txt', 'w', encoding='utf-8') as f:
            f.write(param_llama)

        self.status.emit("[INFO] 正在初始化项目文件夹...")
        if use_input_dir:
            self.status.emit("[INFO] 已启用“输出到音频目录”，将按每个输入文件目录输出。")
        else:
            self.status.emit(f"[INFO] 输出目录：{output_dir}")

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

        self.status.emit(f"[INFO] 当前输入：{input_files}")

        if input_files:
            input_files = input_files.split('\n')
        else:
            input_files = []

        os.makedirs('project/cache', exist_ok=True)

        # 统一刷新翻译配置
        self.update_translation_config()

        need_translate = translator != '不进行翻译' and language != 'zh'
        if not need_translate:
            if translator == '不进行翻译':
                self.status.emit("[INFO] 翻译器未选择，按单文件流程跳过翻译步骤...")
            elif language == 'zh':
                self.status.emit("[INFO] 听写语言为中文，按单文件流程跳过翻译步骤...")

        def reset_translation_workspace():
            for folder in ['project/gt_input', 'project/gt_output', 'project/transl_cache']:
                if os.path.exists(folder):
                    shutil.rmtree(folder)
                os.makedirs(folder, exist_ok=True)

        engine = 'gpt35-1106'
        if need_translate:
            engine = 'sakura-010' if (
                'galtransl' in translator or 'sakura' in translator or 'llamacpp' in translator
            ) else 'gpt35-1106'

        running_procs = {}

        def start_named_proc(proc_name, args):
            existing = running_procs.get(proc_name)
            if existing and existing.poll() is None:
                self.status.emit(f"[WARN] 检测到进程 {proc_name} 已在运行，跳过重复启动。")
                return existing, True
            if existing:
                self._cleanup_process(existing)
                running_procs.pop(proc_name, None)

            new_proc = self._start_process(args)
            running_procs[proc_name] = new_proc
            return new_proc, False

        def stop_named_proc(proc_name):
            target = running_procs.pop(proc_name, None)
            if target:
                self._cleanup_process(target)

        for idx, input_file in enumerate(input_files):
            if self._stop_requested:
                break
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
                    downloaded_file = os.path.abspath(f"{title}_{res['bvid']}.mp4")
                    target_file = os.path.join(output_dir, os.path.basename(downloaded_file))
                    if os.path.exists(downloaded_file):
                        if os.path.exists(target_file):
                            os.remove(target_file)
                        input_file = shutil.move(downloaded_file, target_file)
                    else:
                        self.status.emit(f"[ERROR] 下载完成但未找到文件：{downloaded_file}")
                        self.finished.emit()
                        return

                else:
                    ydl_outtmpl = os.path.join(output_dir, 'YoutubeDL_%(title)s_%(id)s.%(ext)s')
                    if proxy_address:
                        ydl_ctx = YoutubeDL({'proxy': proxy_address, 'outtmpl': ydl_outtmpl})
                    else:
                        ydl_ctx = YoutubeDL({'outtmpl': ydl_outtmpl})

                    with ydl_ctx as ydl:
                        self.status.emit("[INFO] 正在下载视频...")
                        info = ydl.extract_info(input_file, download=True)
                        self.status.emit("[INFO] 视频下载完成！")
                        input_file = ydl.prepare_filename(info)
                        requested_downloads = info.get('requested_downloads') if isinstance(info, dict) else None
                        if requested_downloads and isinstance(requested_downloads[0], dict):
                            actual_file = requested_downloads[0].get('filepath')
                            if actual_file:
                                input_file = actual_file
                        if isinstance(info, dict) and info.get('_filename') and os.path.exists(info.get('_filename')):
                            input_file = info.get('_filename')

                    input_file = os.path.abspath(str(input_file or ''))
                    if not os.path.exists(input_file):
                        self.status.emit(f"[ERROR] 下载完成但未找到文件：{input_file}")
                        self.finished.emit()
                        return

            self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{idx+1}个，共{len(input_files)}个")
            current_output_dir = output_dir
            if use_input_dir:
                current_output_dir = os.path.dirname(os.path.abspath(input_file)) or output_dir
                self.status.emit(f"[INFO] 当前文件输出目录：{current_output_dir}")
            if need_translate:
                reset_translation_workspace()
            else:
                os.makedirs('project/gt_input', exist_ok=True)

            if input_file.endswith('.srt'):
                self.status.emit("[INFO] 正在进行字幕转换...")
                output_file_path = os.path.join('project/gt_input', os.path.basename(input_file).replace('.srt','.json'))
                make_prompt(input_file, output_file_path)
                self.status.emit("[INFO] 字幕转换完成！")
                # Ensure original srt is available in output_dir for later merging
                try:
                    orig_srt_src = os.path.abspath(input_file)
                    orig_srt_dst = os.path.join(current_output_dir, os.path.basename(orig_srt_src))
                    if os.path.exists(orig_srt_src):
                        shutil.copy(orig_srt_src, orig_srt_dst)
                except Exception:
                    pass
                if output_format == '双语LRC':
                    lrc_name = os.path.basename(input_file[:-4] + '.orig.lrc')
                    lrc_output = os.path.join(current_output_dir, lrc_name)
                    make_lrc(output_file_path, lrc_output)
                input_file = input_file[:-4]
            else:
                if whisper_file == '不进行听写':
                    self.status.emit("[INFO] 不进行听写，跳过听写步骤...")
                    continue

                wav_file = '.'.join(input_file.split('.')[:-1]) + '.16k.wav'
                self.status.emit("[INFO] 正在进行音频提取...")
                ffmpeg_proc, _ = start_named_proc(
                    'ffmpeg_extract',
                    ['ffmpeg/ffmpeg', '-y', '-i', input_file, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', wav_file]
                )
                ffmpeg_proc.wait()
                stop_named_proc('ffmpeg_extract')

                if not os.path.exists(wav_file):
                    self.status.emit("[ERROR] 音频提取失败，请检查文件格式！")
                    break

                self.status.emit("[INFO] 正在进行语音识别...")

                if whisper_file.startswith('ggml'):
                    print(param_whisper)
                    whisper_proc, _ = start_named_proc(
                        'whisper',
                        [param.replace('$whisper_file',whisper_file).replace('$input_file',wav_file[:-4]).replace('$language',language) for param in param_whisper.split()]
                    )
                elif whisper_file.startswith('faster-whisper'):
                    print(param_whisper_faster)
                    whisper_proc, _ = start_named_proc(
                        'whisper_faster',
                        [param.replace('$whisper_file',whisper_file[15:]).replace('$input_file',wav_file[:-4]).replace('$language',language).replace('$output_dir',os.path.dirname(input_file)) for param in param_whisper_faster.split()]
                    )
                else:
                    self.status.emit("[INFO] 不进行听写，跳过听写步骤...")
                    continue
                whisper_proc.wait()
                if whisper_file.startswith('ggml'):
                    stop_named_proc('whisper')
                else:
                    stop_named_proc('whisper_faster')

                input_file = wav_file[:-8]
                output_file_path = os.path.join('project/gt_input', os.path.basename(input_file)+'.json')
                make_prompt(wav_file[:-4]+'.srt', output_file_path)

                if output_format == '原文SRT' or output_format == '双语SRT':
                    srt_name = os.path.basename(input_file + '.srt')
                    srt_output = os.path.join(current_output_dir, srt_name)
                    make_srt(output_file_path, srt_output)

                if output_format == '原文LRC' or output_format == '双语LRC':
                    lrc_path = input_file + '.lrc'
                    if output_format == '双语LRC':
                        lrc_path = input_file + '.orig.lrc'
                    lrc_name = os.path.basename(lrc_path)
                    lrc_output = os.path.join(current_output_dir, lrc_name)
                    make_lrc(output_file_path, lrc_output)

                if os.path.exists(wav_file):
                    os.remove(wav_file)

                if os.path.exists(wav_file[:-4]+'.srt'):
                    os.remove(wav_file[:-4]+'.srt')
                self.status.emit("[INFO] 语音识别完成！")

            if need_translate and ('sakura' in translator or 'llamacpp' in translator or 'galtransl' in translator):
                if not sakura_file:
                    self.status.emit("[INFO] 未选择模型文件，跳过翻译步骤...")
                    need_translate = False
                else:
                    _, duplicated = start_named_proc(
                        'llama_translator',
                        [param.replace('$model_file',sakura_file).replace('$num_layers',sakura_mode).replace('$port', '8989') for param in param_llama.split()]
                    )

                    if not duplicated:
                        self.status.emit("[INFO] 正在等待Sakura翻译器启动并确认/chat/completions可用...")
                        expected_model = str(Path(sakura_file).name) if sakura_file else ""
                        model_ready = False
                        start_wait = time()
                        while True:
                            if self._stop_requested:
                                break
                            try:
                                chat_resp = requests.post(
                                    "http://localhost:8989/v1/chat/completions",
                                    json={
                                        "model": expected_model,
                                        "messages": [{"role": "user", "content": "ping"}],
                                        "max_tokens": 1,
                                        "temperature": 0
                                    },
                                    timeout=8
                                )
                                if chat_resp.status_code == 200:
                                    try:
                                        body = chat_resp.json()
                                        if isinstance(body, dict) and body.get("choices"):
                                            model_ready = True
                                            self.status.emit("[INFO] Sakura翻译器启动并准备就绪！返回值：" + str(body)[:200])
                                            break
                                    except Exception:
                                        pass
                            except requests.exceptions.RequestException:
                                pass
                            if time() - start_wait > 120:
                                self.status.emit("[ERROR] Sakura翻译器启动超时或模型未加载成功。")
                                stop_named_proc('llama_translator')
                                self.finished.emit()
                                return
                            sleep(1)

                        if not model_ready and not self._stop_requested:
                            self.status.emit("[ERROR] 未检测到目标模型，终止翻译流程。")
                            stop_named_proc('llama_translator')
                            self.finished.emit()
                            return

                        if self._stop_requested:
                            stop_named_proc('llama_translator')
                            self.finished.emit()
                            return

            if need_translate:
                self.status.emit("[INFO] 正在进行翻译...")
                try:
                    cfg = CProjectConfig('project','config.yaml')
                    asyncio.run(run_galtransl(cfg, engine))
                except Exception as e:
                    self.status.emit(f"[ERROR] 翻译过程中发生错误: {e}")
                    continue

                self.status.emit("[INFO] 正在生成字幕文件...")
                if output_format == '中文SRT' or output_format == '双语SRT':
                    zh_srt_name = os.path.basename(input_file + '.zh.srt')
                    zh_srt_output = os.path.join(current_output_dir, zh_srt_name)
                    make_srt(output_file_path.replace('gt_input','gt_output'), zh_srt_output)

                if output_format == '中文LRC' or output_format == '双语LRC':
                    lrc_path = input_file + '.lrc'
                    if output_format == '双语LRC':
                        lrc_path = input_file + '.zh.lrc'
                    lrc_name = os.path.basename(lrc_path)
                    lrc_output = os.path.join(current_output_dir, lrc_name)
                    make_lrc(output_file_path.replace('gt_input','gt_output'), lrc_output)

                if output_format == '双语SRT':
                    combine_name = os.path.basename(input_file + '.combine.srt')
                    combine_output = os.path.join(current_output_dir, combine_name)
                    left = os.path.join(current_output_dir, os.path.basename(input_file + '.srt'))
                    right = os.path.join(current_output_dir, os.path.basename(input_file + '.zh.srt'))
                    merge_srt_files([left, right], combine_output)

                if output_format == '双语LRC':
                    combine_name = os.path.basename(input_file + '.combine.lrc')
                    combine_output = os.path.join(current_output_dir, combine_name)
                    left = os.path.join(current_output_dir, os.path.basename(input_file + '.orig.lrc'))
                    right = os.path.join(current_output_dir, os.path.basename(input_file + '.zh.lrc'))
                    merge_lrc_files([left, right], combine_output)

                self.status.emit("[INFO] 字幕文件生成完成！")

        if running_procs.get('llama_translator'):
            self.status.emit("[INFO] 正在关闭Llamacpp翻译器...")
            stop_named_proc('llama_translator')

        self.status.emit("[INFO] 所有文件处理完成！")
        self.finished.emit()

if __name__ == "__main__":
    os.makedirs('project/cache', exist_ok=True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
