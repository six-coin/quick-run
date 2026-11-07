"""Background task runner for translate / definition / calculate.

Results are tagged with a *generation* counter. Whenever the query changes (or
the window is hidden) the generation is bumped, so late results from a previous
query are dropped instead of overwriting the current list. The old code matched
results by a millisecond timestamp, which could collide and could not tell
"stale" from "current".

QRunnable instances are kept referenced until they report completion, otherwise
PySide could garbage collect the Python wrapper while Qt is still running it.
"""

from __future__ import annotations

from typing import Callable

from loguru import logger
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal


class _TaskSignals(QObject):
    done = Signal(str, int, bool, object)


class _Task(QRunnable):
    def __init__(
        self, key: str, generation: int, function: Callable[[], object], signals: _TaskSignals
    ) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.key = key
        self.generation = generation
        self.finished = False
        self._function = function
        self._signals = signals

    def run(self) -> None:
        try:
            result = self._function()
        except Exception as error:  # noqa: BLE001 - forwarded to the UI thread
            logger.debug("后台任务失败 {}：{}", self.key, error)
            self._signals.done.emit(self.key, self.generation, False, error)
        else:
            self._signals.done.emit(self.key, self.generation, True, result)
        finally:
            self.finished = True


class TaskRunner(QObject):
    finished = Signal(str, int, bool, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._signals = _TaskSignals()
        self._signals.done.connect(self._on_done)
        self._tasks: list[_Task] = []

        self._prune_timer = QTimer(self)
        self._prune_timer.setInterval(2000)
        self._prune_timer.timeout.connect(self._prune)
        self._prune_timer.start()

    def submit(self, key: str, generation: int, function: Callable[[], object]) -> None:
        task = _Task(key, generation, function, self._signals)
        self._tasks.append(task)
        self._pool.start(task)

    def _on_done(self, key: str, generation: int, ok: bool, payload: object) -> None:
        self.finished.emit(key, generation, ok, payload)

    def _prune(self) -> None:
        self._tasks = [task for task in self._tasks if not task.finished]
