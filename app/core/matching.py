r"""搜索和目录浏览共用的字符串归一化与拼音工具。

规则完全沿用旧实现：

* 关键词用 ``startswith`` 做前缀匹配，绝不用 ``in``；
* 文件夹操作的关键词和查询都会先压成 ``[a-z0-9]``，所以 ``play`` 既能匹配
  ``Play|wan`` 也能匹配 ``e:\play``；
* 中文名字会额外生成一份拼音，所以 ``biji`` 能找到 ``笔记``。
"""

from __future__ import annotations

from pypinyin import Style, lazy_pinyin

_CJK_START = "\u4e00"
_CJK_END = "\u9fff"


def normalize_alnum(text: str) -> str:
    """转小写并只保留 ``a-z0-9``。"""
    return "".join(ch for ch in text.lower() if ("a" <= ch <= "z" or "0" <= ch <= "9"))


def to_pinyin(name: str) -> str:
    """生成可搜索的拼音串，英文和数字片段原样保留。"""
    parts: list[str] = []
    buffer = ""
    for char in name:
        if _CJK_START <= char <= _CJK_END:
            if buffer:
                parts.append(normalize_alnum(buffer))
                buffer = ""
            syllables = lazy_pinyin(char, style=Style.NORMAL)
            if syllables:
                parts.append(syllables[0])
        elif char.isspace():
            if buffer:
                parts.append(normalize_alnum(buffer))
                buffer = ""
        else:
            buffer += char
    if buffer:
        parts.append(normalize_alnum(buffer))
    return "".join(parts)


def starts_with_any(keywords: list[str], query: str) -> bool:
    return any(keyword.startswith(query) for keyword in keywords)


def match_position(name: str, pinyin: str, query: str) -> int:
    """名字里第一次命中的位置，名字里没有就退回拼音。

    用于给目录浏览的结果排序；``-1`` 表示“只在拼音里命中，位置未知”，
    会排在直接命中名字的条目后面。
    """
    position = name.lower().find(query)
    if position >= 0:
        return position
    return pinyin.find(query)
