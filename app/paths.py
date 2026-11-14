"""项目里所有路径的唯一来源。

这里的路径全部是绝对路径，并且都由本文件的位置或系统环境变量推导出来。
项目内任何模块都不允许依赖进程的当前工作目录，也不允许调用 ``os.chdir``；
需要指定子进程工作目录时，请看 ``app/system/shell.py`` 里那套安全的启动函数。

四类位置：

| 位置 | 内容 | 默认 |
|---|---|---|
| 程序目录 | 代码与随程序分发的资源 | 仓库根目录 |
| 数据目录 | 应用配置、操作列表、自定义脚本 | ``%PROGRAMDATA%\\six-coin\\quick-run`` |
| 本地目录 | 日志、锁、数据目录指针 | ``%LOCALAPPDATA%\\six-coin\\quick-run`` |
| 临时目录 | 可随时丢弃的中间文件 | ``%TEMP%\\six-coin\\quick-run`` |

数据目录可在设置里改，指针写在本地目录；改完重启才生效。
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

VENDOR = "six-coin"
PROJECT = "quick-run"

PACKAGE_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = PACKAGE_DIR.parent

_ENV_DATA = "SIXCOIN_DATA_DIR"
_ENV_LOCAL = "SIXCOIN_LOCAL_DIR"
_ENV_TEMP = "SIXCOIN_TEMP_DIR"


def _system_dir(variable: str, fallback: str) -> Path:
    raw = os.environ.get(variable, "").strip()
    return Path(raw) if raw else Path(fallback)


LOCAL_DIR = Path(
    os.environ.get(_ENV_LOCAL, "").strip()
    or _system_dir("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")) / VENDOR / PROJECT
)
TEMP_DIR = Path(
    os.environ.get(_ENV_TEMP, "").strip() or Path(tempfile.gettempdir()) / VENDOR / PROJECT
)
DATA_DIR_DEFAULT = _system_dir("PROGRAMDATA", "C:/ProgramData") / VENDOR / PROJECT

LOG_DIR = LOCAL_DIR / "logs"
LOCK_DIR = LOCAL_DIR / "locks"
DATA_POINTER = LOCAL_DIR / "data-dir.txt"


def read_data_dir() -> Path:
    """读数据目录指针；没设过、读不出来、不是绝对路径都回退默认值。"""
    override = os.environ.get(_ENV_DATA, "").strip()
    if override:
        return Path(override)
    try:
        text = DATA_POINTER.read_text(encoding="utf-8").strip()
    except OSError:
        return DATA_DIR_DEFAULT
    if not text:
        return DATA_DIR_DEFAULT
    path = Path(text)
    return path if path.is_absolute() else DATA_DIR_DEFAULT


DATA_DIR = read_data_dir()

#: 旧名字保留：配置现在在数据目录里。
CONFIG_DIR = DATA_DIR
#: 用户自定义脚本与图标；操作列表里写 ``custom\\...`` 相对路径。
CUSTOM_DIR = DATA_DIR / "custom"

LOCALE_DIR = PACKAGE_DIR / "locales"

#: 应用级配置：语言、外观、导航上限、外部服务密钥。
APP_CONFIG_PATH = DATA_DIR / "app.json"

#: 操作列表：根层就是分组数组。
OPERATIONS_PATH = DATA_DIR / "operations.json"

ENTRY_MAIN = PROGRAM_DIR / "main.pyw"
ENTRY_MANAGER = PROGRAM_DIR / "manager.pyw"
PYTHONW = PROGRAM_DIR / ".venv" / "Scripts" / "pythonw.exe"

WEB_DIR = PACKAGE_DIR / "manager" / "web"


def write_data_dir(path: Path) -> None:
    """把新的数据目录写进指针文件。下次启动才生效。"""
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    temp = DATA_POINTER.with_suffix(".tmp")
    temp.write_text(str(path), encoding="utf-8", newline="\n")
    os.replace(temp, DATA_POINTER)


def resolve_user_path(raw: str) -> Path:
    """把配置里写下的路径解析成绝对路径。

    相对路径（例如 ``custom\\foo.py``）以数据目录为基准，而不是进程的当前
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
    return (DATA_DIR / path).resolve()


def split_paths(raw: str) -> list[Path]:
    """把配置里用 ``|`` 分隔的路径串拆成绝对路径列表。"""
    return [resolve_user_path(part) for part in (raw or "").split("|") if part.strip()]


def migrate_legacy() -> list[str]:
    """把旧版本留在程序目录里的数据搬到新位置。

    只在目标位置还没有同名项时搬，绝不覆盖；搬完删掉空目录。
    """
    warnings: list[str] = []
    for source, target in (
        (PROGRAM_DIR / "config", DATA_DIR),
        (PROGRAM_DIR / "custom", CUSTOM_DIR),
        (PROGRAM_DIR / "logs", LOG_DIR),
    ):
        warnings.extend(_merge_move(source, target))
    return warnings


def _merge_move(source: Path, target: Path) -> list[str]:
    if not source.is_dir():
        return []
    warnings: list[str] = []
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return [f"无法创建 {target}：{error}"]
    for item in list(source.iterdir()):
        if item.suffix == ".lock":
            # 旧锁文件没有迁移价值，留着还会让人以为锁在数据目录里。
            try:
                item.unlink()
            except OSError:
                pass
            continue
        destination = target / item.name
        if destination.exists():
            continue
        try:
            shutil.move(str(item), str(destination))
        except OSError as error:
            warnings.append(f"迁移 {item} 失败：{error}")
    try:
        source.rmdir()
    except OSError:
        pass
    return warnings
