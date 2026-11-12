"""安全地启动文件、文件夹、网址和命令，全程不碰 cwd。

这里的规矩很简单：**绝不调用 os.chdir**。子进程的工作目录一律用参数表达
（``cwd=`` / ``os.startfile(..., cwd=...)``），进程自己的 cwd 从头到尾不动。

这样做有两个直接好处：任何线程写日志、写配置都落在固定的绝对路径上，不会
跟着被打开的文件跑；并发启动多个目标时也不会互相干扰。
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

from loguru import logger

from app import paths

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010

#: ``AllowSetForegroundWindow`` 的「任意进程」参数
ASFW_ANY = -1


def allow_foreground() -> None:
    """把「谁可以抢到前台」的权利让出去。

    窗口一收起，启动器就不再是前台进程；按 Windows 的规则，这时它拉起来的
    程序没有资格调用 ``SetForegroundWindow``，窗口会开在别的窗口后面。所以
    在收起之前先放弃这份权利，目标程序才能正常出现在最前面。

    调用方不是前台进程时这个调用会直接失败，那正是它该失败的时候。
    """
    try:
        ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)
    except Exception as error:  # 非 Windows 平台没有 windll，静默降级
        logger.warning("让出前台权限时出错：{}", error)


class WindowsOpener:
    """:class:`app.core.actions.Opener` 的 Windows 实现。"""

    def open_file(self, path: Path, *, cwd: Path, no_window: bool = False) -> None:
        target = Path(path)
        if not target.is_file():
            logger.warning("打开文件 {} 时出错：文件不存在或不是文件", target)
            return
        try:
            if no_window:
                # shell=True 让 shell 去解析 .py/.bat 的文件关联。
                # 工作目录用参数传，而不是先 os.chdir 再启动。
                subprocess.Popen(
                    [str(target)],
                    shell=True,
                    cwd=str(cwd),
                    close_fds=True,
                    creationflags=CREATE_NO_WINDOW,
                )
            else:
                os.startfile(str(target), cwd=str(cwd))
        except OSError as error:
            logger.warning("打开文件 {} 时出错：{}", target, error)

    def open_dir(self, path: Path) -> None:
        target = Path(path)
        if not target.is_dir():
            logger.warning("打开路径 {} 时出错：路径不存在或不是路径", target)
            return
        try:
            os.startfile(str(target))  # 这里就是要交给 shell 打开
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
