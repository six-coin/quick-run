"""工作目录不变的回归测试。

两条不变量：

1. 打开任何东西都不会改变 ``Path.cwd()``；
2. 目标目录以参数形式显式传给子进程。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app import paths
from app.core.actions import ActionExecutor, Modifiers
from app.core.rows import ResultRow, RowKind, RowStatus
from app.models import Operation
from app.system import shell


class FakeSpeech:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> bool:
        self.spoken.append(text)
        return True


class RecordingOpener:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def open_file(self, path, *, cwd, no_window: bool = False) -> None:
        self.calls.append(("file", Path(path), Path(cwd), no_window))

    def open_dir(self, path) -> None:
        self.calls.append(("dir", Path(path)))

    def open_url(self, url: str) -> None:
        self.calls.append(("url", url))

    def run_command(self, command: str, *, cwd) -> None:
        self.calls.append(("cmd", command, Path(cwd)))

    def debug(self, function: str) -> None:
        self.calls.append(("debug", function))


def make_row(operation: Operation) -> ResultRow:
    return ResultRow(key="row", kind=RowKind.EXTERNAL, text=operation.display, payload=operation)


def test_open_file_keeps_cwd(tmp_path, monkeypatch):
    target = tmp_path / "note.txt"
    target.write_text("x", encoding="utf-8")
    calls: list[tuple] = []

    def fake_startfile(path, operation="open", arguments="", cwd=None, show_cmd=None):
        calls.append((path, cwd))

    monkeypatch.setattr(os, "startfile", fake_startfile, raising=False)
    before = Path.cwd()

    shell.WindowsOpener().open_file(target, cwd=tmp_path)

    assert Path.cwd() == before
    assert calls == [(str(target), str(tmp_path))]


def test_open_file_no_window_passes_cwd(tmp_path, monkeypatch):
    target = tmp_path / "tool.exe"
    target.write_bytes(b"")
    recorded: dict = {}

    class FakePopen:
        def __init__(self, args, **kwargs):
            recorded["args"] = args
            recorded["kwargs"] = kwargs

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    before = Path.cwd()

    shell.WindowsOpener().open_file(target, cwd=tmp_path, no_window=True)

    assert Path.cwd() == before
    assert recorded["kwargs"]["cwd"] == str(tmp_path)
    assert recorded["kwargs"]["creationflags"] == shell.CREATE_NO_WINDOW


def test_open_dir_keeps_cwd(tmp_path, monkeypatch):
    def fake_startfile(path, operation="open", arguments="", cwd=None, show_cmd=None):
        return None

    monkeypatch.setattr(os, "startfile", fake_startfile, raising=False)
    before = Path.cwd()

    shell.WindowsOpener().open_dir(tmp_path)

    assert Path.cwd() == before


def test_modifier_opens_containing_folder(tmp_path):
    target = tmp_path / "note.txt"
    target.write_text("x", encoding="utf-8")
    opener = RecordingOpener()
    executor = ActionExecutor(opener, FakeSpeech())
    operation = Operation(
        display="Note",
        type="file",
        keywords="n",
        arguments={"path": str(target), "no_window": False},
    )

    executor.execute(make_row(operation), Modifiers(ctrl=True))

    assert opener.calls == [("dir", tmp_path)]


def test_missing_file_is_ignored(tmp_path):
    opener = RecordingOpener()
    executor = ActionExecutor(opener, FakeSpeech())
    operation = Operation(
        display="Ghost",
        type="file",
        keywords="g",
        arguments={"path": str(tmp_path / "nope.txt"), "no_window": False},
    )

    executor.execute(make_row(operation), Modifiers())

    assert opener.calls == []


def test_pipe_separated_paths_are_all_opened(tmp_path):
    first = tmp_path / "a.txt"
    second = tmp_path / "b.txt"
    first.write_text("x", encoding="utf-8")
    second.write_text("x", encoding="utf-8")
    opener = RecordingOpener()
    executor = ActionExecutor(opener, FakeSpeech())
    operation = Operation(
        display="Both",
        type="file",
        keywords="b",
        arguments={"path": f"{first}|{second}", "no_window": False},
    )

    executor.execute(make_row(operation), Modifiers())

    assert [call[1] for call in opener.calls] == [first, second]


def test_calculate_row_copies_only_when_done():
    executor = ActionExecutor(RecordingOpener(), FakeSpeech())

    done = ResultRow(
        key="1", kind=RowKind.CALCULATE, text="计算：3", status=RowStatus.DONE, value="3"
    )
    outcome = executor.execute(done)
    assert outcome.hide is True
    assert outcome.clipboard_text == "3"

    loading = ResultRow(
        key="2", kind=RowKind.CALCULATE, text="计算：计算中...", status=RowStatus.LOADING
    )
    outcome = executor.execute(loading)
    assert outcome.hide is False
    assert outcome.clipboard_text is None


def test_translate_with_modifier_speaks():
    speech = FakeSpeech()
    executor = ActionExecutor(RecordingOpener(), speech)
    row = ResultRow(key="t", kind=RowKind.TRANSLATE, text="翻译：hello", payload="hello")

    executor.execute(row, Modifiers(alt=True))

    assert speech.spoken == ["hello"]


def test_log_directory_is_absolute():
    assert paths.LOG_DIR.is_absolute()
    assert paths.LOG_DIR.name == "logs"
