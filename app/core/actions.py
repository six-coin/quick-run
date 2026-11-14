"""动作执行：把一条 :class:`ResultRow` 变成真正的副作用。

所有和系统相关的东西都通过小协议注入，所以这个模块不启动任何进程也能做单元
测试。它不会修改进程的工作目录：目标目录永远以参数形式交给启动器。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from loguru import logger

from app import paths
from app.core.rows import ResultRow, RowKind, RowStatus
from app.core.services.search import baidu_translate_url, bing_url
from app.models import Operation, OperationType


@dataclass(frozen=True)
class Modifiers:
    ctrl: bool = False
    shift: bool = False
    alt: bool = False

    @property
    def any(self) -> bool:
        return self.ctrl or self.shift or self.alt


@dataclass(frozen=True)
class ActionOutcome:
    hide: bool = True
    clipboard_text: str | None = None


class Opener(Protocol):
    def open_file(self, path, *, cwd, no_window: bool = False) -> None: ...

    def open_dir(self, path) -> None: ...

    def open_url(self, url: str) -> None: ...

    def run_command(self, command: str, *, cwd) -> None: ...

    def debug(self, function: str) -> None: ...


class Speech(Protocol):
    def speak(self, text: str) -> bool: ...


class ActionExecutor:
    """执行一条结果行。

    复制到剪贴板由调用方完成，因为执行结果里只带“应该被复制的文本”。
    """

    def __init__(self, opener: Opener, speech: Speech) -> None:
        self._opener = opener
        self._speech = speech

    def execute(self, row: ResultRow, modifiers: Modifiers | None = None) -> ActionOutcome:
        modifiers = modifiers or Modifiers()
        handler = {
            RowKind.EXTERNAL: self._external,
            RowKind.SEARCH: self._search,
            RowKind.EXPLORE: self._explore,
            RowKind.CALCULATE: self._copyable,
            RowKind.DEFINITION: self._copyable,
            RowKind.TRANSLATE: self._translate,
            RowKind.ERROR: lambda *_: ActionOutcome(hide=True),
        }.get(row.kind)

        if handler is None:
            return ActionOutcome(hide=True)
        return handler(row, modifiers)

    # -- 各类结果行的处理 ---------------------------------------------------
    def _external(self, row: ResultRow, modifiers: Modifiers) -> ActionOutcome:
        operation: Operation = row.payload

        if operation.type == OperationType.DEBUG:
            self._opener.debug(str(operation.arguments.get("function", "restart")))
            logger.info("操作成功执行：{}（debug）", operation.display)
            return ActionOutcome(hide=True)

        if operation.type == OperationType.FILE:
            self._open_files(operation, modifiers)
        elif operation.type == OperationType.DIR:
            self._open_dirs(operation)
        elif operation.type == OperationType.URL:
            self._opener.open_url(str(operation.arguments.get("url", "")))
        elif operation.type == OperationType.CMD:
            self._opener.run_command(
                str(operation.arguments.get("command", "")), cwd=paths.PROGRAM_DIR
            )

        logger.info("操作成功执行：{}（{}）", operation.display, operation.type)
        return ActionOutcome(hide=True)

    def _open_files(self, operation: Operation, modifiers: Modifiers) -> None:
        no_window = bool(operation.arguments.get("no_window", False))
        base = paths.normalize_path_base(operation.arguments.get("base"))
        for path in paths.split_paths(str(operation.arguments.get("path", "")), base):
            if modifiers.any:
                # 按住 Ctrl / Shift / Alt 时改成打开所在文件夹。
                self._opener.open_dir(path.parent)
                continue
            if path.is_file():
                # 工作目录恒为程序目录，不跟着目标文件走。
                self._opener.open_file(path, cwd=paths.PROGRAM_DIR, no_window=no_window)
            else:
                logger.warning("打开文件 {} 时出错：文件不存在或不是文件", path)

    def _open_dirs(self, operation: Operation) -> None:
        base = paths.normalize_path_base(operation.arguments.get("base"))
        for path in paths.split_paths(str(operation.arguments.get("dir", "")), base):
            if path.is_dir():
                self._opener.open_dir(path)
            else:
                logger.warning("打开路径 {} 时出错：路径不存在或不是路径", path)

    def _search(self, row: ResultRow, _modifiers: Modifiers) -> ActionOutcome:
        self._opener.open_url(bing_url(str(row.payload)))
        logger.info("操作成功执行：搜索")
        return ActionOutcome(hide=True)

    def _explore(self, row: ResultRow, _modifiers: Modifiers) -> ActionOutcome:
        entry = row.payload
        if entry.is_dir:
            self._opener.open_dir(entry.path)
        else:
            self._opener.open_file(entry.path, cwd=paths.PROGRAM_DIR, no_window=False)
        return ActionOutcome(hide=True)

    def _copyable(self, row: ResultRow, _modifiers: Modifiers) -> ActionOutcome:
        """计算和查词行：算完了就复制并收起，没算完就保持打开。"""
        if row.status is RowStatus.DONE and row.value is not None:
            return ActionOutcome(hide=True, clipboard_text=row.value)
        return ActionOutcome(hide=False)

    def _translate(self, row: ResultRow, modifiers: Modifiers) -> ActionOutcome:
        text = str(row.payload)
        if modifiers.any and len(text) < 1000:
            self._speech.speak(text)
        else:
            self._opener.open_url(baidu_translate_url(text))
        logger.info("操作成功执行：翻译")
        return ActionOutcome(hide=True)
