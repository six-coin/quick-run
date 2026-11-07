"""Domain model for a single operation entry.

The JSON layout is a hard contract with existing ``config/operations.json``
files and must stay byte-compatible:

    {"display": str, "type": str, "keywords": str, "arguments": {...}}
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

MAX_EXPLORE_DEPTH = 5


class OperationType:
    """String constants instead of an Enum so the JSON round-trip stays trivial."""

    FILE = "file"
    DIR = "dir"
    URL = "url"
    CMD = "cmd"
    DEBUG = "debug"


#: Display order of the "运行方式" selector; kept identical to the old manager.
TYPE_ORDER: tuple[str, ...] = (
    OperationType.FILE,
    OperationType.DIR,
    OperationType.URL,
    OperationType.CMD,
    OperationType.DEBUG,
)


TYPE_LABELS: dict[str, str] = {
    OperationType.FILE: "打开文件",
    OperationType.DIR: "打开文件夹",
    OperationType.URL: "打开网页",
    OperationType.CMD: "执行命令",
    OperationType.DEBUG: "程序调试",
}

TYPE_DEFAULTS: dict[str, dict[str, Any]] = {
    OperationType.FILE: {"path": "", "no_window": False},
    OperationType.DIR: {"dir": "", "allow_explore": True, "explore_depth": 0},
    OperationType.URL: {"url": ""},
    OperationType.CMD: {"command": ""},
    OperationType.DEBUG: {"function": "restart"},
}

DEBUG_FUNCTIONS = (("restart", "重启程序"), ("close", "关闭程序"))

FIELD_LABELS: dict[str, str] = {
    "display": "显示名称",
    "type": "运行方式",
    "keywords": "匹配字串",
    "path": "文件路径",
    "dir": "文件夹路径",
    "url": "网页地址",
    "command": "执行命令",
}

#: Which argument key each type requires to be non-empty.
REQUIRED_ARGUMENT: dict[str, str] = {
    OperationType.FILE: "path",
    OperationType.DIR: "dir",
    OperationType.URL: "url",
    OperationType.CMD: "command",
}


def default_arguments(op_type: str) -> dict[str, Any]:
    return dict(TYPE_DEFAULTS.get(op_type, {}))


def sanitize_keywords(raw: str) -> str:
    """Keywords may only contain ``a-z`` and ``|``.

    Lowercases, drops every other character, removes empty segments (so
    ``"a||b|"`` becomes ``"a|b"``) and returns ``""`` when nothing is left.
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


DEFAULT_GROUP_NAME = "默认分组"


@dataclass(frozen=True)
class FieldError:
    """Points at the first invalid field of a given operation."""

    group: int
    index: int
    field: str

    @property
    def label(self) -> str:
        return FIELD_LABELS.get(self.field, self.field)

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": self.group,
            "index": self.index,
            "field": self.field,
            "label": self.label,
        }


@dataclass
class OperationGroup:
    """A named, switchable bucket of operations.

    Group order defines the order the launcher lists matches in; a disabled
    group is skipped entirely at load time.
    """

    name: str = DEFAULT_GROUP_NAME
    enabled: bool = True
    operations: list[Operation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationGroup":
        raw_operations = data.get("operations")
        operations = [
            Operation.from_dict(item)
            for item in (raw_operations if isinstance(raw_operations, list) else [])
            if isinstance(item, dict)
        ]
        return cls(
            name=str(data.get("name") or DEFAULT_GROUP_NAME),
            enabled=bool(data.get("enabled", True)),
            operations=operations,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "operations": [operation.to_dict() for operation in self.operations],
        }

    def normalize(self) -> None:
        self.name = (self.name or "").strip() or DEFAULT_GROUP_NAME
        for operation in self.operations:
            operation.normalize()


@dataclass
class Operation:
    display: str = ""
    type: str = OperationType.FILE
    arguments: dict[str, Any] = field(default_factory=lambda: default_arguments(OperationType.FILE))
    keywords: str = ""
    #: Only used to keep list selection stable while dragging; never serialized.
    uid: str = field(default_factory=lambda: uuid.uuid4().hex, compare=False, repr=False)

    # -- construction -----------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Operation":
        op_type = str(data.get("type") or OperationType.FILE)
        raw_args = data.get("arguments")
        arguments = dict(raw_args) if isinstance(raw_args, dict) else {}
        # Fill in anything the file is missing so the rest of the app can rely
        # on the keys existing, while keeping unknown keys untouched.
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

    # -- behaviour --------------------------------------------------------
    def keyword_list(self) -> list[str]:
        return self.keywords.split("|")

    def change_type(self, new_type: str) -> None:
        """Switch type, carrying a path over between ``file`` and ``dir``."""
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
        """Trim and canonicalise user input right before it is written to disk."""
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
        """Name of the first field that would block saving, if any."""
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
    """First invalid field across every group, in display order."""
    for group_index, group in enumerate(groups):
        for index, operation in enumerate(group.operations):
            field_name = operation.first_invalid_field()
            if field_name is not None:
                return FieldError(group_index, index, field_name)
    return None


def flatten_groups(groups: list[OperationGroup], enabled_only: bool = True) -> list[Operation]:
    """Operations in group order, ready for the launcher catalog."""
    operations: list[Operation] = []
    for group in groups:
        if enabled_only and not group.enabled:
            continue
        operations.extend(group.operations)
    return operations

