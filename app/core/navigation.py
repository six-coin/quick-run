"""``关键词 + 空格`` 浏览模式用到的目录导航。

旧版本在启动时把所有配置目录整棵树扫一遍再缓存，``E:\\Play`` 这种深度 5 的
目录会让启动明显变慢，还得维护后台索引。现在每进入一层就列一次目录，结果和
错误文案完全一致，但启动零成本，也不会读到过期数据。

导航语法保持不变：

    keyword <空格> token <空格> token ...
    * 一个 token 选中第一个匹配项（先文件夹后文件）；
    * ``token#3`` 显式选择第 3 个匹配项；
    * ``token  ``（token 后两个空格）表示“进入这个文件夹并列出来”；
    * token 后面空格的个数决定选第几个匹配项。

``NavResult.error`` 里存的是文案键而不是成品文本，由上层负责翻译。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from app.core.matching import match_position, normalize_alnum, to_pinyin
from app.models import MAX_EXPLORE_DEPTH

#: 单个目录超过这么多条目就不再展开，避免卡住界面。
MAX_DIR_ITEMS = 100

ERR_TOO_MANY = "nav.too_many"
ERR_EMPTY = "nav.empty"
ERR_NO_MATCH = "nav.no_match"
ERR_BAD_INDEX = "nav.bad_index"
ERR_NOT_DIR = "nav.not_dir"
ERR_DEPTH_LIMIT = "nav.depth_limit"

Lister = Callable[[Path], Iterable[tuple[str, bool]]]


@dataclass(frozen=True)
class NavEntry:
    name: str
    path: Path
    is_dir: bool
    pinyin: str


@dataclass(frozen=True)
class NavResult:
    entries: tuple[NavEntry, ...] = ()
    error: str | None = None


def make_entry(name: str, path: Path, is_dir: bool) -> NavEntry:
    return NavEntry(name=name, path=path, is_dir=is_dir, pinyin=to_pinyin(name))


def list_directory(path: Path) -> list[tuple[str, bool]]:
    """默认的目录列举函数：返回所有非隐藏条目及其是否为文件夹。"""
    items: list[tuple[str, bool]] = []
    with os.scandir(path) as iterator:
        for entry in iterator:
            if entry.name.startswith("."):
                continue
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            items.append((entry.name, is_dir))
    return items


def filter_entries(entries: Iterable[NavEntry], filter_text: str) -> list[NavEntry]:
    """按名字或拼音匹配，再按命中位置排序。"""
    if not filter_text:
        return list(entries)
    needle = normalize_alnum(filter_text)
    if not needle:
        return list(entries)
    matches = [
        entry
        for entry in entries
        if needle in entry.name.lower() or needle in entry.pinyin
    ]
    matches.sort(key=lambda entry: match_position(entry.name, entry.pinyin, needle))
    return matches


def parse_token(token: str) -> tuple[str, int | None]:
    """拆分 ``名字#序号``；返回 ``-1`` 表示序号不可用。"""
    if "#" not in token:
        return token, None
    filter_text, _, raw_index = token.partition("#")
    if not raw_index:
        return filter_text, None
    try:
        number = int(raw_index)
    except ValueError:
        return filter_text, -1
    if number < 1:
        return filter_text, -1
    return filter_text, number


def tokenize_nav(nav_text: str) -> list[tuple[str, int]]:
    """按空格切分，并记录每个 token 后面跟了几个空格。"""
    levels: list[tuple[str, int]] = []
    index = 0
    length = len(nav_text)
    while index < length and nav_text[index] == " ":
        index += 1
    while index < length:
        start = index
        while index < length and nav_text[index] != " ":
            index += 1
        token = nav_text[start:index]
        spaces = 0
        while index < length and nav_text[index] == " ":
            index += 1
            spaces += 1
        levels.append((token, spaces))
    return levels


class DirectoryNavigator:
    """在真实文件系统上做无状态导航（列举函数可注入，方便测试）。"""

    def __init__(
        self,
        lister: Lister = list_directory,
        max_items: int = MAX_DIR_ITEMS,
        max_depth: int = MAX_EXPLORE_DEPTH,
    ) -> None:
        self._lister = lister
        self._max_items = max(1, int(max_items))
        self._max_depth = max(0, min(int(max_depth), MAX_EXPLORE_DEPTH))

    @property
    def max_depth(self) -> int:
        return self._max_depth

    @property
    def max_items(self) -> int:
        return self._max_items

    def can_explore(self, root: Path) -> bool:
        try:
            return root.is_dir()
        except OSError:
            return False

    def navigate(self, root: Path, nav_text: str, explore_depth: int) -> NavResult:
        # 单条操作的探索深度还要再受全局上限约束，两者取小。
        depth_limit = max(0, min(int(explore_depth), self._max_depth))
        levels = tokenize_nav(nav_text)
        if not levels:
            return self._list_children(root)

        current = root
        navigated = 0

        for position, (token, spaces) in enumerate(levels):
            is_last = position == len(levels) - 1
            filter_text, number = parse_token(token)

            if number == -1:
                return NavResult(error=ERR_BAD_INDEX)

            children, too_many = self._read(current)
            if too_many:
                return NavResult(error=ERR_TOO_MANY)

            matches = filter_entries(children, filter_text)
            if not matches:
                return NavResult(error=ERR_NO_MATCH)

            if number is not None:
                index = number
            elif spaces > 0:
                index = spaces
            else:
                index = None

            if is_last and spaces == 0 and index is None:
                return NavResult(entries=tuple(matches))

            if index is None:
                index = 1
            if index > len(matches):
                return NavResult(error=ERR_BAD_INDEX)

            item = matches[index - 1]

            if is_last and spaces == 0:
                return NavResult(entries=(item,))

            if not item.is_dir:
                return NavResult(error=ERR_NOT_DIR)
            if navigated >= depth_limit:
                return NavResult(error=ERR_DEPTH_LIMIT)

            current = item.path
            navigated += 1

            if is_last and spaces > 0:
                return self._list_children(current)

        return NavResult(error=ERR_EMPTY)

    # -- 内部实现 ---------------------------------------------------------
    def _list_children(self, path: Path) -> NavResult:
        entries, too_many = self._read(path)
        if too_many:
            return NavResult(error=ERR_TOO_MANY)
        if not entries:
            return NavResult(error=ERR_EMPTY)
        return NavResult(entries=tuple(entries))

    def _read(self, path: Path) -> tuple[list[NavEntry], bool]:
        try:
            raw = list(self._lister(path))
        except OSError:
            return [], False

        directories: list[NavEntry] = []
        files: list[NavEntry] = []
        for name, is_dir in raw:
            if name.startswith("."):
                continue
            entry = make_entry(name, path / name, is_dir)
            (directories if is_dir else files).append(entry)

        if len(directories) + len(files) > self._max_items:
            return [], True

        directories.sort(key=lambda entry: entry.name.lower())
        files.sort(key=lambda entry: entry.name.lower())
        return directories + files, False
