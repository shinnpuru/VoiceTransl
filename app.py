import sys
import os
import shutil
from threading import Thread
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QFileDialog, QFrame, QScrollArea
from qfluentwidgets import PushButton as QPushButton, TextEdit as QTextEdit, LineEdit as QLineEdit, ComboBox as QComboBox, Slider as QSlider, FluentWindow as QMainWindow
from qfluentwidgets import FluentIcon, NavigationItemPosition, SubtitleLabel, TitleLabel, BodyLabel
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal

TRANSLATOR_SUPPORTED = [
    '不进行翻译',
    "sakura-009",
    "sakura-010",
    "index",
    "Galtransl",
    "gpt35-0613",
    "gpt35-1106",
    "gpt4-turbo",
    "moonshot-v1-8k",
    "glm-4",
    "glm-4-flash",
    "qwen2-7b-instruct",
    "qwen2-57b-a14b-instruct",
    "qwen2-72b-instruct",
    "abab6.5-chat",
    "abab6.5s-chat",
]

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

        self.setWindowTitle("GalTransl for ASMR")
        self.resize(800, 600)
        self.initUI()
        
    def initUI(self):
        self.initInputOutputTab()
        self.initSettingsTab()
        self.initDictTab()
        self.initOutputTab()

        # load config
        if os.path.exists('config.txt'):
            with open('config.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                whisper_file = lines[0].strip()
                translator = lines[1].strip()
                gpt_token = lines[2].strip()
                sakura_file = lines[3].strip()
                sakura_mode = int(lines[4].strip())
                proxy_address = lines[5].strip()

                if self.whisper_file: self.whisper_file.setCurrentText(whisper_file)
                self.translator_group.setCurrentText(translator)
                self.gpt_token.setText(gpt_token)
                self.sakura_file.setCurrentText(sakura_file)
                self.sakura_mode.setValue(sakura_mode)
                self.proxy_address.setText(proxy_address)
        
    def initInputOutputTab(self):
        self.input_output_tab = Widget("Home", self)
        self.input_output_layout = self.input_output_tab.vBoxLayout
        
        self.input_output_layout.addWidget(TitleLabel("🎉 欢迎使用GalTransl for ASMR！"))
        self.input_output_layout.addWidget(BodyLabel("📄 您可以使用本程序将日语音视频文件/字幕文件转换为中文字幕文件。"))
        
        # Input Section
        self.input_file_button = QPushButton("📂 请选择音视频文件/SRT文件或拖拽文件到窗口（可多选）。")
        self.input_file_button.clicked.connect(self.select_input)
        self.input_output_layout.addWidget(self.input_file_button)

        # Input Files List
        self.input_files_list = QTextEdit()
        self.input_files_list.setAcceptDrops(True)
        self.input_files_list.dropEvent = lambda e: self.input_files_list.setPlainText('\n'.join([i[8:] for i in e.mimeData().text().split('\n')]))
        self.input_files_list.setPlaceholderText("当前未选择本地文件...")
        self.input_output_layout.addWidget(self.input_files_list)

        # YouTube URL Section
        self.input_output_layout.addWidget(BodyLabel("🔗 或者输入B站视频BV号或者YouTube视频链接。"))
        self.yt_url = QTextEdit()
        self.yt_url.setAcceptDrops(False)
        self.yt_url.setPlaceholderText("例如：https://www.youtube.com/watch?v=...\n例如：BV1Lxt5e8EJF")
        self.input_output_layout.addWidget(self.yt_url)
        
        # Run Button
        self.run_button = QPushButton("🚀 运行（状态详情请见输出界面）")
        self.run_button.clicked.connect(self.run_worker)
        self.input_output_layout.addWidget(self.run_button)
        
        self.addSubInterface(self.input_output_tab, FluentIcon.HOME, "主页", NavigationItemPosition.TOP)

    def initDictTab(self):
        self.dict_tab = Widget("Dict", self)
        self.dict_layout = self.dict_tab.vBoxLayout

        self.dict_layout.addWidget(TitleLabel("📚 字典配置"))
        self.dict_layout.addWidget(BodyLabel("配置翻译前的字典。"))
        self.before_dict = QTextEdit()
        self.before_dict.setPlaceholderText("日文\t日文\n日文\t日文")
        self.dict_layout.addWidget(self.before_dict)
        
        self.dict_layout.addWidget(BodyLabel("配置翻译后的字典。"))
        self.gpt_dict = QTextEdit()
        self.gpt_dict.setPlaceholderText("日文\t中文\n日文\t中文")
        self.dict_layout.addWidget(self.gpt_dict)
        
        self.dict_layout.addWidget(BodyLabel("配置翻译后的字典。"))
        self.after_dict = QTextEdit()
        self.after_dict.setPlaceholderText("中文\t中文\n中文\t中文")
        self.dict_layout.addWidget(self.after_dict)

        self.addSubInterface(self.dict_tab, FluentIcon.DICTIONARY, "字典", NavigationItemPosition.TOP)
        
    def initSettingsTab(self):
        self.settings_tab = Widget("Settings", self)
        self.settings_layout = self.settings_tab.vBoxLayout

        self.settings_layout.addWidget(TitleLabel("⚙️ 设置"))
        
        # Proxy Section
        self.settings_layout.addWidget(SubtitleLabel("🌐 代理设置"))
        self.settings_layout.addWidget(BodyLabel("设置代理地址以便下载视频。"))
        self.proxy_address = QLineEdit()
        self.proxy_address.setPlaceholderText("例如：http://127.0.0.1:7890，留空为不使用代理。")
        self.settings_layout.addWidget(self.proxy_address)
        
        # Whisper Section
        self.settings_layout.addWidget(SubtitleLabel("🗣️ 语音识别AI模型"))
        self.settings_layout.addWidget(BodyLabel("选择用于语音识别的 Whisper 模型文件。"))
        self.whisper_file = QComboBox()
        whisper_lst = [i for i in os.listdir('whisper') if i.startswith('ggml') and i.endswith('bin')]
        self.whisper_file.addItems(whisper_lst)
        self.settings_layout.addWidget(self.whisper_file)
        
        # Translator Section
        self.settings_layout.addWidget(SubtitleLabel("🌍 翻译AI模型"))
        self.settings_layout.addWidget(BodyLabel("选择用于翻译的模型类别。"))
        self.translator_group = QComboBox()
        self.translator_group.addItems(TRANSLATOR_SUPPORTED)
        self.settings_layout.addWidget(self.translator_group)
        
        self.settings_layout.addWidget(BodyLabel("🔑 在线模型令牌"))
        self.gpt_token = QLineEdit()
        self.gpt_token.setPlaceholderText("留空为使用上次配置的Token。")
        self.settings_layout.addWidget(self.gpt_token)
        
        self.settings_layout.addWidget(BodyLabel("📦 离线模型文件"))
        self.sakura_file = QComboBox()
        sakura_lst = [i for i in os.listdir('llama') if i.endswith('gguf')]
        self.sakura_file.addItems(sakura_lst)
        self.settings_layout.addWidget(self.sakura_file)
        
        self.settings_layout.addWidget(BodyLabel("🔢 离线模型参数（越大表示使用GPU越多）: "))
        self.sakura_value = QLineEdit()
        self.sakura_value.setPlaceholderText("999")
        self.sakura_value.setReadOnly(True)
        self.settings_layout.addWidget(self.sakura_value)
        self.sakura_mode = QSlider(Qt.Horizontal)
        self.sakura_mode.setRange(0, 999)
        self.sakura_mode.setValue(999)
        self.sakura_mode.valueChanged.connect(lambda: self.sakura_value.setText(str(self.sakura_mode.value())))
        self.settings_layout.addWidget(self.sakura_mode)
        
        self.addSubInterface(self.settings_tab, FluentIcon.SETTING, "设置", NavigationItemPosition.TOP)
    
    def initOutputTab(self):
        self.output_tab = Widget("Output", self)
        self.output_layout = self.output_tab.vBoxLayout

        self.output_layout.addWidget(TitleLabel("💾 输出"))
        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)
        self.status.connect(self.output_text_edit.append)
        self.output_layout.addWidget(self.output_text_edit)

        self.open_log_button = QPushButton("📤 详细日志")
        self.open_log_button.clicked.connect(lambda: os.startfile('log.txt'))
        self.output_layout.addWidget(self.open_log_button)

        self.open_output_button = QPushButton("📁 打开下载文件夹")
        self.open_output_button.clicked.connect(lambda: os.startfile(os.path.join(os.getcwd(),'project/cache')))
        self.output_layout.addWidget(self.open_output_button)
        
        self.clean_button = QPushButton("🧹 清空下载缓存")
        self.clean_button.clicked.connect(self.cleaner)
        self.output_layout.addWidget(self.clean_button)

        self.addSubInterface(self.output_tab, FluentIcon.DOCUMENT, "输出", NavigationItemPosition.TOP)
        
    def select_input(self):
        options = QFileDialog.Options()
        files, _ = QFileDialog.getOpenFileNames(self, "选择音视频文件/SRT文件", "", "All Files (*);;Video Files (*.mp4 *.webm, *.flv);;SRT Files (*.srt);;Audio Files (*.wav, *.mp3, *.flac)", options=options)
        if files:
            self.input_files_list.setPlainText('\n'.join(files))

    def run_worker(self):
        # Create a thread object
        self.thread = QThread()

        # Create a worker object
        self.worker = MainWorker(self)

        # Move worker to the thread
        self.worker.moveToThread(self.thread)

        # Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)

        # Start the thread
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


