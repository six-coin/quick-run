"""cwd-safe launching of files, folders, URLs and commands.

This module exists because of a real bug in the previous version:

    os.chdir(file_cwd)          # process wide, executed from a worker thread
    os.startfile(file_path)     # asynchronous, child inherits the cwd
    os.chdir(original_cwd)

While the cwd was switched, any other thread writing a relative log path
created a ``logs/`` folder next to the opened file, and two concurrent opens
could leave the cwd permanently wrong.

The rule here is simple: **never call os.chdir**. The child's working directory
is expressed as a parameter (``cwd=`` / ``os.startfile(..., cwd=...)``), so this
process' own cwd is never touched.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from loguru import logger

from app import paths

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010


class WindowsOpener:
    """Concrete :class:`app.core.actions.Opener` implementation."""

    def open_file(self, path: Path, *, cwd: Path, no_window: bool = False) -> None:
        target = Path(path)
        if not target.is_file():
            logger.warning("打开文件 {} 时出错：文件不存在或不是文件", target)
            return
        try:
            if no_window:
                # shell=True keeps the old behaviour for .py/.bat targets: the
                # shell resolves the file association. cwd is passed explicitly
                # instead of calling os.chdir first.
                subprocess.Popen(
                    [str(target)],
                    shell=True,
                    cwd=str(cwd),
                    close_fds=True,
                    creationflags=CREATE_NO_WINDOW,
                )
            else:
                self._startfile(target, cwd)
        except OSError as error:
            logger.warning("打开文件 {} 时出错：{}", target, error)

    def open_dir(self, path: Path) -> None:
        target = Path(path)
        if not target.is_dir():
            logger.warning("打开路径 {} 时出错：路径不存在或不是路径", target)
            return
        try:
            os.startfile(str(target))  # noqa: S606 - shell open is the intent
        except OSError as error:
            logger.warning("打开路径 {} 时出错：{}", target, error)

    def open_url(self, url: str) -> None:
        if not url:
            return
        try:
            webbrowser.open(url)
        except Exception as error:
            logger.warning("打开网页 {} 时出错：{}", url, error)

    def run_command(self, command: str, *, cwd: Path) -> None:
        if not command.strip():
            return
        try:
            subprocess.Popen(
                command,
                shell=True,
                cwd=str(cwd),
                creationflags=CREATE_NEW_CONSOLE,
            )
        except OSError as error:
            logger.warning("执行命令 {} 时出错：{}", command, error)

    def debug(self, function: str) -> None:
        if function == "restart":
            self._restart()
        elif function == "close":
            logger.info("操作成功执行：关闭程序")
            os._exit(0)
        else:
            logger.warning("未知的调试功能：{}", function)

    # -- internals --------------------------------------------------------
    @staticmethod
    def _startfile(target: Path, cwd: Path) -> None:
        try:
            os.startfile(str(target), cwd=str(cwd))
        except TypeError:
            # Python < 3.10 has no ``cwd`` argument; the shell resolves relative
            # paths against our own cwd, which is the program directory anyway.
            os.startfile(str(target))

    def _restart(self) -> None:
        interpreter = self._pythonw()
        try:
            subprocess.Popen(
                [str(interpreter), str(paths.ENTRY_MAIN)],
                cwd=str(paths.PROGRAM_DIR),
                close_fds=True,
            )
            logger.info("操作成功执行：重启程序")
        except OSError as error:
            logger.warning("重启程序失败：{}", error)
            return
        os._exit(0)

    @staticmethod
    def _pythonw() -> Path:
        executable = Path(sys.executable)
        candidate = executable.with_name("pythonw.exe")
        return candidate if candidate.exists() else executable
