"""Taskbar hiding while the launcher is open.

The launcher is meant to feel like an overlay. When a fullscreen application is
in the foreground (a game, a video), Windows' taskbar would otherwise pop up on
top of it when our window is shown, so we hide it for the lifetime of the popup
and restore it on hide.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from loguru import logger

_user32 = ctypes.windll.user32


class _Rect(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def is_fullscreen_foreground() -> bool:
    """Heuristic kept from the old version: foreground window covers the screen."""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return False

        rect = _Rect()
        if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False

        width = rect.right - rect.left
        height = rect.bottom - rect.top
        return width == _user32.GetSystemMetrics(0) and height == _user32.GetSystemMetrics(1)
    except Exception as error:
        logger.warning("检测任务栏时发生错误：{}", error)
        return False


def hide() -> None:
    _show_taskbar(0)


def show() -> None:
    _show_taskbar(9)


def _show_taskbar(command: int) -> None:
    try:
        hwnd = _user32.FindWindowA(b"Shell_TrayWnd", None)
        if hwnd:
            _user32.ShowWindow(hwnd, command)
    except Exception as error:
        logger.warning("切换任务栏显示状态时发生错误：{}", error)
