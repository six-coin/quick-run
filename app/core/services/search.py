"""内置网页动作的 URL 构造。"""

from __future__ import annotations

from urllib.parse import quote


def bing_url(text: str) -> str:
    return f"https://cn.bing.com/search?q={quote(text)}"


def baidu_translate_url(text: str) -> str:
    return f"https://fanyi.baidu.com/mtpe-individual/transText?query={quote(text)}&lang=auto2auto#/"


def tts_url(text: str) -> str:
    language = "en" if _is_ascii(text) else "zh"
    return f"https://fanyi.baidu.com/gettts?lan={language}&text={quote(text)}&spd=3&source=web"


def _is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True
