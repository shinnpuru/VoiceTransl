import io
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

_ORIGINAL_STDOUT = sys.stdout
_ORIGINAL_STDERR = sys.stderr
from app import (
    ConcurrentTranslationPool,
    UIMessageQueue,
    MainWindow,
    _TranslationLogParser,
    _clean_control_chars,
    _compose_output_format,
    _decode_subprocess_line,
    _find_available_local_port,
    _line_passes_filter,
    _set_command_option,
    _split_command_template,
    _split_output_format,
    _strip_ansi,
    _stream_proc_to_queue,
)
sys.stdout = _ORIGINAL_STDOUT
sys.stderr = _ORIGINAL_STDERR


class AppFormattingTests(unittest.TestCase):
    def test_output_format_round_trip(self):
        self.assertEqual(_compose_output_format("双语", "SRT", True), "双语SRT")
        self.assertEqual(_compose_output_format("目标", "LRC", False), "原文LRC")
        self.assertEqual(_split_output_format("双语SRT"), ("双语", "SRT"))
        self.assertEqual(_split_output_format("目标LRC"), ("目标", "LRC"))
        self.assertEqual(_split_output_format("unknown"), ("unknown", ""))

    def test_command_option_replaces_separate_and_equals_forms(self):
        command = ["tool", "-m", "old", "--port=1"]
        _set_command_option(command, ("--model", "-m"), "--model", "new")
        _set_command_option(command, ("--port",), "--port", "2")
        _set_command_option(command, ("--backend",), "--backend", "qwen")
        self.assertEqual(command, ["tool", "-m", "new", "--port=2", "--backend", "qwen"])

    def test_command_template_preserves_quoted_argument(self):
        tokens = _split_command_template('tool --model "a model.gguf"')
        self.assertEqual(tokens, ["tool", "--model", "a model.gguf"])

    def test_log_text_cleaning_and_filtering(self):
        self.assertEqual(_strip_ansi("\x1b[31merror\x1b[0m"), "error")
        self.assertEqual(_clean_control_chars("abc\rthis is the longest line\x00"), "this is the longest line")
        self.assertEqual(_clean_control_chars("yg2|message"), "message")
        self.assertTrue(_line_passes_filter("plain", "ERROR+"))
        self.assertFalse(_line_passes_filter("[INFO] hello", "WARNING+"))
        self.assertTrue(_line_passes_filter("[ERROR] boom", "WARNING+"))

    def test_subprocess_decoding_falls_back_to_gbk(self):
        self.assertEqual(_decode_subprocess_line("中文".encode("gbk")), "中文")
        self.assertEqual(_decode_subprocess_line(b"ascii"), "ascii")

    def test_available_port_is_in_valid_range(self):
        port = _find_available_local_port()
        self.assertGreater(port, 0)
        self.assertLessEqual(port, 65535)


class MessageQueueAndLogParserTests(unittest.TestCase):
    def test_message_queue_logs_clean_text_drains_and_completes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "app.log"
            queue = UIMessageQueue(str(log_path))
            queue.put("detail", "\x1b[32mhello\x1b[0m")
            self.assertEqual(queue.drain(), [("detail", "\x1b[32mhello\x1b[0m")])
            self.assertEqual(log_path.read_text(encoding="utf-8"), "hello\n")
            self.assertFalse(queue.is_completion_ready())
            queue.set_completion_flag()
            queue.put_completion_sentinel()
            target, text = queue.drain()[0]
            self.assertTrue(queue.is_completion_ready())
            self.assertTrue(queue.is_completion_entry(target))
            self.assertEqual(text, "")

    def test_translation_log_parser_batches_destinations(self):
        parser = _TranslationLogParser()
        self.assertEqual(parser.feed("v--1-[A]"), [])
        self.assertEqual(parser.feed("> Src: 原文"), [])
        self.assertEqual(parser.feed("> Dst: 译文"), [])
        output = parser.feed("ordinary")
        self.assertEqual(json.loads(output[0]), {"id": 1, "dst": "译文"})
        self.assertEqual(output[1], "ordinary")

    def test_translation_log_parser_preserves_interrupted_record(self):
        parser = _TranslationLogParser()
        parser.feed("v--2")
        self.assertEqual(parser.feed("unexpected"), ["v--2", "unexpected"])

    def test_stream_process_forwards_clean_nonempty_lines(self):
        class Proc:
            stdout = io.BytesIO(b"\x1b[31merror\x1b[0m\n\n")

        class Queue:
            def __init__(self):
                self.items = []

            def put(self, target, text):
                self.items.append((target, text))

        queue = Queue()
        _stream_proc_to_queue(Proc(), queue, label="worker")
        self.assertEqual(queue.items, [("detail", "[worker] error")])


