import os
from typing import Optional

from pypinyin import Style, lazy_pinyin

_MAX_DIR_ITEMS = 100
_MAX_EXPLORE_DEPTH = 5


def _norm(text):
    result = []
    for ch in text.lower():
        if 'a' <= ch <= 'z' or '0' <= ch <= '9':
            result.append(ch)
    return "".join(result)


def _to_pinyin(name: str) -> str:
    result = []
    buf = ""
    for ch in name:
        if '\u4e00' <= ch <= '\u9fff':
            if buf:
                result.append(_norm(buf))
                buf = ""
            py = lazy_pinyin(ch, style=Style.NORMAL)
            if py:
                result.append(py[0])
        elif ch.isspace():
            if buf:
                result.append(_norm(buf))
                buf = ""
        else:
            buf += ch
    if buf:
        result.append(_norm(buf))
    return "".join(result)


class DirEntry:
    __slots__ = ("name", "full_path", "is_dir", "children", "pinyin", "_too_many")

    def __init__(self, name: str, full_path: str, is_dir: bool):
        self.name = name
        self.full_path = full_path
        self.is_dir = is_dir
        self.children: list[DirEntry] = []
        self.pinyin = _to_pinyin(name)
        self._too_many = False


def _scan_dir(path: str, current_depth: int, max_depth: int) -> DirEntry:
    name = os.path.basename(path) or path
    root = DirEntry(name, path, True)

    if current_depth > max_depth:
        return root

    try:
        entries = os.listdir(path)
    except (PermissionError, OSError):
        return root

    visible_count = 0
    for entry_name in entries:
        if not entry_name.startswith("."):
            visible_count += 1
    if visible_count > _MAX_DIR_ITEMS:
        root._too_many = True
        return root

    dirs = []
    files = []
    for entry_name in entries:
        if entry_name.startswith("."):
            continue
        full = os.path.join(path, entry_name)
        try:
            is_dir = os.path.isdir(full)
        except OSError:
            continue
        if is_dir:
            dirs.append((entry_name, full))
        else:
            files.append((entry_name, full))

    dirs.sort(key=lambda x: x[0].lower())
    files.sort(key=lambda x: x[0].lower())

    for dname, dpath in dirs:
        if current_depth >= max_depth:
            child = DirEntry(dname, dpath, True)
            root.children.append(child)
            continue
        try:
            sub_entries = os.listdir(dpath)
        except (PermissionError, OSError):
            child = DirEntry(dname, dpath, True)
            root.children.append(child)
            continue
        visible = [e for e in sub_entries if not e.startswith(".")]
        if len(visible) > _MAX_DIR_ITEMS:
            child = DirEntry(dname, dpath, True)
            child._too_many = True
            root.children.append(child)
            continue
        child = _scan_dir(dpath, current_depth + 1, max_depth)
        child.name = dname
        child.full_path = dpath
        root.children.append(child)

    for fname, fpath in files:
        root.children.append(DirEntry(fname, fpath, False))

    return root


def scan_root(root_path: str, explore_depth: int) -> Optional[DirEntry]:
    depth = max(0, min(explore_depth + 1, _MAX_EXPLORE_DEPTH))
    try:
        return _scan_dir(root_path, 0, depth)
    except Exception:
        return None


def _match_pos(entry: DirEntry, lower: str) -> int:
    pos = entry.name.lower().find(lower)
    if pos >= 0:
        return pos
    return entry.pinyin.find(lower)


def filter_entries(entries: list[DirEntry], filter_text: str) -> list[DirEntry]:
    if not filter_text:
        return list(entries)
    lower = _norm(filter_text)
    result = []
    for e in entries:
        if lower in e.name.lower() or lower in e.pinyin:
            result.append(e)
    result.sort(key=lambda e: _match_pos(e, lower))
    return result


def _parse_token(token: str) -> tuple[str, Optional[int]]:
    if "#" not in token:
        return token, None
    parts = token.split("#", 1)
    filter_text = parts[0]
    if not parts[1]:
        return filter_text, None
    try:
        num = int(parts[1])
        if num < 1:
            return filter_text, -1
        return filter_text, num
    except ValueError:
        return filter_text, -1


def _tokenize_nav(nav_text: str) -> list[tuple[str, int]]:
    levels = []
    i = 0
    n = len(nav_text)
    while i < n and nav_text[i] == " ":
        i += 1
    while i < n:
        start = i
        while i < n and nav_text[i] != " ":
            i += 1
        token = nav_text[start:i]
        spaces = 0
        while i < n and nav_text[i] == " ":
            i += 1
            spaces += 1
        levels.append((token, spaces))
    return levels


class ExploreResult:
    __slots__ = ("entries", "error")

    def __init__(self, entries=None, error=None):
        self.entries: list[DirEntry] = entries or []
        self.error: Optional[str] = error


def _list_children(node: DirEntry) -> ExploreResult:
    if node._too_many:
        return ExploreResult(error="该文件夹内项目过多")
    if not node.children:
        return ExploreResult(error="文件夹中没有任何项目")
    return ExploreResult(entries=list(node.children))


def navigate(root: DirEntry, nav_text: str, explore_depth: int) -> ExploreResult:
    levels = _tokenize_nav(nav_text)

    if not levels:
        return _list_children(root)

    current = root
    nav_depth = 0

    for i, (token, spaces) in enumerate(levels):
        is_last = (i == len(levels) - 1)
        filter_text, number = _parse_token(token)

        if number == -1:
            return ExploreResult(error="未知序号")

        if current._too_many:
            return ExploreResult(error="该文件夹内项目过多")

        matches = filter_entries(current.children, filter_text)
        if not matches:
            return ExploreResult(error="没有搜索到指定的项目")

        if number is not None:
            index = number
        elif spaces > 0:
            index = spaces
        else:
            index = None

        if is_last and spaces == 0 and index is None:
            return ExploreResult(entries=matches)

        if index is None:
            index = 1

        if index > len(matches):
            return ExploreResult(error="未知序号")
        item = matches[index - 1]

        if is_last and spaces == 0:
            return ExploreResult(entries=[item])

        if not item.is_dir:
            return ExploreResult(error="没有指定的文件夹")

        if nav_depth >= explore_depth:
            return ExploreResult(error="搜索已达深度上限")

        current = item
        nav_depth += 1

        if is_last and spaces > 0:
            return _list_children(current)

    return ExploreResult(error="文件夹中没有任何项目")
