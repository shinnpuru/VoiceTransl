import re
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ORIGINAL_STDOUT = sys.stdout
_ORIGINAL_STDERR = sys.stderr
from app import (
    NO_TRANSCRIPTION,
    NO_TRANSLATION,
    TRANSLATOR_SUPPORTED,
    _build_crispasr_command,
    _compose_output_format,
    _list_crispasr_aligners,
    _list_crispasr_backends,
    _list_crispasr_models,
)
sys.stdout = _ORIGINAL_STDOUT
sys.stderr = _ORIGINAL_STDERR


ROOT = Path(__file__).resolve().parents[1]
CRISPASR_DIR = ROOT / "crispasr"
AUDIO_FIXTURE = ROOT / "フリートークA 涼花みなせ.mp3"
MODEL_FILE = CRISPASR_DIR / "qwen3-asr-1.7b-q4_k.gguf"
ALIGNER_FILE = CRISPASR_DIR / "qwen3-forced-aligner-0.6b-q4_k.gguf"
EXECUTABLE = CRISPASR_DIR / "crispasr.exe"
PARAM_FILE = CRISPASR_DIR / "param.txt"


class CrispASRWorkflowTest(unittest.TestCase):
    def test_model_discovery_excludes_forced_aligner(self):
        models = _list_crispasr_models()
        aligners = _list_crispasr_aligners()
        self.assertIn(MODEL_FILE.name, models)
        self.assertNotIn(ALIGNER_FILE.name, models)
        self.assertIn(ALIGNER_FILE.name, aligners)
        self.assertNotIn(MODEL_FILE.name, aligners)
        self.assertIn("qwen3-1.7b", _list_crispasr_backends())
        self.assertNotIn(NO_TRANSCRIPTION, models)
        self.assertNotIn(NO_TRANSLATION, TRANSLATOR_SUPPORTED)

    def test_split_output_options_compose_the_pipeline_format(self):
        self.assertEqual(_compose_output_format("双语", "SRT", True), "双语SRT")
        self.assertEqual(_compose_output_format("目标", "LRC", True), "目标LRC")
        self.assertEqual(_compose_output_format("双语", "LRC", False), "原文LRC")

    def test_default_arguments_keep_alignment_without_strict_failure(self):
        parameter_template = PARAM_FILE.read_text(encoding="utf-8").strip()
        command = _build_crispasr_command(
            ROOT / "input.wav",
            ROOT / "transcript",
            MODEL_FILE,
            "ja",
            parameter_template,
            aligner_file=ALIGNER_FILE,
            backend="qwen3-1.7b",
        )
        self.assertIn("--force-aligner", command)
        self.assertIn("--split-on-punct", command)
        self.assertEqual(command[command.index("--vad-model") + 1], "firered")
        self.assertEqual(command[command.index("--vad-threshold") + 1], "0.3")
        self.assertNotIn("--strict-pipeline", command)
        self.assertNotIn("--require-word-timestamps", command)
        aligner_arg = command[command.index("--aligner-model") + 1]
        self.assertEqual(Path(aligner_arg), ALIGNER_FILE.resolve())
        self.assertEqual(command[command.index("--backend") + 1], "qwen3-1.7b")

    def test_selected_backend_overrides_a_legacy_hardcoded_template(self):
        command = _build_crispasr_command(
            ROOT / "input.wav",
            ROOT / "transcript",
            MODEL_FILE,
            "ja",
            "$crispasr_executable --backend whisper --model $model_file "
            "--aligner-model $aligner_file --output-srt --output-file $output_file "
            "--file $input_file",
            aligner_file=ALIGNER_FILE,
            backend="qwen3-1.7b",
        )
        self.assertEqual(command[command.index("--backend") + 1], "qwen3-1.7b")

    def test_length_slider_overrides_all_aliases_without_truncating_generation(self):
        template = PARAM_FILE.read_text(encoding='utf-8') + ' -ml 90 --max-len=80 --max-new-tokens 512'
        command = _build_crispasr_command(
            ROOT / 'input.wav', ROOT / 'transcript', MODEL_FILE, 'ja', template,
            aligner_file=ALIGNER_FILE, max_chars=30,
        )
        self.assertEqual(command.count('--max-len'), 1)
        self.assertEqual(command[command.index('--max-len') + 1], '30')
        self.assertNotIn('-ml', command)
        self.assertNotIn('--max-len=80', command)
        self.assertEqual([command[i + 1] for i, arg in enumerate(command) if arg == '--max-new-tokens'], ['96', '512'])
        default = _build_crispasr_command(
            ROOT / 'input.wav', ROOT / 'transcript', MODEL_FILE, 'ja', template,
            aligner_file=ALIGNER_FILE, max_chars=0,
        )
        self.assertIn('--max-len=80', default)

    @unittest.skipUnless(
        all(path.is_file() for path in (AUDIO_FIXTURE, MODEL_FILE, ALIGNER_FILE, EXECUTABLE)),
        "local CrispASR binaries, models, and MP3 fixture are required",
    )
    def test_transcribes_free_talk_mp3_to_japanese_srt(self):
        cache_root = ROOT / "project" / "cache"
        cache_root.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="crispasr_test_", dir=cache_root) as temp_dir:
            staged_input = Path(temp_dir) / "input.mp3"
            output_srt = Path(temp_dir) / "free_talk.srt"
            shutil.copyfile(AUDIO_FIXTURE, staged_input)
            command = _build_crispasr_command(
                staged_input,
                output_srt.with_suffix(''),
                MODEL_FILE,
                "ja",
                PARAM_FILE.read_text(encoding="utf-8").strip(),
                aligner_file=ALIGNER_FILE,
                backend="qwen3-1.7b",
            )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
                creationflags=0x08000000 if os.name == 'nt' else 0,
                check=False,
            )

            transcript = output_srt.read_text(encoding="utf-8-sig")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(transcript, r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}")
            self.assertGreater(len(transcript), 100)
            self.assertRegex(transcript, re.compile(r"[ぁ-んァ-ヶ一-龯]"))


if __name__ == "__main__":
    unittest.main()
