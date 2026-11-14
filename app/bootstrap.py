"""启动期的公共步骤。

两个入口（``main.pyw`` 启动器、``manager.pyw`` 管理器）在做任何事之前调用
:func:`prepare`：建目录，并把数据目录搬迁时留下的警告交给日志。

「第一次运行」的判据是数据目录里有没有 ``app.json``。先启动启动器时，由
:func:`launch_manager` 把管理器拉起来并带上来源标记；管理器完成语言选择后
会解释一句「你打开的不是这个程序」。
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

from app import i18n, paths

_MB_ICONINFORMATION = 0x00000040
_MB_SETFOREGROUND = 0x00010000


def prepare() -> list[str]:
    """建目录，返回需要写进日志的警告。"""
    warnings: list[str] = list(paths.MIGRATION_WARNINGS)
    if paths.MIGRATED_ITEMS:
        warnings.append(f"数据目录已迁移 {paths.MIGRATED_ITEMS} 项到 {paths.DATA_DIR}")
    # custom/ 是「数据目录」这个基准的落点，先建好，用户填相对路径时才有地方放。
    folders = (paths.DATA_DIR, paths.CUSTOM_DIR, paths.LOCAL_DIR, paths.LOG_DIR, paths.LOCK_DIR)
    for folder in folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            warnings.append(f"无法创建 {folder}：{error}")
    return warnings


def is_first_run() -> bool:
    """数据目录里还没有应用配置，就是第一次运行。"""
    return not paths.APP_CONFIG_PATH.exists()


def pythonw() -> Path:
    return paths.PYTHONW if paths.PYTHONW.is_file() else Path(sys.executable)


def launch_manager(origin: str) -> bool:
    """首次运行时把管理器拉起来。``origin`` 是刚才被启动的入口名。"""
    try:
        subprocess.Popen(
            [str(pythonw()), str(paths.ENTRY_MANAGER), "--redirected-from", origin],
            cwd=str(paths.PROGRAM_DIR),
            close_fds=True,
        )
        return True
    except OSError:
        return False


def redirected_from() -> str:
    """解析 ``--redirected-from <入口名>``。没有这个参数就是正常启动。"""
    argv = sys.argv[1:]
    for index, item in enumerate(argv):
        if item == "--redirected-from" and index + 1 < len(argv):
            return argv[index + 1]
    return ""


def sync_language() -> None:
    """多开提示与崩溃弹窗要按用户选过的语言说话；读不到配置就用系统语言。

    这里直接读文件，不走 ``settings.load_app_config()``：那条路径会顺手写一份
    默认配置，把「第一次运行」标记冲掉。
    """
    i18n.set_language(current_language())


def current_language() -> str:
    """配置文件里记下的界面语言；没有或读不出来时按系统语言判定。"""
    try:
        raw = json.loads(paths.APP_CONFIG_PATH.read_text(encoding="utf-8"))
        language = raw["language"]
    except (OSError, ValueError, KeyError, TypeError):
        return i18n.initial_language()
    return language if isinstance(language, str) and language else i18n.initial_language()


def info(message: str, title: str = "") -> None:
    """提示框（信息图标）。多开、需要用户知道但不致命的事情用它。"""
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.MessageBoxW(
            None, str(message), title or "Quick Run", _MB_ICONINFORMATION | _MB_SETFOREGROUND
        )
    except Exception:  # 弹窗失败时没有别的出口
        pass


def guard(main, name: str) -> None:
    """入口的最后一道防线：任何未捕获异常都变成「错误 + 时间 + 日志路径」弹窗。"""
    try:
        main()
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - 这里就是要兜住一切
        try:
            from app import logging_setup

            logging_setup.setup(name)
            # 弹窗要说用户选的语言：这里可能发生在读配置之前，先同步一次。
            sync_language()
            logging_setup.fatal(
                i18n.t("fatal.unexpected", error=f"{type(error).__name__}: {error}")
            )
        except Exception:  # 连日志都起不来时只能静默退出
            os._exit(1)
