import json, argparse

from datetime import timedelta
def format_result(result):
    seconds = int(result)
    mm, ss = divmod(seconds, 60)
    hh, mm= divmod(mm, 60)
    ms = (result * 1000) % 1000
    return "%02d:%02d:%02d,%03d"%(hh,mm,ss,ms)

def format_result_lrc(result):
    seconds = int(result)
    mm, ss = divmod(seconds, 60)
    ms = (result * 1000) % 1000
    return "%02d:%02d.%03d"%(mm,ss,ms)

def make_srt(input_file, output_file):
    with open(input_file, encoding='utf-8') as f:
        data = json.load(f)

    with open(output_file, 'w', encoding="utf-8") as f:
        for i, d in enumerate(data):
            print(i+1, file=f)
            print(format_result(d["start"])+" --> "+format_result(d["end"]),file=f)
            print(d["message"], file=f)
            print("", file=f)
        
def make_lrc(input_file, output_file):
    with open(input_file, encoding='utf-8') as f:
        data = json.load(f)

    with open(output_file, 'w', encoding="utf-8") as f:
        for i, d in enumerate(data):
            print("["+format_result_lrc(d["start"])+"] "+d["message"], file=f)

def merge_lrc_files(input_files, output_file):
    lines = []
    for input_file in input_files:
        with open(input_file, encoding='utf-8') as f:
            lines.extend(f.readlines())

    # Sort lines by timestamp (string sort works for [mm:ss.xx])
    lines.sort()

    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i","--input_file", type=str, required=True)
    parser.add_argument("-o","--output_file", type=str, required=True)
    args = parser.parse_args()
    make_srt(args.input_file, args.output_file)