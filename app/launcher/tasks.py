"""后台任务执行器：一类算结果，一类做副作用。

``TaskRunner`` 负责翻译 / 查词 / 计算。每个结果都带一个“代次”编号。查询一变
（或窗口收起）代次就加一，于是上一次查询迟到的结果会被直接丢掉，而不会覆盖
当前列表——结果和查询一一对应，不会出现张冠李戴。

``ActionRunner`` 负责执行结果行的副作用（打开文件、网址、朗读）。它不关心
代次：动作一旦被用户确认就必须发生，迟到的“取消”是不存在的。它存在的唯一
理由是让界面线程别被 ``ShellExecute`` 拖住。

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


class _ActionSignals(QObject):
    done = Signal(object)


class _Action(QRunnable):
    def __init__(self, function: Callable[[], object], signals: _ActionSignals) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.finished = False
        self._function = function
        self._signals = signals

    def run(self) -> None:
        outcome: object = None
        try:
            outcome = self._function()
        except Exception:  # 副作用失败不该带走整个进程
            logger.exception("执行操作时出现未捕获的异常")
        finally:
            self.finished = True
        self._signals.done.emit(outcome)


class ActionRunner(QObject):
    """在界面线程之外执行一条结果行的副作用。

    打开文件 / 网址最终都落到 ``ShellExecuteW`` 上，它会一直等到关联程序给出
    回应才返回：浏览器走 DDE 要等握手，慢的 exe 还要被安全软件先扫一遍。这几
    百毫秒到一两秒如果占着界面线程，窗口就僵在满不透明的状态，用户看到的是
    “按了回车没反应”。

    动作没有代次的概念——用户按下的那一下必须生效，所以这里只按提交顺序把
    结果送回界面线程。
    """

    #: 执行完成，携带 ``ActionOutcome``；线程里出异常时为 ``None``
    finished = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._signals = _ActionSignals()
        self._signals.done.connect(self.finished)
        self._tasks: list[_Action] = []

    def submit(self, function: Callable[[], object]) -> None:
        task = _Action(function, self._signals)
        self._tasks = [item for item in self._tasks if not item.finished]
        self._tasks.append(task)
        self._pool.start(task)
