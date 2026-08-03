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
    depth = max(0, min(explore_depth, _MAX_EXPLORE_DEPTH))
    try:
        return _scan_dir(root_path, 0, depth)
    except Exception:
        return None


def filter_entries(entries: list[DirEntry], filter_text: str) -> list[DirEntry]:
    if not filter_text:
        return list(entries)
    lower = _norm(filter_text)
    result = []
    for e in entries:
        if lower in e.name.lower() or lower in e.pinyin:
            result.append(e)
    return result


def _parse_token(token: str) -> tuple[str, Optional[int]]:
    if "#" not in token:
        return token, None
    parts = token.split("#", 1)
    filter_text = parts[0]
    try:
        num = int(parts[1])
        if num < 1:
            return filter_text, -1
        return filter_text, num
    except ValueError:
        return filter_text, -1


class ExploreResult:
    __slots__ = ("entries", "error")

    def __init__(self, entries=None, error=None):
        self.entries: list[DirEntry] = entries or []
        self.error: Optional[str] = error


def navigate(root: DirEntry, nav_text: str, explore_depth: int) -> ExploreResult:
    trailing_space = nav_text.endswith(" ")
    stripped = nav_text.strip()
    tokens = stripped.split(" ") if stripped else []

    if not tokens:
        if not root.children:
            return ExploreResult(error="文件夹中没有任何项目")
        return ExploreResult(entries=list(root.children))

    current = root
    nav_depth = 0

    for i, token in enumerate(tokens):
        is_last = (i == len(tokens) - 1)
        filter_text, number = _parse_token(token)

        if number == -1:
            return ExploreResult(error="未知序号")

        matches = filter_entries(current.children, filter_text)
        if not matches:
            return ExploreResult(error="没有搜索到指定的项目")

        if number is not None:
            if number > len(matches):
                return ExploreResult(error="未知序号")
            item = matches[number - 1]

            if is_last and not trailing_space:
                return ExploreResult(entries=[item])

            if not item.is_dir:
                return ExploreResult(error="没有指定的文件夹")

            if nav_depth >= explore_depth - 1:
                return ExploreResult(error="搜索已达深度上限")

            current = item
            nav_depth += 1

            if is_last and trailing_space:
                if not current.children:
                    return ExploreResult(error="文件夹中没有任何项目")
                return ExploreResult(entries=list(current.children))
        else:
            if is_last and not trailing_space:
                return ExploreResult(entries=matches)

            first = matches[0]
            if not first.is_dir:
                return ExploreResult(error="没有指定的文件夹")

            if nav_depth >= explore_depth - 1:
                return ExploreResult(error="搜索已达深度上限")

            current = first
            nav_depth += 1

            if is_last and trailing_space:
                if not current.children:
                    return ExploreResult(error="文件夹中没有任何项目")
                return ExploreResult(entries=list(current.children))

    return ExploreResult(error="文件夹中没有任何项目")
