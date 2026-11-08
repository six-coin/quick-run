"""基于 loguru 的日志初始化。

选它是因为线程 / 进程安全的队列、轮转与保留策略都是内置的，而且不涉及相对
路径。日志文件路径永远是绝对路径（``app.paths.LOG_DIR``），工作目录再怎么变，
日志都落在同一个地方。
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from types import TracebackType

from loguru import logger

from app import paths

LOG_FILE: Path | None = None
_CONFIGURED = False

_LOG_FORMAT = "[{level}] [{time:YYYY-MM-DD HH:mm:ss}] {message}"


def setup(name: str) -> Path:
    """配置一次全局日志器，并返回日志文件路径。"""
    global LOG_FILE, _CONFIGURED
    if _CONFIGURED and LOG_FILE is not None:
        return LOG_FILE

    paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = paths.LOG_DIR / f"{name}_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"

    logger.remove()
    logger.add(
        str(log_file),
        level="DEBUG",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=False,
        rotation="5 MB",
        retention="14 days",
        format=_LOG_FORMAT,
    )

    LOG_FILE = log_file
    _CONFIGURED = True
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook

    logger.info("已初始化日志文件：{}", log_file)
    return log_file


def fatal(message: str, title: str = "Fast Run - 启动失败") -> None:
    """记录致命错误、弹窗告知用户，然后退出进程。"""
    try:
        logger.critical(message)
        logger.complete()
    except Exception:
        pass
    _message_box(message, title)
    os._exit(1)


def _excepthook(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    try:
        logger.opt(exception=(exc_type, exc_value, exc_tb)).critical("程序运行中出现未捕获的异常")
        logger.complete()
    except Exception:
        pass
    _message_box(
        f"程序运行中出现未捕获的异常：\n{exc_type.__name__}: {exc_value}\n\n"
        f"日志文件：{LOG_FILE}",
        "Fast Run - 程序错误",
    )


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    if args.exc_type is SystemExit:
        return
    try:
        logger.opt(exception=(args.exc_type, args.exc_value, args.exc_traceback)).critical(
            "线程 {} 中出现未捕获的异常", getattr(args.thread, "name", "?")
        )
    except Exception:
        pass


def _message_box(text: str, title: str) -> None:
    """用系统消息框，这样 ``.pyw`` 进程里的致命错误也能被用户看到。"""
    try:
        ctypes.windll.user32.MessageBoxW(None, str(text), str(title), 0x00000010)
    except Exception:
        pass
