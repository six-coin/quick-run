"""Global hotkey (Alt+Space) via ``RegisterHotKey`` on a dedicated thread.

Differences from the old implementation:

* ``WinDLL(..., use_last_error=True)`` so a failure actually yields an error
  code instead of a meaningless ``get_last_error()``;
* registration failures are reported to the caller instead of silently calling
  ``os._exit(0)``;
* the thread can be stopped cleanly, and the hotkey is unregistered.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

from loguru import logger

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
        """Block until registration finished; False means "unknown yet"."""
        return self._ready.wait(timeout)

    def run(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._thread_id = kernel32.GetCurrentThreadId()

        if not user32.RegisterHotKey(
            None, self._hotkey_id, self._modifiers, self._virtual_key
        ):
            code = ctypes.get_last_error()
            self.error = f"全局快捷键 {self._label} 注册失败（错误码 {code}），可能已被其他程序占用"
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
