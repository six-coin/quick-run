"""单条操作的领域模型。

JSON 结构是对外的硬约定，必须保持稳定：

    {"display": 字符串, "type": 字符串, "keywords": 字符串, "arguments": {...}}

分组只是操作的有序容器，本身不带任何行为。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app import i18n

#: 单条操作允许的探索深度上限，属于安全边界而不是用户偏好。
MAX_EXPLORE_DEPTH = 5


class OperationType:
    """用字符串常量而不是枚举，JSON 往返最省事。"""

    FILE = "file"
    DIR = "dir"
    URL = "url"
    CMD = "cmd"
    DEBUG = "debug"


#: “运行方式”选择器的显示顺序。
TYPE_ORDER: tuple[str, ...] = (
    OperationType.FILE,
    OperationType.DIR,
    OperationType.URL,
    OperationType.CMD,
    OperationType.DEBUG,
)

#: 每种类型需要用户填写的必填参数。
TYPE_DEFAULTS: dict[str, dict[str, Any]] = {
    OperationType.FILE: {"path": "", "no_window": False},
    OperationType.DIR: {"dir": "", "allow_explore": True, "explore_depth": 0},
    OperationType.URL: {"url": ""},
    OperationType.CMD: {"command": ""},
    OperationType.DEBUG: {"function": "restart"},
}

#: “程序调试”里可选的调试动作。
DEBUG_FUNCTION_VALUES: tuple[str, ...] = ("restart", "close")

#: 哪种类型的哪个参数不能为空。
REQUIRED_ARGUMENT: dict[str, str] = {
    OperationType.FILE: "path",
    OperationType.DIR: "dir",
    OperationType.URL: "url",
    OperationType.CMD: "command",
}


def type_label(op_type: str) -> str:
    """运行方式在界面上的名字。"""
    return i18n.t(f"type.{op_type}")


def field_label(field_name: str) -> str:
    """字段在界面上的名字。"""
    return i18n.t(f"field.{field_name}")


def debug_label(value: str) -> str:
    """调试动作在界面上的名字。"""
    return i18n.t(f"debug.{value}")


def default_arguments(op_type: str) -> dict[str, Any]:
    return dict(TYPE_DEFAULTS.get(op_type, {}))


def sanitize_keywords(raw: str) -> str:
    """匹配字串只允许 ``a-z`` 与 ``|``。

    会转小写、丢掉其他字符、去掉空段（``"a||b|"`` 变成 ``"a|b"``）并去重；
    什么都不剩时返回空串，由上层当作“没填”处理。
    """
    lowered = (raw or "").lower()
    cleaned = "".join(
        char for char in lowered if ("a" <= char <= "z") or char == "|"
    )
    unique: list[str] = []
    for part in cleaned.split("|"):
        if part and part not in unique:
            unique.append(part)
    return "|".join(unique)


@dataclass(frozen=True)
class FieldError:
    """指出某条操作里第一个不合法的字段。"""

    group: int
    index: int
    field: str

    @property
    def label(self) -> str:
        return field_label(self.field)

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "index": self.index,
            "field": self.field,
            "label": self.label,
        }


@dataclass
class OperationGroup:
    """有名字、可整体开关的操作集合。

    分组的顺序决定启动器里结果的顺序；关闭的分组在加载时整组跳过。
    """

    name: str = ""
    enabled: bool = True
    operations: list[Operation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "operations": [operation.to_dict() for operation in self.operations],
        }

    def normalize(self) -> None:
        """写盘前统一整理：名字去空格，操作各自整理。"""
        self.name = (self.name or "").strip()
        for operation in self.operations:
            operation.normalize()


@dataclass
class Operation:
    display: str = ""
    type: str = OperationType.FILE
    arguments: dict[str, Any] = field(default_factory=lambda: default_arguments(OperationType.FILE))
    keywords: str = ""
    #: 仅用于拖拽时保持选中稳定，永远不写进配置文件。
    uid: str = field(default_factory=lambda: uuid.uuid4().hex, compare=False, repr=False)

    # -- 构造 -------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Operation":
        op_type = str(data.get("type") or OperationType.FILE)
        raw_args = data.get("arguments")
        arguments = dict(raw_args) if isinstance(raw_args, dict) else {}
        # 补齐文件里缺的键，让下游可以放心取值；未知的键原样保留。
        for key, value in default_arguments(op_type).items():
            arguments.setdefault(key, value)
        return cls(
            display=str(data.get("display") or ""),
            type=op_type,
            arguments=arguments,
            keywords=str(data.get("keywords") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "display": self.display,
            "type": self.type,
            "keywords": self.keywords,
            "arguments": self.arguments,
        }

    def copy(self) -> "Operation":
        return Operation(
            display=self.display,
            type=self.type,
            arguments=dict(self.arguments),
            keywords=self.keywords,
        )

    # -- 行为 -------------------------------------------------------------
    def keyword_list(self) -> list[str]:
        return self.keywords.split("|")

    def change_type(self, new_type: str) -> None:
        """切换类型，并在文件和文件夹之间搬运已经填好的路径。"""
        if new_type == self.type:
            return
        old_type = self.type
        old_args = self.arguments
        new_args = default_arguments(new_type)
        if new_type == OperationType.FILE and old_type == OperationType.DIR:
            new_args["path"] = old_args.get("dir", "")
        elif new_type == OperationType.DIR and old_type == OperationType.FILE:
            new_args["dir"] = old_args.get("path", "")
        self.type = new_type
        self.arguments = new_args

    def normalize(self) -> None:
        """写盘前把用户输入整理成规范形式。"""
        self.display = (self.display or "").strip()
        self.keywords = sanitize_keywords(self.keywords)
        args = self.arguments

        if self.type == OperationType.FILE:
            args["path"] = str(args.get("path", "")).strip().strip('"').replace("/", "\\")
            args["no_window"] = bool(args.get("no_window", False))
        elif self.type == OperationType.DIR:
            args["dir"] = str(args.get("dir", "")).strip().strip('"').replace("/", "\\")
            args["allow_explore"] = bool(args.get("allow_explore", True))
            args["explore_depth"] = _clamp_depth(args.get("explore_depth", 0))
        elif self.type == OperationType.URL:
            args["url"] = str(args.get("url", "")).strip().replace("\\", "/")
        elif self.type == OperationType.CMD:
            args["command"] = str(args.get("command", "")).strip()

    def first_invalid_field(self) -> str | None:
        """返回第一个会阻止保存的字段名，全部合法时返回 ``None``。"""
        if not (self.display or "").strip():
            return "display"
        if not (self.type or "").strip():
            return "type"
        if not sanitize_keywords(self.keywords):
            return "keywords"
        required = REQUIRED_ARGUMENT.get(self.type)
        if required and not str(self.arguments.get(required, "")).strip():
            return required
        return None

    def explore_depth(self) -> int:
        return _clamp_depth(self.arguments.get("explore_depth", 0))

    def allow_explore(self) -> bool:
        return bool(self.arguments.get("allow_explore", True))


def _clamp_depth(value: Any) -> int:
    try:
        depth = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    return max(0, min(depth, MAX_EXPLORE_DEPTH))


def validate_groups(groups: list[OperationGroup]) -> FieldError | None:
    """按显示顺序找出第一个不合法的字段。"""
    for group_index, group in enumerate(groups):
        for index, operation in enumerate(group.operations):
            field_name = operation.first_invalid_field()
            if field_name is not None:
                return FieldError(group_index, index, field_name)
    return None


def flatten_groups(groups: list[OperationGroup], enabled_only: bool = True) -> list[Operation]:
    """按分组顺序展平，供启动器的操作目录使用。"""
    operations: list[Operation] = []
    for group in groups:
        if enabled_only and not group.enabled:
            continue
        operations.extend(group.operations)
    return operations
