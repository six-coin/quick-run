r"""String normalisation and pinyin helpers shared by search and navigation.

The rules are inherited verbatim from the previous implementation:

* keywords are matched with ``startswith`` (prefix), never ``in``;
* directory keywords and queries are reduced to ``[a-z0-9]`` before matching,
  which makes ``play`` match ``Play|wan`` and ``e:\play`` alike;
* Chinese names get a pinyin form so ``biji`` finds ``笔记``.
"""

from __future__ import annotations

from pypinyin import Style, lazy_pinyin

_CJK_START = "\u4e00"
_CJK_END = "\u9fff"


def normalize_alnum(text: str) -> str:
    """Lowercase and keep only ``a-z0-9``."""
    return "".join(ch for ch in text.lower() if ("a" <= ch <= "z" or "0" <= ch <= "9"))


def to_pinyin(name: str) -> str:
    """Build a searchable pinyin string, keeping latin segments in place."""
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
    """Position of the first hit in the name, falling back to pinyin.

    Used to rank navigation results; ``-1`` means "matched via pinyin only at
    an unknown offset", which sorts after direct name matches.
    """
    position = name.lower().find(query)
    if position >= 0:
        return position
    return pinyin.find(query)
