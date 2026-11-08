"""用静态检查守住架构约定。

跑起来很便宜，但能挡住最伤人的几类退化：冒出来的 ``os.chdir``、界面依赖渗进
核心层、以及任何无法解析的文件。
"""

from __future__ import annotations

import ast
from pathlib import Path

from app import paths

APP_DIR = paths.PACKAGE_DIR


def _sources(directory: Path):
    for path in directory.rglob("*.py"):
        yield path, path.read_text(encoding="utf-8")


def _parse(path: Path, text: str) -> ast.Module:
    return ast.parse(text, filename=str(path))


def _imported_modules(tree: ast.Module) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _violates(modules: set[str], forbidden: tuple[str, ...]) -> list[str]:
    hits = []
    for module in modules:
        root = module.split(".")[0]
        for name in forbidden:
            if module == name or module.startswith(name + ".") or root == name:
                hits.append(module)
                break
    return hits


def _calls_chdir(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Attribute) and function.attr == "chdir":
            return True
        if isinstance(function, ast.Name) and function.id == "chdir":
            return True
    return False


def test_all_modules_parse():
    broken = []
    for path, text in _sources(APP_DIR):
        try:
            _parse(path, text)
        except SyntaxError as error:
            broken.append(f"{path.name}: {error}")
    assert broken == []


def test_no_chdir_anywhere():
    offenders = [
        path.name
        for path, text in _sources(APP_DIR)
        if _calls_chdir(_parse(path, text))
    ]
    assert offenders == []


def test_core_has_no_ui_imports():
    forbidden = ("PySide6", "PyQt5", "PyQt6", "webview", "app.launcher", "app.manager")
    offenders = []
    for path, text in _sources(APP_DIR / "core"):
        for module in _violates(_imported_modules(_parse(path, text)), forbidden):
            offenders.append(f"{path.name}: {module}")
    assert offenders == []


def test_system_layer_has_no_ui_imports():
    forbidden = ("PySide6", "PyQt5", "PyQt6", "webview")
    offenders = []
    for path, text in _sources(APP_DIR / "system"):
        for module in _violates(_imported_modules(_parse(path, text)), forbidden):
            offenders.append(f"{path.name}: {module}")
    assert offenders == []


def test_entry_points_are_thin():
    for name in ("main.pyw", "manager.pyw"):
        text = (paths.PROGRAM_DIR / name).read_text(encoding="utf-8")
        assert len(text.splitlines()) < 30