class MainWorker(QObject):
    finished = pyqtSignal()

    def __init__(self, master):
        super().__init__()
        self.master = master
        self.status = master.status
        self.log = open('log.txt', 'w', encoding='utf-8')

    def run(self):
        self.status.emit("[INFO] 正在读取配置...")
        input_files = self.master.input_files_list.toPlainText()
        yt_url = self.master.yt_url.toPlainText()
        whisper_file = self.master.whisper_file.currentText()
        translator = self.master.translator_group.currentText()
        gpt_token = self.master.gpt_token.text()
        sakura_file = self.master.sakura_file.currentText()
        sakura_mode = self.master.sakura_mode.value()
        proxy_address = self.master.proxy_address.text()
        before_dict = self.master.before_dict.toPlainText()
        gpt_dict = self.master.gpt_dict.toPlainText()
        after_dict = self.master.after_dict.toPlainText()

        # save config
        with open('config.txt', 'w', encoding='utf-8') as f:
            f.write(f"{whisper_file}\n{translator}\n{gpt_token}\n{sakura_file}\n{sakura_mode}\n{proxy_address}\n")

        self.status.emit("[INFO] 正在初始化项目文件夹...")

        import os
        os.makedirs('project/cache', exist_ok=True)
        if before_dict:
            with open('project/项目字典_译前.txt', 'w', encoding='utf-8') as f:
                f.write(before_dict.replace(' ','\t'))
        else:
            if os.path.exists('project/项目字典_译前.txt'):
                os.remove('project/项目字典_译前.txt')
        if gpt_dict:
            with open('project/项目GPT字典.txt', 'w', encoding='utf-8') as f:
                f.write(gpt_dict.replace(' ','\t'))
        else:
            if os.path.exists('project/项目GPT字典.txt'):
                os.remove('project/项目GPT字典.txt')
        if after_dict:
            with open('project/项目字典_译后.txt', 'w', encoding='utf-8') as f:
                f.write(after_dict.replace(' ','\t'))
        else:
            if os.path.exists('project/项目字典_译后.txt'):
                os.remove('project/项目字典_译后.txt')

        self.status.emit(f"[INFO] 当前输入文件：{input_files}, 当前视频链接：{yt_url}")

        if input_files:
            input_files = input_files.split('\n')
        else:
            input_files = []

        if yt_url:
            input_files.extend(yt_url.split('\n'))

        import os
        os.makedirs('project/cache', exist_ok=True)

        for input_file in input_files:
            if not os.path.exists(input_file):
                if 'youtu.be' in input_file or 'youtube.com' in input_file:
                    from yt_dlp import YoutubeDL
                    import os
                    if os.path.exists('project/YoutubeDL.webm'):
                        os.remove('project/YoutubeDL.webm')
                    with YoutubeDL({'proxy': proxy_address,'outtmpl': 'project/YoutubeDL.webm'}) as ydl:
                        self.status.emit("[INFO] 正在下载视频...")
                        results = ydl.download([input_file])
                        self.status.emit("[INFO] 视频下载完成！")
                    input_file = 'project/YoutubeDL.webm'

                elif 'BV' in yt_url:
                    from bilibili_dl.bilibili_dl.Video import Video
                    from bilibili_dl.bilibili_dl.downloader import download
                    from bilibili_dl.bilibili_dl.utils import send_request
                    from bilibili_dl.bilibili_dl.constants import URL_VIDEO_INFO
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
                    import re
                    title = res['title'] if res['videos'] == 1 else res['pages'][0]['part']
                    title = re.sub(r'[.:?/\\]', ' ', title).strip()
                    title = re.sub(r'\s+', ' ', title)
                    input_file = f'{title}.mp4'

                else:
                    self.status.emit(f"[ERROR] {input_file}文件不存在，请重新选择文件！")
                    continue

                if os.path.exists(os.path.join('project/cache', os.path.basename(input_file))):
                    os.remove(os.path.join('project/cache', os.path.basename(input_file)))
                input_file = shutil.move(input_file, 'project/cache/')

            self.status.emit(f"[INFO] 当前处理文件：{input_file} 第{input_files.index(input_file)+1}个，共{len(input_files)}个")

            from prompt2srt import make_srt, make_lrc
            from srt2prompt import make_prompt
            os.makedirs('project/gt_input', exist_ok=True)
            if input_file.endswith('.srt'):
                self.status.emit("[INFO] 正在进行字幕转换...")
                output_file_path = os.path.join('project/gt_input', os.path.basename(input_file).replace('.srt','.json'))
                make_prompt(input_file, output_file_path)
                self.status.emit("[INFO] 字幕转换完成！")
            else:
                if not whisper_file:
                    self.status.emit("[INFO] 未选择语音识别模型文件，请重新配置...")
                    break

                self.status.emit("[INFO] 正在进行音频提取...")
                import subprocess
                self.pid = subprocess.Popen(['ffmpeg.exe', '-y', '-i', input_file, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', input_file+'.wav'], stdout=self.log, stderr=self.log)
                self.pid.wait()

                self.status.emit("[INFO] 正在进行语音识别...")
                self.pid = subprocess.Popen(['whisper/main.exe', '-m', 'whisper/'+whisper_file, '-osrt', '-l', 'ja', input_file+'.wav', '-of', input_file], stdout=self.log, stderr=self.log)
                self.pid.wait()

                output_file_path = os.path.join('project/gt_input', os.path.basename(input_file)+'.json')
                make_prompt(input_file+'.srt', output_file_path)
                self.status.emit("[INFO] 语音识别完成！")

            if translator == '不进行翻译':
                self.status.emit("[INFO] 翻译器未选择，跳过翻译步骤...")
                continue

            self.status.emit("[INFO] 正在进行翻译配置...")
            with open('project/config.yaml', 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for idx, line in enumerate(lines):
                if 'gpt' in translator and gpt_token:
                    if 'GPT35:' in line:
                        lines[idx+2] = f"      - token: {gpt_token}\n"
                        lines[idx+6] = f"    defaultEndpoint: https://api.openai.com\n"
                        lines[idx+7] = f'    rewriteModelName: ""\n'
                    if 'GPT4: # GPT4 API' in line:
                        lines[idx+2] = f"      - token: {gpt_token}\n"
                if 'moonshot' in translator and gpt_token:
                    if 'GPT35:' in line:
                        lines[idx+4] = f"      - token: {gpt_token}\n"
                        lines[idx+6] = f"    defaultEndpoint: https://api.moonshot.cn\n"
                        lines[idx+7] = f'    rewriteModelName: "moonshot-v1-8k"\n'
                if 'qwen' in translator and gpt_token:
                    if 'GPT35:' in line:
                        lines[idx+4] = f"      - token: {gpt_token}\n"
                        lines[idx+6] = f"    defaultEndpoint: https://dashscope.aliyuncs.com/compatible-mode\n"
                        lines[idx+7] = f'    rewriteModelName: "{translator}"\n'
                if 'glm' in translator and gpt_token:
                    if 'GPT35:' in line:
                        lines[idx+4] = f"      - token: {gpt_token}\n"
                        lines[idx+6] = f"    defaultEndpoint: https://open.bigmodel.cn/api/paas\n"
                        lines[idx+7] = f'    rewriteModelName: "{translator}"\n'
                if 'abab' in translator and gpt_token:
                    if 'GPT35:' in line:
                        lines[idx+4] = f"      - token: {gpt_token}\n"
                        lines[idx+6] = f"    defaultEndpoint: https://api.minimax.chat\n"
                        lines[idx+7] = f'    rewriteModelName: "{translator}"\n'
                if proxy_address:
                    if 'proxy' in line:
                        lines[idx+1] = f"  enableProxy: true\n"
                        lines[idx+3] = f"    - address: {proxy_address}\n"
                else:
                    if 'proxy' in line:
                        lines[idx+1] = f"  enableProxy: false\n"

            if 'moonshot' in translator or 'qwen' in translator or 'glm' in translator or 'abab' in translator:
                translator = 'gpt35-0613'
            
            if 'index' in translator:
                translator = 'sakura-009'

            if 'Galtransl' in translator:
                translator = 'sakura-010'

            with open('project/config.yaml', 'w', encoding='utf-8') as f:
                f.writelines(lines)


            if 'sakura' in translator:
                self.status.emit("[INFO] 正在启动Sakura翻译器...")
                if not sakura_file:
                    self.status.emit("[INFO] 未选择模型文件，跳过翻译步骤...")
                    continue

                import subprocess
                self.pid = subprocess.Popen(['llama/server.exe', '-m', 'llama/'+sakura_file, '-c', '2048', '-ngl' , str(sakura_mode), '--host', '127.0.0.1', '--port', '8989'], stdout=self.log, stderr=self.log)

            self.status.emit("[INFO] 正在进行翻译...")
            from GalTransl.__main__ import worker
            worker('project', 'config.yaml', translator, show_banner=False)

            self.status.emit("[INFO] 正在生成字幕文件...")
            make_srt(output_file_path.replace('gt_input','gt_output'), input_file+'.zh.srt')
            make_lrc(output_file_path.replace('gt_input','gt_output'), input_file+'.lrc')
            self.status.emit("[INFO] 字幕文件生成完成！")

            if 'sakura' in translator:
                self.pid.kill()
                self.pid.terminate()

        self.status.emit("[INFO] 所有文件处理完成！")
        self.finished.emit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
