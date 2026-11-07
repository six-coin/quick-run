"""Logging bootstrap built on loguru.

Why loguru instead of the hand written module: thread/process safe queueing,
rotation and retention built in, and no relative paths. The sink path is always
absolute (``app.paths.LOG_DIR``), so a stray working directory can never make
the app scatter ``logs/`` folders around the disk again.
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
    """Configure the global logger once and return the log file path."""
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
        format=_LOG_FORMAT,
    )

    LOG_FILE = log_file
    _CONFIGURED = True
    sys.excepthook = _excepthook
    threading.excepthook = _thread_excepthook

    logger.info("已初始化日志文件：{}", log_file)
    return log_file


def fatal(message: str, title: str = "Fast Run - 启动失败") -> None:
    """Log a fatal error, tell the user and terminate."""
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
    """Native message box so fatal errors also surface from ``.pyw`` processes."""
    try:
        ctypes.windll.user32.MessageBoxW(None, str(text), str(title), 0x00000010)
    except Exception:
        pass
