"""配置的读取、校验与写入。

配置分成两个文件，职责很明确：

* ``config/app.json``：应用级设置，包括语言、外观、文件夹浏览上限和外部
  服务密钥；
* ``config/operations.json``：操作列表，根层就是一个分组数组。

这里不用任何 JSON Schema 框架：文件结构很小且固定，写清楚校验代码比引入
一套迷你框架更好读。所有路径都来自 :mod:`app.paths`，且都是绝对路径。
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from app import i18n, paths
from app.errors import ConfigError
from app.models import (
    MAX_EXPLORE_DEPTH,
    Operation,
    OperationGroup,
    flatten_groups,
)
from app.system.theme import normalize_theme, system_theme

_OPERATION_KEYS = ("display", "type", "arguments", "keywords")

#: 单目录条目上限的取值范围，避免手改配置写进离谱的数字。
MAX_ENTRIES_RANGE = (1, 10000)

#: 单目录条目上限的默认值，也是读不出数字时的回退值。
DEFAULT_MAX_ENTRIES = 100

#: 淡入、淡出时长的取值范围与默认值（毫秒）。0 表示不做动画。
ANIMATION_RANGE = (0, 1000)
DEFAULT_ANIMATION_IN_MS = 150
DEFAULT_ANIMATION_OUT_MS = 150


@dataclass(frozen=True)
class TranslateConfig:
    """百度翻译所需的凭据。"""

    appid: str
    secret_key: str


@dataclass
class AppConfig:
    """``config/app.json`` 的内存表示。

    字段在内存里是扁平的，写盘时再还原成嵌套结构，这样调用方不用一路
    ``config.navigation.max_depth`` 地点下去。
    """

    language: str = i18n.DEFAULT_LANGUAGE
    theme: str = "light"
    animation_in_ms: int = DEFAULT_ANIMATION_IN_MS
    animation_out_ms: int = DEFAULT_ANIMATION_OUT_MS
    max_depth: int = MAX_EXPLORE_DEPTH
    max_entries: int = DEFAULT_MAX_ENTRIES
    translate_appid: str = ""
    translate_secret: str = ""
    ai_api_key: str = ""

    @property
    def translate(self) -> TranslateConfig | None:
        """appid 与密钥都填了才算启用翻译。"""
        if not self.translate_appid or not self.translate_secret:
            return None
        return TranslateConfig(self.translate_appid, self.translate_secret)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        animation = data.get("animation")
        animation = animation if isinstance(animation, dict) else {}
        navigation = data.get("navigation")
        navigation = navigation if isinstance(navigation, dict) else {}
        translate = data.get("translate")
        translate = translate if isinstance(translate, dict) else {}
        ai = data.get("ai")
        ai = ai if isinstance(ai, dict) else {}
        return cls(
            language=i18n.normalize(data.get("language")),
            theme=normalize_theme(data.get("theme")),
            animation_in_ms=clamp_animation(animation.get("in_ms"), DEFAULT_ANIMATION_IN_MS),
            animation_out_ms=clamp_animation(animation.get("out_ms"), DEFAULT_ANIMATION_OUT_MS),
            max_depth=clamp_depth(navigation.get("max_depth")),
            max_entries=clamp_entries(navigation.get("max_entries")),
            translate_appid=str(translate.get("appid") or "").strip(),
            translate_secret=str(translate.get("secret_key") or "").strip(),
            ai_api_key=str(ai.get("api_key") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "theme": self.theme,
            "animation": {
                "in_ms": self.animation_in_ms,
                "out_ms": self.animation_out_ms,
            },
            "navigation": {
                "max_depth": self.max_depth,
                "max_entries": self.max_entries,
            },
            "translate": {
                "appid": self.translate_appid,
                "secret_key": self.translate_secret,
            },
            "ai": {"api_key": self.ai_api_key},
        }


@dataclass
class AppSettings:
    """启动器需要的一次性快照。"""

    groups: list[OperationGroup] = field(default_factory=list)
    config: AppConfig = field(default_factory=AppConfig)
    warnings: list[str] = field(default_factory=list)

    @property
    def operations(self) -> list[Operation]:
        """按分组顺序展平后的操作，已跳过关闭的分组。"""
        return flatten_groups(self.groups)

    @property
    def translate(self) -> TranslateConfig | None:
        return self.config.translate

    @property
    def ai_api_key(self) -> str:
        return self.config.ai_api_key


def default_operations() -> list[dict[str, Any]]:
    """首次生成配置文件时写入的示例操作。"""
    startup_dir = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Startup"
    return [
        {
            "display": i18n.t("default.manager"),
            "type": "file",
            "keywords": "manager",
            "arguments": {"path": "manager.bat", "no_window": True},
        },
        {
            "display": i18n.t("default.program_folder"),
            "type": "dir",
            "keywords": "folder",
            "arguments": {"dir": ".", "allow_explore": False, "explore_depth": 0},
        },
        {
            "display": i18n.t("default.startup_folder"),
            "type": "dir",
            "keywords": "startup",
            "arguments": {"dir": startup_dir, "allow_explore": False, "explore_depth": 0},
        },
        {
            "display": i18n.t("debug.restart"),
            "type": "debug",
            "keywords": "restart",
            "arguments": {"function": "restart"},
        },
        {
            "display": i18n.t("debug.close"),
            "type": "debug",
            "keywords": "close",
            "arguments": {"function": "close"},
        },
    ]


def default_groups() -> list[dict[str, Any]]:
    """首次生成操作文件时写入的初始分组数组。"""
    return [
        {
            "name": i18n.t("default.group"),
            "enabled": True,
            "operations": default_operations(),
        }
    ]


# -- 应用级配置 -----------------------------------------------------------
def load_app_config(path: Path | None = None) -> AppConfig:
    """读取 ``app.json``；文件不存在时按系统外观创建一份。"""
    target = Path(path) if path is not None else paths.APP_CONFIG_PATH

    if not target.exists():
        config = AppConfig(theme=system_theme())
        _write_json(target, config.to_dict())
        logger.info("已生成默认配置：{}", target)
        return config

    data = _read_json(target)
    if not isinstance(data, dict):
        raise ConfigError(i18n.t("config.root_not_object", name=target.name))
    return AppConfig.from_dict(data)


def save_app_config(config: AppConfig, path: Path | None = None) -> None:
    target = Path(path) if path is not None else paths.APP_CONFIG_PATH
    _write_json(target, config.to_dict())
    logger.info("应用配置已保存：{}", target)


# -- 操作列表 -------------------------------------------------------------
def load_groups(path: Path | None = None) -> list[OperationGroup]:
    """读取分组数组，文件不存在时写入初始内容。"""
    target = Path(path) if path is not None else paths.OPERATIONS_PATH

    if not target.exists():
        _write_json(target, default_groups())

    return _parse_groups(_read_json(target), target)


def save_groups(groups: list[OperationGroup], path: Path | None = None) -> None:
    target = Path(path) if path is not None else paths.OPERATIONS_PATH
    _write_json(target, [group.to_dict() for group in groups])
    logger.info(
        "操作列表已保存：{} 个分组，{} 条操作",
        len(groups),
        sum(len(group.operations) for group in groups),
    )


def _parse_groups(data: Any, target: Path) -> list[OperationGroup]:
    if not isinstance(data, list):
        raise ConfigError(i18n.t("config.root_not_list", name=target.name))
    if not data:
        raise ConfigError(i18n.t("config.need_group", name=target.name))

    groups: list[OperationGroup] = []
    for group_index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ConfigError(i18n.t("config.group_not_object", index=group_index + 1))
        name = str(item.get("name") or "").strip() or i18n.t("manager.unnamed_group")
        raw_operations = item.get("operations", [])
        if not isinstance(raw_operations, list):
            raise ConfigError(i18n.t("config.ops_not_list", name=name))
        groups.append(
            OperationGroup(
                name=name,
                enabled=bool(item.get("enabled", True)),
                operations=_parse_operations(raw_operations, name),
            )
        )
    return groups


def _parse_operations(items: list[Any], group_name: str) -> list[Operation]:
    """解析一个分组下的操作数组，出错时把分组名带进提示里。"""
    operations: list[Operation] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigError(i18n.t("config.op_not_object_in", name=group_name, index=index + 1))
        missing = [key for key in _OPERATION_KEYS if key not in item]
        if missing:
            fields = i18n.list_separator().join(missing)
            raise ConfigError(
                i18n.t(
                    "config.op_missing_in",
                    name=group_name,
                    index=index + 1,
                    fields=fields,
                )
            )
        operations.append(Operation.from_dict(item))
    return operations


def load_settings() -> AppSettings:
    """读取全部配置并切好语言。

    只有配置或操作列表损坏才会抛 :class:`ConfigError`；缺少可选服务凭据
    只记一条警告，程序照常运行。
    """
    config = load_app_config()
    i18n.set_language(config.language)

    settings = AppSettings(groups=load_groups(), config=config)

    if not any(group.enabled for group in settings.groups):
        settings.warnings.append(i18n.t("warn.no_enabled_group"))
    if config.translate is None:
        settings.warnings.append(i18n.t("warn.translate_off"))
    if not config.ai_api_key:
        settings.warnings.append(i18n.t("warn.ai_off"))

    return settings


# -- 底层读写 -------------------------------------------------------------
def _read_json(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as error:
        raise ConfigError(i18n.t("config.not_found", path=path)) from error
    except json.JSONDecodeError as error:
        raise ConfigError(i18n.t("config.bad_json", name=path.name, error=error)) from error
    except OSError as error:
        raise ConfigError(i18n.t("config.unreadable", name=path.name, error=error)) from error


def _write_json(path: Path, payload: Any) -> None:
    """原子写入：中途崩溃也不会留下写了一半的配置。"""
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


def clamp_depth(value: Any) -> int:
    try:
        depth = int(str(value).strip())
    except (TypeError, ValueError):
        return MAX_EXPLORE_DEPTH
    return max(0, min(depth, MAX_EXPLORE_DEPTH))


def clamp_entries(value: Any) -> int:
    low, high = MAX_ENTRIES_RANGE
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_MAX_ENTRIES
    return max(low, min(count, high))


def clamp_animation(value: Any, default: int) -> int:
    """淡入 / 淡出时长夹到 0–1000；读不出数字时回退 ``default``。

    0 是合法值，意思是「不做动画」，所以这里不能拿 0 当「没填」。
    """
    low, high = ANIMATION_RANGE
    try:
        duration = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(low, min(duration, high))