class TaskLifecycleTests(unittest.TestCase):
    class Signal:
        def __init__(self):
            self.slots = []

        def connect(self, slot):
            self.slots.append(slot)

        def emit(self):
            for slot in list(self.slots):
                slot()

    class Button:
        def __init__(self, enabled=True):
            self.enabled = enabled

        def setEnabled(self, enabled):
            self.enabled = enabled

    class Thread:
        def __init__(self):
            self.started = TaskLifecycleTests.Signal()
            self.finished = TaskLifecycleTests.Signal()
            self.running = False
            self.quit_requested = False
            self.interruption_requested = False

        def start(self):
            self.running = True

        def isRunning(self):
            return self.running

        def quit(self):
            self.quit_requested = True

        def requestInterruption(self):
            self.interruption_requested = True

        def deleteLater(self):
            pass

    class Worker:
        def __init__(self):
            self.finished = TaskLifecycleTests.Signal()
            self.show_model_dialog = TaskLifecycleTests.Signal()
            self.stop_requested = False

        def moveToThread(self, thread):
            self.thread = thread

        def run(self):
            pass

        def request_stop(self):
            self.stop_requested = True

        def deleteLater(self):
            pass

    class Window:
        _task_is_running = MainWindow._task_is_running
        _restore_task_button = MainWindow._restore_task_button
        _task_finished = MainWindow._task_finished
        _start_worker_task = MainWindow._start_worker_task
        _set_action_button_enabled = MainWindow._set_action_button_enabled
        cancel_task = MainWindow.cancel_task

        def __init__(self):
            self.thread = None
            self.worker = None
            self._active_task_button = None
            self._cancel_requested = False
            self._button_mirrors = []
            self.cancel_button = TaskLifecycleTests.Button(False)
            self.messages = []

        def _emit_status(self, message):
            self.messages.append(message)

    def test_cancel_blocks_restart_until_old_thread_finishes(self):
        window = self.Window()
        run_button = self.Button()
        first_thread = self.Thread()
        first_worker = self.Worker()
        second_thread = self.Thread()
        second_worker = self.Worker()

        with patch('app.QThread', side_effect=[first_thread, second_thread]), patch(
            'app.MainWorker', side_effect=[first_worker, second_worker]
        ):
            self.assertTrue(window._start_worker_task('run', run_button))
            window.cancel_task()

            self.assertTrue(first_worker.stop_requested)
            self.assertTrue(first_thread.quit_requested)
            self.assertTrue(first_thread.interruption_requested)
            self.assertFalse(window._start_worker_task('run', run_button))
            self.assertIs(window.thread, first_thread)

            first_worker.finished.emit()
            first_thread.running = False
            first_thread.finished.emit()
            self.assertIsNone(window.thread)
            self.assertTrue(run_button.enabled)
            self.assertFalse(window.cancel_button.enabled)

            self.assertTrue(window._start_worker_task('run', run_button))
            self.assertIs(window.thread, second_thread)

    def test_translation_pool_terminates_tracked_active_processes(self):
        class Process:
            terminated = False

            def poll(self):
                return None

            def terminate(self):
                self.terminated = True

        stop_event = threading.Event()
        pool = ConcurrentTranslationPool(
            project_dir='project',
            base_config_path='project/config.yaml',
            max_concurrent=1,
            stop_event=stop_event,
            msg_queue=None,
        )
        process = Process()
        pool._active_translate_procs.append(process)

        pool.request_stop()

        self.assertTrue(stop_event.is_set())
        self.assertTrue(process.terminated)


if __name__ == "__main__":
    unittest.main()
