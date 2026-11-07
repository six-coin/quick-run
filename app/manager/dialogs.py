"""Native dialogs used by the manager window.

The close-confirmation must not depend on the web view: ``closing`` fires on the
UI thread, and calling ``evaluate_js`` from there blocks (or deadlocks) while it
waits for the very same thread to pump messages. A Win32 message box runs its
own modal loop on the current thread and is always safe.
"""

from __future__ import annotations

import ctypes

from loguru import logger

_MB_YESNOCANCEL = 0x00000003
_MB_ICONWARNING = 0x00000030
_MB_SETFOREGROUND = 0x00010000
_MB_TOPMOST = 0x00040000

_IDYES = 6
_IDNO = 7

_TITLE = "Fast Run 操作管理器"
_MESSAGE = (
    "有未保存的更改。\n\n"
    "是：保存后关闭\n"
    "否：不保存直接关闭\n"
    "取消：返回继续编辑"
)


def confirm_unsaved() -> str:
    """Return ``"save"``, ``"discard"`` or ``"cancel"``."""
    try:
        result = ctypes.windll.user32.MessageBoxW(
            None,
            _MESSAGE,
            _TITLE,
            _MB_YESNOCANCEL | _MB_ICONWARNING | _MB_SETFOREGROUND | _MB_TOPMOST,
        )
    except Exception as error:  # noqa: BLE001 - never block closing on a dialog bug
        logger.warning("显示未保存提示失败：{}", error)
        return "cancel"

    if result == _IDYES:
        return "save"
    if result == _IDNO:
        return "discard"
    return "cancel"
