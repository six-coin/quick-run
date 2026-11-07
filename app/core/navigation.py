"""Directory navigation used by the ``keyword + space`` browsing mode.

The previous implementation pre-scanned every configured directory at startup
and cached a tree. That made startup slow (``E:\\Play`` at depth 5) and forced a
background index. This version lists one directory per navigation level on
demand, which produces identical results and error messages but costs nothing
at startup and never serves stale data.

The navigation grammar is unchanged:

    keyword <space> token <space> token ...
    * a token selects the first match (directories first, then files);
    * ``token#3`` picks the third match explicitly;
    * ``token  `` (two trailing spaces) means "enter that folder and list it";
    * the number of spaces after a token selects the nth match.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from app.core.matching import match_position, normalize_alnum, to_pinyin

MAX_DIR_ITEMS = 100
MAX_EXPLORE_DEPTH = 5

ERR_TOO_MANY = "该文件夹内项目过多"
ERR_EMPTY = "文件夹中没有任何项目"
ERR_NO_MATCH = "没有搜索到指定的项目"
ERR_BAD_INDEX = "未知序号"
ERR_NOT_DIR = "没有指定的文件夹"
ERR_DEPTH_LIMIT = "搜索已达深度上限"

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
    """Default lister: every non hidden entry with its directory flag."""
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
    """Match by name or pinyin, then rank by where the hit starts."""
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
    """Split ``name#index``; ``-1`` signals an unusable index."""
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
    """Split on spaces and record how many spaces followed each token."""
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
    """Stateless navigation over the real file system (lister is injectable)."""

    def __init__(self, lister: Lister = list_directory, max_items: int = MAX_DIR_ITEMS) -> None:
        self._lister = lister
        self._max_items = max_items

    def can_explore(self, root: Path) -> bool:
        try:
            return root.is_dir()
        except OSError:
            return False

    def navigate(self, root: Path, nav_text: str, explore_depth: int) -> NavResult:
        depth_limit = max(0, min(int(explore_depth), MAX_EXPLORE_DEPTH))
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

    # -- internals --------------------------------------------------------
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
