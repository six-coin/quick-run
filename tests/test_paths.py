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


def test_normalize_appends_the_project_code(tmp_path):
    """选一个普通目录，落点自动补上项目代号。"""
    assert paths.normalize_data_dir(str(tmp_path)) == tmp_path / paths.PROJECT


def test_normalize_keeps_a_path_that_already_ends_with_the_code(tmp_path):
    target = tmp_path / paths.PROJECT
    assert paths.normalize_data_dir(str(target)) == target


def test_normalize_is_case_insensitive(tmp_path):
    """Windows 路径不分大小写，已经补过就别再补一层。"""
    target = tmp_path / paths.PROJECT.upper()
    assert paths.normalize_data_dir(str(target)) == target


def test_normalize_strips_quotes_and_trailing_separator(tmp_path):
    assert paths.normalize_data_dir(f'"{tmp_path}\\"') == tmp_path / paths.PROJECT


def test_normalize_empty_text_falls_back_to_default(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DATA_DIR_DEFAULT", tmp_path / "default" / paths.PROJECT)
    assert paths.normalize_data_dir("  ") == paths.DATA_DIR_DEFAULT


def test_request_data_dir_records_the_pending_target(tmp_path, monkeypatch):
    """更改只写待搬迁标记，指针等真正搬完才改。"""
    monkeypatch.delenv("SIXCOIN_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "LOCAL_DIR", tmp_path)
    monkeypatch.setattr(paths, "DATA_POINTER", tmp_path / "data-dir.txt")
    monkeypatch.setattr(paths, "DATA_PENDING", tmp_path / "data-dir.pending")
    monkeypatch.setattr(paths, "DATA_DIR_DEFAULT", tmp_path / "default" / paths.PROJECT)

    target = paths.request_data_dir(str(tmp_path / "new"))

    assert target == tmp_path / "new" / paths.PROJECT
    assert paths.pending_data_dir() == target
    assert paths.read_data_dir() == paths.DATA_DIR_DEFAULT


def test_requesting_the_current_dir_clears_the_pending_marker(tmp_path, monkeypatch):
    """改回来就当没改过，不留一条「下次重启」的假提示。"""
    monkeypatch.delenv("SIXCOIN_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "LOCAL_DIR", tmp_path)
    monkeypatch.setattr(paths, "DATA_POINTER", tmp_path / "data-dir.txt")
    monkeypatch.setattr(paths, "DATA_PENDING", tmp_path / "data-dir.pending")
    current = tmp_path / "current" / paths.PROJECT
    paths.write_data_dir(current)

    paths.request_data_dir(str(tmp_path / "new"))
    paths.request_data_dir(str(current))

    assert paths.pending_data_dir() is None


def test_reconcile_moves_files_and_drops_locks(tmp_path, monkeypatch):
    """启动时把旧目录的内容搬进新目录，指针跟着改，旧锁文件丢掉。"""
    monkeypatch.delenv("SIXCOIN_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "LOCAL_DIR", tmp_path / "local")
    monkeypatch.setattr(paths, "DATA_POINTER", tmp_path / "local" / "data-dir.txt")
    monkeypatch.setattr(paths, "DATA_PENDING", tmp_path / "local" / "data-dir.pending")
    monkeypatch.setattr(paths, "DATA_DIR_DEFAULT", tmp_path / "default" / paths.PROJECT)
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.json").write_text("{}", encoding="utf-8")
    (source / "stale.lock").write_text("", encoding="utf-8")
    paths.write_data_dir(source)

    target = tmp_path / "target" / paths.PROJECT
    paths.request_data_dir(str(target))
    paths._reconcile_data_dir()

    assert (target / "app.json").is_file()
    assert not (target / "stale.lock").exists()
    assert not source.exists()
    assert paths.read_data_dir() == target
    assert paths.pending_data_dir() is None


def test_reconcile_never_overwrites_existing_files(tmp_path, monkeypatch):
    """目标里已有同名文件时保留目标的那份，不静默覆盖。"""
    monkeypatch.delenv("SIXCOIN_DATA_DIR", raising=False)
    monkeypatch.setattr(paths, "LOCAL_DIR", tmp_path / "local")
    monkeypatch.setattr(paths, "DATA_POINTER", tmp_path / "local" / "data-dir.txt")
    monkeypatch.setattr(paths, "DATA_PENDING", tmp_path / "local" / "data-dir.pending")
    monkeypatch.setattr(paths, "DATA_DIR_DEFAULT", tmp_path / "default" / paths.PROJECT)
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.json").write_text("old", encoding="utf-8")
    paths.write_data_dir(source)
    target = tmp_path / "target" / paths.PROJECT
    target.mkdir(parents=True)
    (target / "app.json").write_text("new", encoding="utf-8")

    paths.request_data_dir(str(target))
    paths._reconcile_data_dir()

    assert (target / "app.json").read_text(encoding="utf-8") == "new"
