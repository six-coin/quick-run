"""剪贴板读写。"""

from __future__ import annotations

import pyperclip
from loguru import logger


class PyperclipClipboard:
    """很薄的一层封装，方便用假剪贴板测试执行器。"""

    def copy(self, text: str) -> None:
        try:
            pyperclip.copy(text)
            logger.info("已复制到剪贴板：{}", text[:60])
        except Exception as error:
            logger.warning("写入剪贴板失败：{}", error)
