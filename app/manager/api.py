"""Everything the web UI is allowed to call.

One method per user intention, each returning a complete state snapshot so the
front end stays a pure renderer. Operations live in ordered, switchable groups;
the manager edits that structure directly.
"""

from __future__ import annotations

from typing import Any

import webview
from loguru import logger

from app import settings as settings_module
from app.models import (
    DEBUG_FUNCTIONS,
    DEFAULT_GROUP_NAME,
    FIELD_LABELS,
    TYPE_LABELS,
    TYPE_ORDER,
    Operation,
    OperationGroup,
    OperationType,
    default_arguments,
    validate_groups,
)

HELP_HTML = """
<h3>一、分组</h3>
<ul>
    <li>操作按分组组织。分组之间的顺序，就是启动器里结果的排列顺序。</li>
    <li>点击分组标题可以编辑分组名称，或用右侧开关整组关闭；关闭的分组不参与搜索。</li>
    <li>拖拽分组标题可以调整分组顺序。</li>
</ul>

<h3>二、操作类型</h3>
<ul>
    <li><b>打开文件</b>：用系统默认程序打开一个文件。可勾选“无窗口运行”以避免弹出命令行窗口。</li>
    <li><b>打开文件夹</b>：用文件资源管理器打开一个文件夹。可勾选“允许浏览子文件夹”以启用输入空格浏览子目录的功能（需设置探索深度）。</li>
    <li><b>打开网页</b>：用默认浏览器打开一个网址。</li>
    <li><b>执行命令</b>：在命令行中执行一条命令。</li>
    <li><b>程序调试</b>：重启或关闭 Fast Run 程序。</li>
</ul>

<h3>三、字段说明</h3>
<ul>
    <li><b>显示名称</b>：在结果列表中显示的文本。</li>
    <li><b>运行方式</b>：选择操作的类型。</li>
    <li><b>匹配字串</b>：只允许小写字母 <code>a-z</code> 和分隔符 <code>|</code>，前缀匹配。保存时会自动清理非法字符与多余的 <code>|</code>。</li>
    <li><b>切换到组</b>：把当前操作移动到别的分组（操作详情底部的按钮）。</li>
</ul>

<h3>四、文件夹浏览</h3>
<ul>
    <li>勾选“允许浏览子文件夹”后，在主搜索框输入关键词+空格即可进入该文件夹的子文件浏览模式。</li>
    <li>探索深度控制最多可以进入多少层子文件夹。0 表示仅显示根目录内容，2 表示可以进入一层子文件夹。</li>
    <li>深度最大不能超过 5。子文件夹内条目超过 100 个的不会被扫描。</li>
    <li>浏览模式下支持拼音搜索和序号选择（例：<code>关键词 a#2</code>）。</li>
</ul>

<h3>五、操作方式</h3>
<ul>
    <li>拖拽操作可以调整组内顺序，拖到别的分组标题上即可移动到该组末尾。</li>
    <li>按 <code>Ctrl + S</code> 保存，<code>Ctrl + F</code> 搜索。</li>
    <li>关闭窗口时若有未保存的更改，会询问是否保存。</li>
</ul>
"""


