"""界面文案的本地化支持。

所有面向用户的文本都放在 ``app/locales`` 目录下的 JSON 文件里：
键名是点分小写英文，值是该语言下的最终文本。代码里只写键，不写文案，
这样切换语言时不需要改动任何逻辑。

模板里可以用 ``{name}`` 这样的占位符，通过 ``t("键", name=值)`` 填充；
占位符缺失时原样返回模板，避免因为一个字段名写错就整条文案报错。
"""

from __future__ import annotations

import json
from typing import Any

from app import paths

#: 找不到配置或配置非法时使用的语言。
DEFAULT_LANGUAGE = "zh"

#: 目前提供语言包的语言。
SUPPORTED_LANGUAGES: tuple[str, ...] = ("zh", "en")

#: 语言代码在界面上的显示名，用各自的语言书写。
LANGUAGE_NAMES: dict[str, str] = {"zh": "中文", "en": "English"}

_catalog: dict[str, str] = {}
_fallback: dict[str, str] = {}
_language = DEFAULT_LANGUAGE


def language() -> str:
    """返回当前语言代码。"""
    return _language


def normalize(value: Any) -> str:
    """把任意输入收敛成受支持的语言代码。"""
    text = str(value or "").strip().lower()
    return text if text in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def set_language(value: Any) -> str:
    """切换语言并重新加载语言包，返回最终生效的语言代码。"""
    global _language, _catalog, _fallback
    _language = normalize(value)
    _catalog = _load(_language)
    # 英文包缺键时回退到中文，保证界面上不会出现裸露的键名。
    _fallback = _catalog if _language == DEFAULT_LANGUAGE else _load(DEFAULT_LANGUAGE)
    return _language


def t(key: str, **kwargs: Any) -> str:
    """取一条文案，并用关键字参数填充占位符。"""
    template = _catalog.get(key) or _fallback.get(key) or key
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def strings() -> dict[str, str]:
    """返回当前语言的完整文案表，供网页前端使用。"""
    return dict(_catalog)


def help_html() -> str:
    """返回当前语言的使用帮助正文。"""
    target = paths.LOCALE_DIR / f"help.{_language}.html"
    if not target.exists():
        target = paths.LOCALE_DIR / f"help.{DEFAULT_LANGUAGE}.html"
    try:
        return target.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load(language_code: str) -> dict[str, str]:
    target = paths.LOCALE_DIR / f"{language_code}.json"
    try:
        with open(target, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}
