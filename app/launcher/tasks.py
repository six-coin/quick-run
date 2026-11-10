"""翻译 / 查词 / 计算用的后台任务执行器。

每个结果都带一个“代次”编号。查询一变（或窗口收起）代次就加一，于是上一次
查询迟到的结果会被直接丢掉，而不会覆盖当前列表——结果和查询一一对应，
不会出现张冠李戴。

QRunnable 在报告完成之前一直保留引用，否则 Qt 还在跑的时候，PySide 可能已经
把 Python 包装对象回收了。
"""

from __future__ import annotations

from collections.abc import Callable

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
        except Exception as error:  # 异常会转交界面线程显示
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
