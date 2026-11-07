"""Config loading, validation and persistence.

Replaces the hand rolled JSON-schema validator with explicit checks: the config
files are small and fixed, so readable code beats a mini framework. All paths
come from :mod:`app.paths` and are absolute.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from app import paths
from app.errors import ConfigError
from app.models import (
    DEFAULT_GROUP_NAME,
    Operation,
    OperationGroup,
    flatten_groups,
)

_OPERATION_KEYS = ("display", "type", "arguments", "keywords")
CONFIG_VERSION = 2


@dataclass(frozen=True)
class TranslateConfig:
    appid: str
    secret_key: str


@dataclass
class AppSettings:
    groups: list[OperationGroup] = field(default_factory=list)
    translate: TranslateConfig | None = None
    ai_api_key: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def operations(self) -> list[Operation]:
        """Enabled operations in group order, as the launcher sees them."""
        return flatten_groups(self.groups)


def default_operations() -> list[dict[str, Any]]:
    program_dir = str(paths.PROGRAM_DIR)
    startup_dir = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup"
    return [
        {
            "display": "重启程序",
            "type": "debug",
            "keywords": "sys:restart|restart",
            "arguments": {"function": "restart"},
        },
        {
            "display": "关闭程序",
            "type": "debug",
            "keywords": "sys:close|close",
            "arguments": {"function": "close"},
        },
        {
            "display": "操作管理与帮助",
            "type": "file",
            "keywords": "sys:manager|manager|sys:help|help",
            "arguments": {"path": "manager.pyw", "no_window": False},
        },
        {
            "display": "打开程序文件夹",
            "type": "dir",
            "keywords": "sys:folder|folder",
            "arguments": {"dir": program_dir, "allow_explore": True, "explore_depth": 0},
        },
        {
            "display": "打开启动文件夹",
            "type": "dir",
            "keywords": "sys:startup|startup",
            "arguments": {"dir": startup_dir, "allow_explore": True, "explore_depth": 0},
        },
        {
            "display": "调试：运行开机启动文件",
            "type": "file",
            "keywords": "debug:startup_file",
            "arguments": {"path": startup_dir + r"\run.pyw", "no_window": False},
        },
        {
            "display": "调试：关闭所有正在运行的 Python 程序并重启",
            "type": "file",
            "keywords": "debug:close_python",
            "arguments": {"path": r"custom\debug.bat", "no_window": True},
        },
    ]


def default_groups() -> list[dict[str, Any]]:
    """Payload for a fresh config file: one group holding the starter actions."""
    return [{"name": DEFAULT_GROUP_NAME, "enabled": True, "operations": default_operations()}]


# -- groups ---------------------------------------------------------------
def load_groups(path: Path | None = None) -> list[OperationGroup]:
    target = Path(path) if path is not None else paths.OPERATIONS_PATH

    if not target.exists():
        _write_json(target, {"version": CONFIG_VERSION, "groups": default_groups()})

    return _parse_groups(_read_json(target), target)


def save_groups(groups: list[OperationGroup], path: Path | None = None) -> None:
    target = Path(path) if path is not None else paths.OPERATIONS_PATH
    payload = {
        "version": CONFIG_VERSION,
        "groups": [group.to_dict() for group in groups],
    }
    _write_json(target, payload)
    logger.info(
        "操作列表已保存：{} 个分组，{} 条操作",
        len(groups),
        sum(len(group.operations) for group in groups),
    )


def _parse_groups(data: Any, target: Path) -> list[OperationGroup]:
    # v1 configs are a bare array; wrap them into a single group on the fly.
    if isinstance(data, list):
        return [
            OperationGroup(
                name=DEFAULT_GROUP_NAME,
                enabled=True,
                operations=_parse_operations(data, "配置"),
            )
        ]

    if not isinstance(data, dict):
        raise ConfigError(f"{target.name} 的顶层必须是对象或列表")

    raw_groups = data.get("groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ConfigError(f"{target.name} 至少需要包含一个分组")

    groups: list[OperationGroup] = []
    for group_index, item in enumerate(raw_groups):
        if not isinstance(item, dict):
            raise ConfigError(f"第 {group_index + 1} 个分组必须是对象")
        name = str(item.get("name") or "").strip() or DEFAULT_GROUP_NAME
        raw_operations = item.get("operations", [])
        if not isinstance(raw_operations, list):
            raise ConfigError(f"分组「{name}」的 operations 必须是列表")
        groups.append(
            OperationGroup(
                name=name,
                enabled=bool(item.get("enabled", True)),
                operations=_parse_operations(raw_operations, f"分组「{name}」"),
            )
        )
    return groups


def _parse_operations(items: list[Any], where: str) -> list[Operation]:
    operations: list[Operation] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigError(f"{where}第 {index + 1} 条操作必须是对象")
        missing = [key for key in _OPERATION_KEYS if key not in item]
        if missing:
            raise ConfigError(f"{where}第 {index + 1} 条操作缺少字段：{'、'.join(missing)}")
        operations.append(Operation.from_dict(item))
    return operations


# -- optional services ----------------------------------------------------
def load_translate(path: Path | None = None) -> TranslateConfig | None:
    target = Path(path) if path is not None else paths.TRANSLATE_PATH
    data = _read_json_or_default(target, {"appid": "", "secret_key": ""})
    appid = str(data.get("appid", "")).strip()
    secret_key = str(data.get("secret_key", "")).strip()
    if not appid or not secret_key:
        return None
    return TranslateConfig(appid=appid, secret_key=secret_key)


def load_ai_key(path: Path | None = None) -> str:
    target = Path(path) if path is not None else paths.AI_PATH
    data = _read_json_or_default(target, {"api_key": ""})
    return str(data.get("api_key", "")).strip()


def load_settings() -> AppSettings:
    """Load everything; only the operations file is fatal."""
    settings = AppSettings(groups=load_groups())

    if not any(group.enabled for group in settings.groups):
        settings.warnings.append("所有分组都已关闭，启动器只会显示搜索、计算与翻译")

    try:
        settings.translate = load_translate()
        if settings.translate is None:
            settings.warnings.append("实时翻译功能已关闭，因为未配置 appid / secret_key")
    except ConfigError as error:
        settings.warnings.append(f"实时翻译功能已关闭，因为无法读取翻译配置：{error}")

    try:
        settings.ai_api_key = load_ai_key()
        if not settings.ai_api_key:
            settings.warnings.append("AI 查词功能已关闭，因为未配置 api_key")
    except ConfigError as error:
        settings.warnings.append(f"AI 查词功能已关闭，因为无法读取 AI 配置：{error}")

    return settings


def _read_json(path: Path) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as error:
        raise ConfigError(f"找不到文件 {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"{path.name} 不是合法的 JSON：{error}") from error
    except OSError as error:
        raise ConfigError(f"无法读取 {path.name}：{error}") from error


def _read_json_or_default(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        _write_json(path, default)
        return dict(default)
    data = _read_json(path)
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name} 的顶层必须是对象")
    return data


def _write_json(path: Path, payload: Any) -> None:
    """Write atomically so a crash can never leave a half written config."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=4, ensure_ascii=False)
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
