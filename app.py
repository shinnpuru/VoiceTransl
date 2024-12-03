# follow main.py to create a web-based demo
import sys, os, shutil
sys.path.append(os.path.dirname(__file__))
import gradio as gr

TRANSLATOR_SUPPORTED = [
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

def worker(input_files, yt_url, model_size, translator, gpt_token, sakura_file, sakura_mode, proxy_address, before_dict, gpt_dict, after_dict):
    print("正在初始化项目文件夹...")
    if before_dict:
        with open('sampleProject/项目字典_译前.txt', 'w', encoding='utf-8') as f:
            f.write(before_dict.replace(' ','\t'))
    else:
        import os
        if os.path.exists('sampleProject/项目字典_译前.txt'):
            os.remove('sampleProject/项目字典_译前.txt')
    if gpt_dict:
        with open('sampleProject/项目GPT字典.txt', 'w', encoding='utf-8') as f:
            f.write(gpt_dict.replace(' ','\t'))
    else:
        import os
        if os.path.exists('sampleProject/项目GPT字典.txt'):
            os.remove('sampleProject/项目GPT字典.txt')
    if after_dict:
        with open('sampleProject/项目字典_译后.txt', 'w', encoding='utf-8') as f:
            f.write(after_dict.replace(' ','\t'))
    else:
        import os
        if os.path.exists('sampleProject/项目字典_译后.txt'):
            os.remove('sampleProject/项目字典_译后.txt')

    if not input_files:
        input_files = []

    if yt_url:
        input_files.extend(yt_url.split('\n'))

    for input_file in input_files:
        if not os.path.exists(input_file) and ('youtu.be' in input_file or 'youtube.com' in input_file):
            from yt_dlp import YoutubeDL
            import os
            if os.path.exists('sampleProject/YoutubeDL.webm'):
                os.remove('sampleProject/YoutubeDL.webm')
            with YoutubeDL({'proxy': proxy_address,'outtmpl': 'sampleProject/YoutubeDL.webm'}) as ydl:
                print("正在下载视频...")
                results = ydl.download([input_file])
                print("视频下载完成！")
            input_file = 'sampleProject/YoutubeDL.webm'

        elif not os.path.exists(input_file) and 'BV' in yt_url:
            from bilibili_dl.bilibili_dl.Video import Video
            from bilibili_dl.bilibili_dl.downloader import download
            from bilibili_dl.bilibili_dl.utils import send_request
            from bilibili_dl.bilibili_dl.constants import URL_VIDEO_INFO
            print("正在下载视频...")
            res = send_request(URL_VIDEO_INFO, params={'bvid': input_file})
            download([Video(
                bvid=res['bvid'],
                cid=res['cid'] if res['videos'] == 1 else res['pages'][0]['cid'],
                title=res['title'] if res['videos'] == 1 else res['pages'][0]['part'],
                up_name=res['owner']['name'],
                cover_url=res['pic'] if res['videos'] == 1 else res['pages'][0]['pic'],
            )], False)
            print("视频下载完成！")
            import re
            title = res['title'] if res['videos'] == 1 else res['pages'][0]['part']
            title = re.sub(r'[.:?/\\]', ' ', title).strip()
            title = re.sub(r'\s+', ' ', title)
            input_file = f'{title}.mp4'

        print("-"*50)
        print("当前处理文件：", input_file)
        import os
        os.makedirs('sampleProject/cache', exist_ok=True)
        if os.path.exists(os.path.join('sampleProject/cache', os.path.basename(input_file))):
            os.remove(os.path.join('sampleProject/cache', os.path.basename(input_file)))
        input_file = shutil.move(input_file, 'sampleProject/cache/')

        from prompt2srt import make_srt, make_lrc
        if input_file.endswith('.srt'):
            from srt2prompt import make_prompt
            print("正在进行字幕转换...")
            os.makedirs('sampleProject/gt_input', exist_ok=True)
            output_file_path = os.path.join('sampleProject/gt_input', os.path.basename(input_file).replace('.srt','.json'))

            make_prompt(input_file, output_file_path)
            print("字幕转换完成！")
        else:
            print("正在进行语音识别...")
            from whisper2prompt import execute_asr
            output_file_path = execute_asr(
                input_file  = input_file,
                output_folder = 'sampleProject/gt_input',
                model_size    = model_size,
                language      = 'ja',
                precision     = 'float16',
            )
            print("语音识别完成！")
            make_srt(output_file_path, input_file+'.raw.srt')

        if translator is None:
            print("翻译器未选择，跳过翻译步骤...")
            continue

        print("正在进行翻译配置...")
        with open('sampleProject/config.yaml', 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for idx, line in enumerate(lines):
            if 'gpt' in translator and gpt_token:
                if 'GPT35' in line:
                    lines[idx+2] = f"      - token: {gpt_token}\n"
                    lines[idx+6] = f"    defaultEndpoint: https://api.openai.com\n"
                    lines[idx+7] = f'    rewriteModelName: ""\n'
                if 'GPT4' in line:
                    lines[idx+2] = f"      - token: {gpt_token}\n"
            if 'moonshot' in translator and gpt_token:
                if 'GPT35' in line:
                    lines[idx+4] = f"      - token: {gpt_token}\n"
                    lines[idx+6] = f"    defaultEndpoint: https://api.moonshot.cn\n"
                    lines[idx+7] = f'    rewriteModelName: "moonshot-v1-8k"\n'
            if 'qwen' in translator and gpt_token:
                if 'GPT35' in line:
                    lines[idx+4] = f"      - token: {gpt_token}\n"
                    lines[idx+6] = f"    defaultEndpoint: https://dashscope.aliyuncs.com/compatible-mode\n"
                    lines[idx+7] = f'    rewriteModelName: "{translator}"\n'
            if 'glm' in translator and gpt_token:
                if 'GPT35' in line:
                    lines[idx+4] = f"      - token: {gpt_token}\n"
                    lines[idx+6] = f"    defaultEndpoint: https://open.bigmodel.cn/api/paas\n"
                    lines[idx+7] = f'    rewriteModelName: "{translator}"\n'
            if 'abab' in translator and gpt_token:
                if 'GPT35' in line:
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

        with open('sampleProject/config.yaml', 'w', encoding='utf-8') as f:
            f.writelines(lines)


        if 'sakura' in translator:
            print("启动Sakura翻译器...")
            if not sakura_file or not sakura_file.endswith('.gguf'):
                print("未选择模型文件，跳过翻译步骤...")
                continue

            import subprocess
            pid = subprocess.Popen(['./venv/Scripts/python', '-m', 'llama_cpp.server', '--model', sakura_file, '--n_ctx', '2048', '--n_gpu_layers' , str(sakura_mode), '--host', '127.0.0.1', '--port', '8080'])

        print("正在进行翻译...")
        from GalTransl.__main__ import worker
        worker('sampleProject', 'config.yaml', translator, show_banner=False)

        print("正在生成字幕文件...")
        make_srt(output_file_path.replace('gt_input','gt_output'), input_file+'.srt')
        make_lrc(output_file_path.replace('gt_input','gt_output'), input_file+'.lrc')
        print("字幕文件生成完成！")
        print("缓存地址为：", input_file)

        if 'sakura' in translator:
            pid.kill()

def cleaner():
    print("正在清理中间文件...")
    if os.path.exists('sampleProject/gt_input'):
        shutil.rmtree('sampleProject/gt_input')
    if os.path.exists('sampleProject/gt_output'):
        shutil.rmtree('sampleProject/gt_output')
    if os.path.exists('sampleProject/transl_cache'):
        shutil.rmtree('sampleProject/transl_cache')
    print("正在清理输出...")
    if os.path.exists('sampleProject/cache'):
        shutil.rmtree('sampleProject/cache')

with gr.Blocks() as demo:
    gr.Markdown("# 欢迎使用GalTransl for ASMR！")
    gr.Markdown("您可以使用本程序将日语音视频文件/字幕文件转换为中文字幕文件。")
    with gr.Accordion("1. 选择输入", open=True):
        input_file = gr.Files(label="请选择音视频文件/SRT文件或拖拽文件到窗口（可多选）。")
        yt_url = gr.Textbox(label="或者输入YouTube视频链接（包含youtu.be或者youtube.com）或者Bilibili的BV号进行下载。（空行区分不同视频）", placeholder="例如：https://www.youtube.com/watch?v=...\n例如：BV1Lxt5e8EJF")
        proxy_address = gr.Textbox(label="请输入网络访问代理地址（可选）。", placeholder="例如：http://127.0.0.1:7890，留空为不使用代理。")
    with gr.Accordion("2. 语音识别", open=True):
        model_size = gr.Radio(
            label="请选择语音识别模型大小:",
            choices=['small', 'medium', 'large-v3',],
            value='large-v3'
        )
    with gr.Accordion("3. 字幕翻译（可选）", open=False):
        translator = gr.Radio(
            label="请选择翻译模型：",
            choices=TRANSLATOR_SUPPORTED,
            value="Galtransl"
        )
        gpt_token = gr.Textbox(label="请输入在线模型API令牌。 (如果选择GPT, Moonshot, Qwen, GLM, MiniMax/abab)", placeholder="留空为使用上次配置的Token。")
        model_list = [i for i in os.listdir('.') if i.endswith('gguf')]
        sakura_file = gr.Dropdown(label="请选择本地模型文件。(如果选择Sakura, Index, Galtransl）", choices=model_list, value=model_list[0])
        sakura_mode = gr.Slider(label="请选择本地模型模式，0代表完全使用CPU，999代表完全使用GPU。 (如果选择Sakura, Index, Galtransl）", minimum=0, maximum=999, step=1, value=999)
    with gr.Accordion("4. 翻译字典（可选）", open=False):
        with gr.Row():
            before_dict = gr.Textbox(label="输入替换字典。（日文到日文）", placeholder="日文\t日文\n日文\t日文")
            gpt_dict = gr.Textbox(label="翻译替换字典。（日文到中文，不支持sakura-009，Index）", placeholder="日文\t中文\n日文\t中文")
            after_dict = gr.Textbox(label="输出替换字典。（中文到中文）", placeholder="中文\t中文\n中文\t中文")


    run = gr.Button("5. 运行（状态详情请见命令行）")
    clean = gr.Button("6.清空输入输出缓存（请在保存完成后点击）")
    files = gr.FileExplorer(root_dir="sampleProject/cache",file_count="single")
    refresh = gr.Button("7. 刷新文件列表")
    download = gr.DownloadButton("8. 下载（单选）")

    def update_file1():
        return gr.FileExplorer(root_dir=".",file_count="single")
    def update_file2():
        return gr.FileExplorer(root_dir="sampleProject/cache",file_count="single")

    refresh.click(update_file1, outputs=files).then(update_file2, outputs=files)

    run.click(worker, inputs=[input_file, yt_url, model_size, translator, gpt_token, sakura_file, sakura_mode, proxy_address, before_dict, gpt_dict, after_dict], queue=True)
    clean.click(cleaner, inputs=[])
    files.change(lambda x: x, files, download)

demo.queue().launch(inbrowser=True, server_name='0.0.0.0', server_port=6006)
