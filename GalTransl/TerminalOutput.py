from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
import json
import os
import threading
import time

from alive_progress import alive_bar


class NullProgressBar:
    def __call__(self, *args: Any, **kwargs: Any) -> None:
        return

    def title(self, *args: Any, **kwargs: Any) -> None:
        return

    def text(self, *args: Any, **kwargs: Any) -> None:
        return


class DesktopProgressBar(NullProgressBar):
    """Emit line-delimited progress even when translation text logging is off."""
    def __init__(self, total):
        self.total = max(0, int(total or 0))
        self.done = 0
        self.started = time.monotonic()
        self.last_emit = 0
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self._emit()
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)
        self.thread.start()

    def _emit(self):
        self.last_emit = time.monotonic()
        print('VOICETRANSL_PROGRESS ' + json.dumps({
            'done': self.done, 'total': self.total,
            'seconds': int(self.last_emit - self.started),
        }), flush=True)

    def __call__(self, count=1, **kwargs):
        with self.lock:
            self.done = min(self.total, max(0, self.done + int(count)))
            if self.done == self.total or time.monotonic() - self.last_emit >= 1:
                self._emit()

    def _heartbeat(self):
        while not self.stop.wait(30):
            with self.lock:
                self._emit()

    def close(self):
        self.stop.set()
        self.thread.join()
        with self.lock:
            self._emit()


def should_print_translation_logs(project_config: Any) -> bool:
    """Return True only for CLI (interactive) jobs.

    Server-started jobs (non_interactive=True) never use alive_bar
    or print translation content to the terminal.
    """
    if getattr(project_config, "non_interactive", False):
        return False
    return bool(getattr(project_config, "print_translation_log_in_terminal", True))


@contextmanager
def terminal_progress(enabled: bool, desktop: bool = False, **kwargs: Any) -> Iterator[Any]:
    if desktop and os.environ.get('VOICETRANSL_PROGRESS') == '1':
        bar = DesktopProgressBar(kwargs.get('total', 0))
        try:
            yield bar
        finally:
            bar.close()
        return
    if enabled:
        with alive_bar(**kwargs) as bar:
            yield bar
        return
    yield NullProgressBar()
