"""界面文案的本地化支持。

所有面向用户的文本都放在 ``app/locales`` 目录下的 JSON 文件里，**文件名就是
语言代码**（``zh-CN.json``、``en-US.json``）。程序启动时扫描这个目录，放进去
什么语言就支持什么语言，不需要改代码。

模板里可以用 ``{name}`` 这样的占位符，通过 ``t("键", name=值)`` 填充；
占位符缺失时原样返回模板，避免因为一个字段名写错就整条文案报错。

每种语言在文件里用 ``language.name`` 声明自己的显示名（用该语言自己的文字），
所以新增语言时不必改代码，也不会有语言名散落在程序里。
"""

from __future__ import annotations

import json
from typing import Any

from app import paths

#: 找不到配置或配置非法时使用的语言。
DEFAULT_LANGUAGE = "zh-CN"

#: 语言包里的语言自称。用它自己的文字书写，界面上直接展示这个值。
NAME_KEY = "language.name"

_catalog: dict[str, str] = {}
_fallback: dict[str, str] = {}
_language = DEFAULT_LANGUAGE
_loaded = False


def available_languages() -> tuple[str, ...]:
    """扫描语言目录，返回所有可用的语言代码。

    默认语言排在最前面，其余按字母序。
    """
    codes = sorted(path.stem for path in paths.LOCALE_DIR.glob("*.json"))
    if DEFAULT_LANGUAGE in codes:
        codes.remove(DEFAULT_LANGUAGE)
        codes.insert(0, DEFAULT_LANGUAGE)
    return tuple(codes)


def language_names() -> dict[str, str]:
    """语言代码到界面显示名的映射。

    显示名由每种语言在自己的语言包里用 ``language.name`` 声明（用该语言自己
    的文字书写），程序里不硬编码任何语言名。缺这个键时退回语言代码本身。
    """
    names: dict[str, str] = {}
    for code in available_languages():
        label = str(_load(code).get(NAME_KEY) or "").strip()
        names[code] = label or code
    return names


def language() -> str:
    """返回当前语言代码。"""
    return _language


def normalize(value: Any) -> str:
    """把任意输入收敛成受支持的语言代码。"""
    text = str(value or "").strip()
    for code in available_languages():
        if code.lower() == text.lower():
            return code
    return DEFAULT_LANGUAGE


def set_language(value: Any) -> str:
    """切换语言并重新加载语言包，返回最终生效的语言代码。"""
    global _language, _catalog, _fallback, _loaded
    _language = normalize(value)
    _catalog = _load(_language)
    # 其他语言缺键时回退到默认语言，保证界面上不会出现裸露的键名。
    _fallback = _catalog if _language == DEFAULT_LANGUAGE else _load(DEFAULT_LANGUAGE)
    _loaded = True
    return _language


def t(key: str, **kwargs: Any) -> str:
    """取一条文案，并用关键字参数填充占位符。"""
    global _loaded
    # 还没人调用过 set_language 时先按默认语言加载一次，
    # 否则首次生成配置会把键名当成文案写进文件。
    if not _loaded:
        set_language(_language)
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


def list_separator() -> str:
    """列举多个项目时用的分隔符。"""
    return "、" if _language.lower().startswith("zh") else ", "


def _load(language_code: str) -> dict[str, str]:
    target = paths.LOCALE_DIR / f"{language_code}.json"
    try:
        with open(target, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}
