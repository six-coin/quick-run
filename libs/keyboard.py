import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import Signal, QObject

from libs import log


class KeyboardWorker(QObject):
    user32 = ctypes.windll.user32  # 定义 Windows API
    MOD_ALT = 0x0001  # Alt 虚拟键码
    VK_SPACE = 0x20  # Space 虚拟键码
    HOTKEY_ID = 20100108  # 任意唯一 ID
    hotkey_pressed = Signal()

    def __init__(self):
        super().__init__()
        self.registered = False

    def _register_hotkey(self):
        # 注册全局热键：Alt + Space
        if self.user32.RegisterHotKey(
                None,  # 窗口句柄（None 表示全局）
                self.HOTKEY_ID,  # 快捷键唯一 ID
                self.MOD_ALT,  # 修饰键（Alt）
                self.VK_SPACE  # 主键（Space）
        ):
            self.registered = True
            log.write("快捷键 Alt+Space 成功注册", 3)
        else:
            error_code = ctypes.get_last_error()
            log.write(f"快捷键 Alt+Space 注册失败，错误码：{error_code}", 0)

    def run(self):
        self._register_hotkey()
        if not self.registered:  # 如果注册失败，直接退出程序
            os._exit(0)

        msg = wintypes.MSG()
        while True:
            # GetMessage 会阻塞直到有消息
            if self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == 0x0312:  # WM_HOTKEY
                    if msg.wParam == self.HOTKEY_ID:
                        self.hotkey_pressed.emit()
                self.user32.TranslateMessage(ctypes.byref(msg))
                self.user32.DispatchMessageW(ctypes.byref(msg))
