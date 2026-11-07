from __future__ import annotations

from pathlib import Path

from app import paths


def test_program_dir_is_absolute():
    assert paths.PROGRAM_DIR.is_absolute()
    assert (paths.PROGRAM_DIR / "main.pyw").exists()
    assert (paths.PROGRAM_DIR / "manager.pyw").exists()


def test_config_paths_are_absolute():
    for path in (
        paths.CONFIG_DIR,
        paths.LOG_DIR,
        paths.OPERATIONS_PATH,
        paths.TRANSLATE_PATH,
        paths.AI_PATH,
        paths.WEB_DIR,
    ):
        assert path.is_absolute()


def test_relative_user_path_anchors_at_program_dir():
    resolved = paths.resolve_user_path(r"custom\clear_clipboard.py")
    assert resolved == (paths.PROGRAM_DIR / r"custom\clear_clipboard.py").resolve()


def test_absolute_user_path_is_untouched():
    assert paths.resolve_user_path(r"D:\Tools\x.exe") == Path(r"D:\Tools\x.exe")


def test_quotes_and_empty_values():
    assert paths.resolve_user_path('"C:\\a\\b"') == Path(r"C:\a\b")
    assert paths.resolve_user_path("") == paths.PROGRAM_DIR


def test_split_paths():
    parts = paths.split_paths(r"C:\a|D:\b")
    assert [str(part) for part in parts] == [r"C:\a", r"D:\b"]
    assert paths.split_paths("") == []
