"""安全地启动文件、文件夹、网址和命令，全程不碰 cwd。

这个模块的存在是为修掉旧版本的一个真实缺陷：

    os.chdir(file_cwd)          # 改的是整个进程，还跑在线程池里
    os.startfile(file_path)     # 异步，子进程继承当前 cwd
    os.chdir(original_cwd)

cwd 被切走的那段时间里，任何别的线程写相对路径日志，都会在被打开的文件旁边
建出一个 ``logs/`` 文件夹；两次并发打开还可能把 cwd 永久留在错误的位置。

这里的规矩很简单：**绝不调用 os.chdir**。子进程的工作目录一律用参数表达
（``cwd=`` / ``os.startfile(..., cwd=...)``），进程自己的 cwd 从头到尾不动。
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
    """:class:`app.core.actions.Opener` 的 Windows 实现。"""

    def open_file(self, path: Path, *, cwd: Path, no_window: bool = False) -> None:
        target = Path(path)
        if not target.is_file():
            logger.warning("打开文件 {} 时出错：文件不存在或不是文件", target)
            return
        try:
            if no_window:
                # shell=True 保留旧行为：让 shell 去解析 .py/.bat 的文件关联。
                # 工作目录用参数传，而不是先 os.chdir 再启动。
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
            os.startfile(str(target))  # noqa: S606 - 这里就是要交给 shell 打开
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

    # -- 内部实现 ---------------------------------------------------------
    @staticmethod
    def _startfile(target: Path, cwd: Path) -> None:
        try:
            os.startfile(str(target), cwd=str(cwd))
        except TypeError:
            # Python 3.10 以前的 startfile 没有 ``cwd`` 参数；反正本进程的 cwd
            # 就是程序目录，相对路径也能解析对。
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
