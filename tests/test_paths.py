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
        paths.LOCALE_DIR,
        paths.APP_CONFIG_PATH,
        paths.OPERATIONS_PATH,
        paths.WEB_DIR,
    ):
        assert path.is_absolute()


def test_relative_user_path_anchors_at_the_data_dir():
    resolved = paths.resolve_user_path(r"custom\clear_clipboard.py")
    assert resolved == (paths.DATA_DIR / r"custom\clear_clipboard.py").resolve()


def test_absolute_user_path_is_untouched():
    assert paths.resolve_user_path(r"D:\Tools\x.exe") == Path(r"D:\Tools\x.exe")


def test_quotes_and_empty_values():
    assert paths.resolve_user_path('"C:\\a\\b"') == Path(r"C:\a\b")
    assert paths.resolve_user_path("") == paths.PROGRAM_DIR


def test_split_paths():
    parts = paths.split_paths(r"C:\a|D:\b")
    assert [str(part) for part in parts] == [r"C:\a", r"D:\b"]
    assert paths.split_paths("") == []


def test_data_dir_pointer_round_trips(tmp_path, monkeypatch):
    """指针写在本地目录，读回来就是新数据目录。"""
    monkeypatch.delenv("SIXCOIN_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "LOCAL_DIR", tmp_path)
    monkeypatch.setattr(paths, "DATA_POINTER", tmp_path / "data-dir.txt")
    target = tmp_path / "custom-data"

    paths.write_data_dir(target)

    assert paths.read_data_dir() == target


def test_migration_moves_config_and_drops_locks(tmp_path, monkeypatch):
    """旧 config 搬进数据目录，旧锁文件直接丢掉。"""
    program = tmp_path / "program"
    (program / "config").mkdir(parents=True)
    (program / "config" / "app.json").write_text("{}", encoding="utf-8")
    (program / "config" / "stale.lock").write_text("", encoding="utf-8")
    data = tmp_path / "data"
    monkeypatch.setattr(paths, "PROGRAM_DIR", program)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(paths, "LOG_DIR", tmp_path / "logs")

    paths.migrate_legacy()

    assert (data / "app.json").is_file()
    assert not (data / "stale.lock").exists()
