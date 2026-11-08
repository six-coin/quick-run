"""网页界面允许调用的全部接口。

一个用户意图对应一个方法，每个方法都返回完整的状态快照，前端因此可以写成
纯粹的渲染器。操作存放在有序、可整体开关的分组里，管理器直接编辑这个结构。
"""

from __future__ import annotations

import threading
from typing import Any

import webview
from loguru import logger

from app import i18n
from app import settings as settings_module
from app.manager.dialogs import confirm_unsaved
from app.models import (
    DEBUG_FUNCTION_VALUES,
    MAX_EXPLORE_DEPTH,
    TYPE_ORDER,
    Operation,
    OperationGroup,
    OperationType,
    debug_label,
    default_arguments,
    field_label,
    type_label,
    validate_groups,
)
from app.system.theme import normalize_theme

#: 分组名为空时使用的兜底文案键。刻意起得中性一点，避免看起来像程序内置的分组。
FALLBACK_GROUP_NAME_KEY = "manager.unnamed_group"


class ManagerApi:
    def __init__(self) -> None:
        self._config = settings_module.load_app_config()
        i18n.set_language(self._config.language)

        self._groups: list[OperationGroup] = settings_module.load_groups()
        self._dirty = False
        self._errors: list[dict[str, Any]] = []
        self._window = None

        self._sel_kind = "none"
        self._sel_group = 0
        self._sel_index = 0
        self._select_initial()

        # 关闭确认与页面之间的握手。``closing`` 回调跑在 UI 线程上，
        # 在那里碰网页会死锁，所以只能交给工作线程去弹页面自己的对话框。
        self._close_confirmed = False
        self._close_prompting = False

    def attach(self, window) -> None:
        self._window = window

    @property
    def dirty(self) -> bool:
        return self._dirty

    # -- 读取 -------------------------------------------------------------
    def get_state(self) -> dict[str, Any]:
        return self._state()

    def get_strings(self) -> dict[str, Any]:
        """返回当前语言的文案表，网页启动时取一次。"""
        return {
            "language": i18n.language(),
            "strings": i18n.strings(),
        }

    def help_html(self) -> str:
        return i18n.help_html()

    def get_settings(self) -> dict[str, Any]:
        """设置弹窗需要的全部字段。"""
        return {
            "language": self._config.language,
            "theme": self._config.theme,
            "max_depth": self._config.max_depth,
            "max_entries": self._config.max_entries,
            "translate_appid": self._config.translate_appid,
            "translate_secret": self._config.translate_secret,
            "ai_api_key": self._config.ai_api_key,
            "languages": [
                {"value": code, "label": label}
                for code, label in i18n.LANGUAGE_NAMES.items()
            ],
            "themes": [
                {"value": "light", "label": i18n.t("settings.light")},
                {"value": "dark", "label": i18n.t("settings.dark")},
            ],
            "max_depth_limit": MAX_EXPLORE_DEPTH,
            "max_entries_range": list(settings_module.MAX_ENTRIES_RANGE),
        }

    # -- 选择 -------------------------------------------------------------
    def select_operation(self, group: int, index: int) -> dict[str, Any]:
        if self._valid_operation(group, index):
            self._sel_kind, self._sel_group, self._sel_index = "operation", group, index
        return self._state()

    def select_group(self, group: int) -> dict[str, Any]:
        if 0 <= group < len(self._groups):
            self._sel_kind, self._sel_group = "group", group
        return self._state()

    # -- 结构 -------------------------------------------------------------
    def add_operation(self, group: int) -> dict[str, Any]:
        """在指定分组的最前面插入一条空操作。

        这里没有“当前分组”或“默认分组”之类的兜底：调用方（分组行上的加号、
        分组详情页的按钮）永远知道自己要往哪个组里加。
        """
        if not 0 <= group < len(self._groups):
            return self._state()

        operation = Operation(
            type=OperationType.FILE, arguments=default_arguments(OperationType.FILE)
        )
        self._groups[group].operations.insert(0, operation)
        self._sel_kind, self._sel_group, self._sel_index = "operation", group, 0
        self._dirty = True

        target = self._groups[group]
        if not target.enabled:
            return self._state(
                ok=True,
                message=i18n.t("manager.added_disabled", name=target.name),
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
            return self._state(ok=False, message=i18n.t("manager.only_one_group"))
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

    # -- 字段编辑 ---------------------------------------------------------
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

    # -- 应用设置 ---------------------------------------------------------
    def set_language(self, value: str) -> dict[str, Any]:
        """切换界面语言并立刻写盘，网页随后会重新拉一次文案表。"""
        language = i18n.set_language(value)
        self._config.language = language
        self._persist_config()
        return self._state()

    def set_theme(self, value: str) -> dict[str, Any]:
        self._config.theme = normalize_theme(value)
        self._persist_config()
        return self._state()

    def update_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        """保存设置弹窗里除语言以外的字段。"""
        if not isinstance(patch, dict):
            return self._state()

        if "max_depth" in patch:
            self._config.max_depth = settings_module.clamp_depth(patch["max_depth"])
        if "max_entries" in patch:
            self._config.max_entries = settings_module.clamp_entries(patch["max_entries"])
        if "translate_appid" in patch:
            self._config.translate_appid = str(patch["translate_appid"] or "").strip()
        if "translate_secret" in patch:
            self._config.translate_secret = str(patch["translate_secret"] or "").strip()
        if "ai_api_key" in patch:
            self._config.ai_api_key = str(patch["ai_api_key"] or "").strip()
        if "theme" in patch:
            self._config.theme = normalize_theme(patch["theme"])

        self._persist_config()
        return self._state()

    # -- 持久化 -----------------------------------------------------------
    def save(self) -> dict[str, Any]:
        # 先归一化再校验：清理匹配字串可能把 “|||” 变成空值，
        # 这种情况必须被当成校验错误报出来。
        cleaned = 0
        for group in self._groups:
            group.name = (group.name or "").strip() or i18n.t(FALLBACK_GROUP_NAME_KEY)
            for operation in group.operations:
                before = operation.keywords
                operation.normalize()
                if operation.keywords != before:
                    cleaned += 1

        error = validate_groups(self._groups)
        if error is not None:
            group = self._groups[error.group]
            operation = group.operations[error.index]
            name = operation.display or i18n.t("manager.unnamed_operation")
            self._errors = [error.to_dict()]
            self._sel_kind, self._sel_group, self._sel_index = (
                "operation",
                error.group,
                error.index,
            )
            return self._state(
                ok=False,
                message=i18n.t(
                    "manager.invalid_field",
                    group=group.name,
                    name=name,
                    field=error.label,
                ),
            )

        try:
            settings_module.save_groups(self._groups)
        except Exception as failure:  # noqa: BLE001 - 需要把原因显示给用户
            logger.exception("保存操作列表失败")
            return self._state(
                ok=False, message=i18n.t("manager.save_failed", error=failure)
            )

        self._errors = []
        self._dirty = False
        message = (
            i18n.t("manager.saved_cleaned", count=cleaned)
            if cleaned
            else i18n.t("manager.saved")
        )
        return self._state(ok=True, message=message)

    # -- 对话框 -----------------------------------------------------------
    def browse_file(self) -> str:
        return self._pick(webview.FileDialog.OPEN)

    def browse_dir(self) -> str:
        return self._pick(webview.FileDialog.FOLDER)

    # -- 关闭 -------------------------------------------------------------
    @property
    def close_confirmed(self) -> bool:
        return self._close_confirmed

    def request_close_prompt(self) -> None:
        """请网页弹出自己的关闭确认框。

        必须从工作线程调用：``closing`` 在 UI 线程执行，在那里调用
        ``evaluate_js`` 会等同一个正在执行回调的消息循环，直接死锁。
        """
        if self._close_prompting:
            return
        self._close_prompting = True
        threading.Thread(target=self._push_close_prompt, daemon=True).start()

    def answer_close(self, action: str) -> dict[str, Any]:
        if action == "close":
            self.force_close()
        return {"ok": True}

    def force_close(self) -> None:
        self._close_confirmed = True
        if self._window is not None:
            self._window.destroy()

    # -- 内部实现 ---------------------------------------------------------
    def _persist_config(self) -> None:
        try:
            settings_module.save_app_config(self._config)
        except Exception as error:  # noqa: BLE001 - 写失败不该让界面崩掉
            logger.exception("保存应用配置失败：{}", error)

    def _push_close_prompt(self) -> None:
        shown = False
        try:
            if self._window is not None:
                shown = bool(
                    self._window.evaluate_js(
                        "window.fastrun ? window.fastrun.askUnsaved() : false"
                    )
                )
        except Exception as error:  # noqa: BLE001 - 兜底走系统对话框
            logger.warning("页面内无法显示未保存提示：{}", error)
        finally:
            self._close_prompting = False

        if not shown:
            self._native_close_prompt()

    def _native_close_prompt(self) -> None:
        """最后手段：页面已经不在了，只能退回系统对话框。"""
        choice = confirm_unsaved()
        if choice == "discard":
            self.force_close()
        elif choice == "save" and self.save().get("ok"):
            self.force_close()

    def _pick(self, dialog_type: int) -> str:
        if self._window is None:
            return ""
        try:
            result = self._window.create_file_dialog(dialog_type, allow_multiple=False)
        except Exception as error:  # noqa: BLE001 - 选择框失败不影响手输路径
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

    def _next_group_name(self) -> str:
        existing = {group.name for group in self._groups}
        prefix = i18n.t("manager.new_group")
        index = 1
        while f"{prefix} {index}" in existing:
            index += 1
        return f"{prefix} {index}"

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
                            "label": operation.display
                            or i18n.t("manager.unnamed_operation"),
                            "type": operation.type,
                            "type_label": type_label(operation.type),
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
            "types": [
                {"value": value, "label": type_label(value)} for value in TYPE_ORDER
            ],
            "debug_functions": [
                {"value": value, "label": debug_label(value)}
                for value in DEBUG_FUNCTION_VALUES
            ],
            "field_labels": {
                name: field_label(name)
                for name in ("display", "type", "keywords", "path", "dir", "url", "command")
            },
            "language": self._config.language,
            "theme": self._config.theme,
            "navigation": {
                "max_depth": self._config.max_depth,
                "max_entries": self._config.max_entries,
            },
        }
