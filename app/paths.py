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

数据目录可在设置里改，落点恒以项目代号结尾；改完在下次启动时把旧目录的内容
搬过去，指针跟着改。
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

VENDOR = "six-coin"
PROJECT = "quick-run"


class PathBase:
    """操作里「路径基准」的取值，决定相对路径从哪里补全。

    绝对路径不受它影响：无论选哪一种，写全了的路径都直接用。
    """

    DATA = "data"
    PROGRAM = "program"
    ABSOLUTE = "absolute"


#: 下拉框里的显示顺序。
PATH_BASE_VALUES: tuple[str, ...] = (PathBase.DATA, PathBase.PROGRAM, PathBase.ABSOLUTE)

#: 没写这个参数时的默认基准。程序目录里放的是 .bat / 脚本，相对路径多半指它。
DEFAULT_PATH_BASE = PathBase.PROGRAM

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
#: 「更改数据目录」留下的待搬迁标记。指针只在搬完之后才改，中途断电也不会让
#: 程序在一个空目录里找数据。
DATA_PENDING = LOCAL_DIR / "data-dir.pending"


def normalize_data_dir(raw: str, base: Path | None = None) -> Path:
    """把用户给的路径收敛成绝对路径，并保证最后一层是项目代号。

    选 ``D:\\Data`` 时实际落点是 ``D:\\Data\\quick-run``；已经以项目代号
    结尾就原样用。相对路径以 ``base``（默认是默认数据目录）为基准。
    """
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    if not text:
        return DATA_DIR_DEFAULT
    path = Path(os.path.expandvars(text)).expanduser()
    if not path.is_absolute():
        path = (base or DATA_DIR_DEFAULT) / path
    path = Path(os.path.normpath(str(path)))
    if path.name.lower() != PROJECT:
        path = path / PROJECT
    return path


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


def write_data_dir(path: Path) -> None:
    """把数据目录写进指针文件。"""
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    temp = DATA_POINTER.with_suffix(".tmp")
    temp.write_text(str(path), encoding="utf-8", newline="\n")
    os.replace(temp, DATA_POINTER)


def pending_data_dir() -> Path | None:
    """上次「更改数据目录」记下的落点；没有就是 ``None``。"""
    try:
        text = DATA_PENDING.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not text:
        return None
    path = Path(text)
    return path if path.is_absolute() else None


def request_data_dir(raw: str, base: Path | None = None) -> Path:
    """记下新的数据目录，等下次启动搬过去。

    只写标记不搬文件：搬发生在下次启动、在所有业务模块打开文件之前，运行中的
    进程不会遇到「文件被搬走了」。改回当前目录时只清掉标记。
    """
    target = normalize_data_dir(raw, base)
    if target == read_data_dir():
        clear_pending_data_dir()
        return target
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    temp = DATA_PENDING.with_suffix(".tmp")
    temp.write_text(str(target), encoding="utf-8", newline="\n")
    os.replace(temp, DATA_PENDING)
    return target


def clear_pending_data_dir() -> None:
    """丢掉待搬迁标记。"""
    try:
        DATA_PENDING.unlink()
    except OSError:
        pass


def _is_nested(inner: Path, outer: Path) -> bool:
    """``inner`` 是否在 ``outer`` 里（含相等）。"""
    try:
        inner.relative_to(outer)
    except ValueError:
        return False
    return True


def _move_contents(source: Path, target: Path) -> tuple[list[str], int]:
    """把 ``source`` 里的东西搬到 ``target``。目标已有的同名项不覆盖。"""
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return [f"无法创建 {target}：{error}"], 0
    if not source.is_dir():
        return [], 0

    warnings: list[str] = []
    moved = 0
    for item in list(source.iterdir()):
        if item.suffix == ".lock":
            # 锁恒在本地目录，数据目录里的锁文件没有搬运价值。
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
            warnings.append(f"迁移 {item.name} 失败：{error}")
            continue
        moved += 1
    try:
        source.rmdir()
    except OSError:
        # 还有搬不走的文件（被占用、权限不足），目录留着即可。
        pass
    return warnings, moved


def _reconcile_data_dir() -> None:
    """启动时把数据目录收敛到最终位置。

    两件事：执行上次「更改数据目录」留下的搬迁，以及修正历史版本里没补项目
    代号的指针。两者都是「把旧目录的内容搬到新目录，再改指针」，走同一段代码。
    测试用 ``SIXCOIN_DATA_DIR`` 指定了目录，一律不碰。
    """
    global MIGRATION_WARNINGS, MIGRATED_ITEMS
    if os.environ.get(_ENV_DATA, "").strip():
        return
    source = read_data_dir()
    target = pending_data_dir() or normalize_data_dir(str(source))
    if target == source:
        clear_pending_data_dir()
        return
    if _is_nested(target, source) or _is_nested(source, target):
        MIGRATION_WARNINGS = [f"数据目录不能互相嵌套：{source} → {target}"]
        return
    try:
        MIGRATION_WARNINGS, MIGRATED_ITEMS = _move_contents(source, target)
        write_data_dir(target)
    except OSError as error:  # 指针写不下去就留在原处，下次启动再试
        MIGRATION_WARNINGS = [f"数据目录切换失败：{error}"]
        return
    clear_pending_data_dir()


#: 启动时搬迁数据的警告与条数，由 ``bootstrap.prepare()`` 取走写日志。
MIGRATION_WARNINGS: list[str] = []
MIGRATED_ITEMS = 0

_reconcile_data_dir()

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


def resolve_user_path(raw: str, base: str = DEFAULT_PATH_BASE) -> Path:
    """把配置里写下的路径解析成绝对路径。

    ``base`` 是这条操作自己的「路径基准」：

    * ``data``：相对路径从数据目录补全（``custom\\foo.py`` 指的就是那儿）；
    * ``program``：相对路径从程序目录补全；
    * ``absolute``：按绝对路径理解，万一填的还是相对路径，退回程序目录——
      启动子进程时的工作目录就是它，两者结果一致。

    无论选哪一种，绝对路径都原样返回；解析结果与进程的当前工作目录无关。
    """
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1]
    if not text:
        return PROGRAM_DIR
    path = Path(os.path.expandvars(text))
    if path.is_absolute():
        return path
    if normalize_path_base(base) == PathBase.DATA:
        return (DATA_DIR / path).resolve()
    return (PROGRAM_DIR / path).resolve()


def normalize_path_base(value: Any) -> str:
    """把任意输入收敛成三种基准之一；认不出来时用默认值。"""
    text = str(value or "").strip().lower()
    return text if text in PATH_BASE_VALUES else DEFAULT_PATH_BASE


def split_paths(raw: str, base: str = DEFAULT_PATH_BASE) -> list[Path]:
    """把配置里用 ``|`` 分隔的路径串拆成绝对路径列表。"""
    return [resolve_user_path(part, base) for part in (raw or "").split("|") if part.strip()]
