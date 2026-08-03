import ctypes
from ctypes import wintypes

import win32gui

from libs import log

user32 = ctypes.windll.user32


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


def is_taskbar_hidden():
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        # 获取前台窗口矩形信息
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        window_width = rect.right - rect.left
        window_height = rect.bottom - rect.top

        # 获取主屏幕分辨率（只考虑主屏幕）
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)

        return screen_height == window_height and window_width == screen_width

    except Exception as e:
        log.write(f"检测任务栏时发生错误：{e}", 2)
        return False


def hide_taskbar():
    """隐藏任务栏"""
    try:
        hwnd = ctypes.windll.user32.FindWindowA(b"Shell_TrayWnd", None)
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0代表隐藏窗口
    except Exception as e:
        log.write(f"隐藏任务栏时发生错误：{e}", 2)


def show_taskbar():
    """恢复显示任务栏"""
    try:
        hwnd = ctypes.windll.user32.FindWindowA(b"Shell_TrayWnd", None)
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # 9代表显示窗口
        # 在显示窗口后使前台窗口重新获得焦点
        hwnd2 = win32gui.GetForegroundWindow()
        win32gui.SetForegroundWindow(hwnd2)
    except Exception as e:
        log.write(f"显示任务栏时发生错误：{e}", 2)
