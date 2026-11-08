"""启动器弹出时隐藏任务栏。

启动器要的是一种“浮层”感觉。当前台是全屏程序（游戏、视频）时，我们的窗口
一显示就会把 Windows 任务栏顶到最前面，所以在弹出期间先隐藏任务栏，
窗口收起后再恢复。
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
    """判断前台窗口是否正好铺满整个屏幕。"""
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