class ManagerApi:
    def __init__(self) -> None:
        self._groups: list[OperationGroup] = settings_module.load_groups()
        self._dirty = False
        self._errors: list[dict[str, Any]] = []
        self._window = None

        self._sel_kind = "none"
        self._sel_group = 0
        self._sel_index = 0
        self._select_initial()

    def attach(self, window) -> None:
        self._window = window

    @property
    def dirty(self) -> bool:
        return self._dirty

    # -- read -------------------------------------------------------------
    def get_state(self) -> dict[str, Any]:
        return self._state()

    def help_html(self) -> str:
        return HELP_HTML

    # -- selection --------------------------------------------------------
    def select_operation(self, group: int, index: int) -> dict[str, Any]:
        if self._valid_operation(group, index):
            self._sel_kind, self._sel_group, self._sel_index = "operation", group, index
        return self._state()

    def select_group(self, group: int) -> dict[str, Any]:
        if 0 <= group < len(self._groups):
            self._sel_kind, self._sel_group = "group", group
        return self._state()

    # -- structure --------------------------------------------------------
    def add_operation(self, group: int | None = None) -> dict[str, Any]:
        target = self._resolve_group(group)
        operation = Operation(
            type=OperationType.FILE, arguments=default_arguments(OperationType.FILE)
        )
        self._groups[target].operations.insert(0, operation)
        self._sel_kind, self._sel_group, self._sel_index = "operation", target, 0
        self._dirty = True

        group = self._groups[target]
        if not group.enabled:
            return self._state(
                ok=True,
                message=f"已添加到「{group.name}」，但该分组已关闭，不会出现在启动器中",
            )
        return self._state()

    def add_group(self) -> dict[str, Any]:
        self._groups.append(OperationGroup(name=self._next_group_name()))
        self._sel_kind, self._sel_group = "group", len(self._groups) - 1
        self._dirty = True
        return self._state()

    def delete_operation(self, group: int, index: int) -> dict[str, Any]:
        if not self._valid_operation(group, index):
            return self._state()
        del self._groups[group].operations[index]
        if not self._groups[group].operations:
            self._sel_kind, self._sel_group = "group", group
        else:
            self._sel_kind, self._sel_group = "operation", group
            self._sel_index = min(index, len(self._groups[group].operations) - 1)
        self._dirty = True
        return self._state()

    def delete_group(self, group: int) -> dict[str, Any]:
        if not 0 <= group < len(self._groups):
            return self._state()
        if len(self._groups) == 1:
            return self._state(ok=False, message="至少要保留一个分组")
        del self._groups[group]
        self._sel_kind, self._sel_group = "group", min(group, len(self._groups) - 1)
        self._dirty = True
        return self._state()

    def move_group(self, from_index: int, to_index: int) -> dict[str, Any]:
        if not (0 <= from_index < len(self._groups) and 0 <= to_index <= len(self._groups)):
            return self._state()
        group = self._groups.pop(from_index)
        if to_index > from_index:
            to_index -= 1
        to_index = max(0, min(to_index, len(self._groups)))
        self._groups.insert(to_index, group)
        self._sel_group = to_index
        self._dirty = True
        return self._state()

    def move_operation(
        self, from_group: int, from_index: int, to_group: int, to_index: int
    ) -> dict[str, Any]:
        if not self._valid_operation(from_group, from_index):
            return self._state()
        if not 0 <= to_group < len(self._groups):
            return self._state()

        operation = self._groups[from_group].operations.pop(from_index)
        if from_group == to_group and to_index > from_index:
            to_index -= 1
        target = self._groups[to_group].operations
        to_index = max(0, min(to_index, len(target)))
        target.insert(to_index, operation)

        self._sel_kind, self._sel_group, self._sel_index = "operation", to_group, to_index
        self._dirty = True
        return self._state()

    def move_operation_by(self, group: int, index: int, offset: int) -> dict[str, Any]:
        if not self._valid_operation(group, index):
            return self._state()
        operations = self._groups[group].operations
        target = index + offset
        if not 0 <= target < len(operations):
            return self._state()
        operations[index], operations[target] = operations[target], operations[index]
        self._sel_kind, self._sel_group, self._sel_index = "operation", group, target
        self._dirty = True
        return self._state()

    def move_group_by(self, group: int, offset: int) -> dict[str, Any]:
        if not 0 <= group < len(self._groups):
            return self._state()
        target = group + offset
        if not 0 <= target < len(self._groups):
            return self._state()
        self._groups[group], self._groups[target] = self._groups[target], self._groups[group]
        self._sel_kind, self._sel_group = "group", target
        self._dirty = True
        return self._state()

    # -- field edits ------------------------------------------------------
    def set_field(self, group: int, index: int, field: str, value: str) -> dict[str, Any]:
        if not self._valid_operation(group, index) or field not in ("display", "keywords"):
            return {"ok": False}
        setattr(self._groups[group].operations[index], field, str(value))
        self._dirty = True
        return {"ok": True}

    def set_argument(self, group: int, index: int, key: str, value: Any) -> dict[str, Any]:
        if not self._valid_operation(group, index):
            return {"ok": False}
        operation = self._groups[group].operations[index]
        if key not in default_arguments(operation.type):
            return {"ok": False}
        if key in ("no_window", "allow_explore"):
            operation.arguments[key] = bool(value)
        else:
            operation.arguments[key] = value
        self._dirty = True
        return {"ok": True}

    def change_type(self, group: int, index: int, op_type: str) -> dict[str, Any]:
        if not self._valid_operation(group, index) or op_type not in TYPE_ORDER:
            return self._state()
        self._groups[group].operations[index].change_type(op_type)
        self._dirty = True
        return self._state()

    def set_group_name(self, group: int, value: str) -> dict[str, Any]:
        if not 0 <= group < len(self._groups):
            return self._state()
        self._groups[group].name = str(value)
        self._dirty = True
        return self._state()

    def set_group_enabled(self, group: int, value: bool) -> dict[str, Any]:
        if not 0 <= group < len(self._groups):
            return self._state()
        self._groups[group].enabled = bool(value)
        self._dirty = True
        return self._state()

    # -- persistence ------------------------------------------------------
    def save(self) -> dict[str, Any]:
        # Normalise first: keyword cleanup can turn "|||" into an empty value,
        # which must then be reported as a validation error.
        cleaned = 0
        for group in self._groups:
            group.name = (group.name or "").strip() or DEFAULT_GROUP_NAME
            for operation in group.operations:
                before = operation.keywords
                operation.normalize()
                if operation.keywords != before:
                    cleaned += 1

        error = validate_groups(self._groups)
        if error is not None:
            group = self._groups[error.group]
            operation = group.operations[error.index]
            name = operation.display or "未命名操作"
            self._errors = [error.to_dict()]
            self._sel_kind, self._sel_group, self._sel_index = (
                "operation",
                error.group,
                error.index,
            )
            return self._state(
                ok=False, message=f"【{group.name} / {name}】的【{error.label}】不能为空。"
            )

        try:
            settings_module.save_groups(self._groups)
        except Exception as failure:  # noqa: BLE001 - surfaced to the UI
            logger.exception("保存操作列表失败")
            return self._state(ok=False, message=f"无法写入配置文件：\n{failure}")

        self._errors = []
        self._dirty = False
        message = "文件已成功保存"
        if cleaned:
            message += f"（已按规则清理 {cleaned} 条匹配字串）"
        return self._state(ok=True, message=message)

    # -- dialogs ----------------------------------------------------------
    def browse_file(self) -> str:
        return self._pick(webview.FileDialog.OPEN)

    def browse_dir(self) -> str:
        return self._pick(webview.FileDialog.FOLDER)

    # -- closing ----------------------------------------------------------
    def request_close(self) -> dict[str, str]:
        return {"action": "ask" if self._dirty else "close"}

    def force_close(self) -> None:
        if self._window is not None:
            self._window.destroy()

    # -- internals --------------------------------------------------------
    def _pick(self, dialog_type: int) -> str:
        if self._window is None:
            return ""
        try:
            result = self._window.create_file_dialog(dialog_type, allow_multiple=False)
        except Exception as error:  # noqa: BLE001 - dialog is best effort
            logger.warning("打开文件选择框失败：{}", error)
            return ""
        if not result:
            return ""
        if isinstance(result, (list, tuple)):
            return str(result[0])
        return str(result)

    def _valid_operation(self, group: int, index: int) -> bool:
        return (
            0 <= group < len(self._groups)
            and 0 <= index < len(self._groups[group].operations)
        )

    def _resolve_group(self, group: int | None) -> int:
        """Explicit index, otherwise the default group (the bottom-left button)."""
        if group is not None and 0 <= group < len(self._groups):
            return group
        for index, existing in enumerate(self._groups):
            if existing.name == DEFAULT_GROUP_NAME:
                return index
        return 0

    def _next_group_name(self) -> str:
        existing = {group.name for group in self._groups}
        index = 1
        while f"新分组 {index}" in existing:
            index += 1
        return f"新分组 {index}"

    def _select_initial(self) -> None:
        if self._groups and self._groups[0].operations:
            self._sel_kind, self._sel_group, self._sel_index = "operation", 0, 0
        elif self._groups:
            self._sel_kind, self._sel_group = "group", 0
        else:
            self._sel_kind = "none"

    def _state(self, ok: bool = True, message: str = "") -> dict[str, Any]:
        total = sum(len(group.operations) for group in self._groups)
        enabled_total = sum(
            len(group.operations) for group in self._groups if group.enabled
        )
        return {
            "ok": ok,
            "message": message,
            "groups": [
                {
                    "index": group_index,
                    "name": group.name,
                    "enabled": group.enabled,
                    "count": len(group.operations),
                    "operations": [
                        {
                            "index": index,
                            "group": group_index,
                            "display": operation.display,
                            "label": operation.display or "未命名操作",
                            "type": operation.type,
                            "type_label": TYPE_LABELS.get(operation.type, operation.type),
                            "keywords": operation.keywords,
                            "arguments": dict(operation.arguments),
                        }
                        for index, operation in enumerate(group.operations)
                    ],
                }
                for group_index, group in enumerate(self._groups)
            ],
            "selection": {
                "kind": self._sel_kind,
                "group": self._sel_group,
                "index": self._sel_index,
            },
            "total": total,
            "enabled_total": enabled_total,
            "dirty": self._dirty,
            "errors": list(self._errors),
            "types": [{"value": value, "label": TYPE_LABELS[value]} for value in TYPE_ORDER],
            "debug_functions": [
                {"value": value, "label": label} for value, label in DEBUG_FUNCTIONS
            ],
            "field_labels": FIELD_LABELS,
            "default_group_name": DEFAULT_GROUP_NAME,
        }
