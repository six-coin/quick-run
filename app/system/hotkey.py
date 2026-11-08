"""在独立线程上用 ``RegisterHotKey`` 注册全局热键（Alt+Space）。

要点：

* 用 ``WinDLL(..., use_last_error=True)``，失败时才真的拿得到错误码；
* 注册失败会把原因交给调用方去弹窗，不静默退出；
* 线程可以干净地停下来，并且会注销热键。
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

from loguru import logger

from app import i18n

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012


class HotkeyListener(threading.Thread):
    def __init__(
        self,
        callback: Callable[[], None],
        modifiers: int = MOD_ALT | MOD_NOREPEAT,
        virtual_key: int = VK_SPACE,
        hotkey_id: int = 0xFA57,
        name: str = "Alt+Space",
    ) -> None:
        super().__init__(name="hotkey-listener", daemon=True)
        self._callback = callback
        self._modifiers = modifiers
        self._virtual_key = virtual_key
        self._hotkey_id = hotkey_id
        self._label = name
        self._ready = threading.Event()
        self._thread_id: int | None = None
        self.error: str | None = None

    def wait_ready(self, timeout: float = 3.0) -> bool:
        """阻塞等待注册结果；返回 False 只表示“还不知道”。"""
        return self._ready.wait(timeout)

    def run(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._thread_id = kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(
            None, self._hotkey_id, self._modifiers, self._virtual_key
        ):
            code = ctypes.get_last_error()
            self.error = i18n.t("fatal.hotkey_failed", label=self._label, code=code)
            logger.error(self.error)
            self._ready.set()
            return

        logger.info("全局快捷键 {} 注册成功", self._label)
        self._ready.set()

        message = wintypes.MSG()
        try:
            while True:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                if message.message == WM_HOTKEY and message.wParam == self._hotkey_id:
                    try:
                        self._callback()
                    except Exception:
                        logger.exception("处理快捷键回调时出错")
        finally:
            user32.UnregisterHotKey(None, self._hotkey_id)

    def stop(self) -> None:
        if self._thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
