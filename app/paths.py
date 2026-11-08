"""项目里所有路径的唯一来源。

这里的路径全部是绝对路径，并且都由本文件的位置推导出来。
项目内任何模块都不允许依赖进程的当前工作目录，也不允许调用 ``os.chdir``；
需要指定子进程工作目录时，请看 ``app/system/shell.py`` 里那套安全的启动函数。
"""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = PACKAGE_DIR.parent

CONFIG_DIR = PROGRAM_DIR / "config"
LOG_DIR = PROGRAM_DIR / "logs"
LOCALE_DIR = PACKAGE_DIR / "locales"

#: 应用级配置：语言、外观、导航上限、外部服务密钥。
APP_CONFIG_PATH = CONFIG_DIR / "app.json"

#: 操作列表：根层就是分组数组。
OPERATIONS_PATH = CONFIG_DIR / "operations.json"

ENTRY_MAIN = PROGRAM_DIR / "main.pyw"
ENTRY_MANAGER = PROGRAM_DIR / "manager.pyw"

WEB_DIR = PACKAGE_DIR / "manager" / "web"


def resolve_user_path(raw: str) -> Path:
    """把配置里写下的路径解析成绝对路径。

    相对路径（例如 ``custom\\foo.py``）以程序目录为基准，而不是进程的当前
    工作目录。这样无论从哪个目录启动程序，配置里写的路径都指向同一个位置。
    """
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1]
    if not text:
        return PROGRAM_DIR
    path = Path(text)
    if path.is_absolute():
        return path
    return (PROGRAM_DIR / path).resolve()


def split_paths(raw: str) -> list[Path]:
    """把配置里用 ``|`` 分隔的路径串拆成绝对路径列表。"""
    return [resolve_user_path(part) for part in (raw or "").split("|") if part.strip()]
