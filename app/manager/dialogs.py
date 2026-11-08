"""管理器用到的原生对话框。

关闭确认正常情况下由网页自己弹（见 ``ManagerApi.request_close_prompt``），
这里只是兜底：网页还没加载完或者渲染进程挂了的时候，仍然要保证窗口关得掉。
``MessageBoxW`` 会在当前线程上跑自己的模态消息循环，从工作线程调用是安全的。
"""

from __future__ import annotations

import ctypes

from loguru import logger

from app import i18n

_MB_YESNOCANCEL = 0x00000003
_MB_ICONWARNING = 0x00000030
_MB_SETFOREGROUND = 0x00010000
_MB_TOPMOST = 0x00040000

_IDYES = 6
_IDNO = 7


def confirm_unsaved() -> str:
    """返回 ``"save"``、``"discard"`` 或 ``"cancel"``。"""
    try:
        result = ctypes.windll.user32.MessageBoxW(
            None,
            i18n.t("dialog.unsaved_text"),
            i18n.t("manager.title"),
            _MB_YESNOCANCEL | _MB_ICONWARNING | _MB_SETFOREGROUND | _MB_TOPMOST,
        )
    except Exception as error:  # 对话框出错也不能卡住关闭流程
        logger.warning("显示未保存提示失败：{}", error)
        return "cancel"

    if result == _IDYES:
        return "save"
    if result == _IDNO:
        return "discard"
    return "cancel"
