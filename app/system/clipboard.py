"""Clipboard access."""

from __future__ import annotations

import pyperclip
from loguru import logger


class PyperclipClipboard:
    """Thin wrapper so the executor can be tested with a fake clipboard."""

    def copy(self, text: str) -> None:
        try:
            pyperclip.copy(text)
            logger.info("已复制到剪贴板：{}", text[:60])
        except Exception as error:
            logger.warning("写入剪贴板失败：{}", error)
