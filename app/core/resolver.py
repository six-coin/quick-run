"""把输入框里的文字变成结果行。

纯函数式的模块：给一段查询，返回要显示的行和需要异步发起的请求。优先级：

    1. 空查询              -> 什么都不显示
    2. 以 ` 结尾           -> 只看内置功能（搜索 / 计算 / 查词 / 翻译）
    3. 含有空格            -> 命中文件夹操作时进入目录浏览
    4. 命中任意操作        -> 显示这些操作
    5. 其他情况            -> 搜索 / 计算 / 查词 / 翻译
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app import i18n, paths
from app.core import calculator
from app.core.catalog import Catalog
from app.core.navigation import ERR_BAD_INDEX, DirectoryNavigator, NavEntry
from app.core.rows import ResultRow, RowKind, RowStatus
from app.errors import CalcError
from app.models import Operation, OperationType

#: 超过这个长度就不做实时翻译，避免又长又慢的请求。
LIVE_TRANSLATE_MAX_LENGTH = 30

CALC_DEBOUNCE_MS = 50
TRANSLATE_DEBOUNCE_MS = 500


def parse_index(text: str) -> tuple[str, int] | None:
    """把 ``关键词#3`` 拆成 ``("关键词", 3)``。

    后缀缺失、不是正整数，或者 ``#`` 前面没有关键词时返回 ``None``，
    所以单独一个 ``#`` 会被自然忽略。
    """
    if "#" not in text:
        return None
    base, _, raw_number = text.rpartition("#")
    base = base.strip()
    if not base or not raw_number.isdigit():
        return None
    number = int(raw_number)
    if number < 1:
        return None
    return base, number


@dataclass(frozen=True)
class PendingRequest:
    """一条需要延迟发起的异步请求（计算或翻译）。"""

    key: str
    kind: RowKind
    payload: Any
    delay_ms: int


@dataclass
class Resolution:
    rows: list[ResultRow] = field(default_factory=list)
    pending: list[PendingRequest] = field(default_factory=list)


class QueryResolver:
    def __init__(
        self,
        catalog: Catalog,
        navigator: DirectoryNavigator,
        ai_api_key: str = "",
        translate_enabled: bool = False,
    ) -> None:
        self._catalog = catalog
        self._navigator = navigator
        self._ai_api_key = ai_api_key
        self._translate_enabled = translate_enabled

    def resolve(self, query: str) -> Resolution:
        text = (query or "").replace("\n", " ")
        # 全是空白等于“什么都没输入”。空格本身是计算器的合法字符，不拦的话
        # 会掉进计算分支报语法错误。
        if not text.strip():
            return Resolution()

        stripped = text.strip()
        if stripped.endswith("`"):
            return self._internal(stripped[:-1].strip())

        # 结尾的 “#” 是 “关键词#2” 的中间状态，先忽略它，
        # 免得一边输数字结果列表一边跳。
        if len(text) > 1 and text.endswith("#"):
            return self.resolve(text[:-1])

        if " " in text:
            head, _, nav_text = text.partition(" ")
            operation = self._explore_target(head)
            raw_root = str(operation.arguments.get("dir", "")).strip() if operation else ""
            if operation is not None and raw_root:
                root = paths.resolve_user_path(raw_root)
                if self._navigator.can_explore(root):
                    result = self._navigator.navigate(root, nav_text, operation.explore_depth())
                    if result.error:
                        return Resolution([self._error_row(result.error)])
                    return Resolution(
                        [
                            self._explore_row(entry, index)
                            for index, entry in enumerate(result.entries, start=1)
                        ]
                    )

            matched = self._catalog.match(text)
            if matched:
                return Resolution([self._external_row(operation) for operation in matched])
            return self._internal(text)

        # 不在文件夹浏览状态时，``关键词#n`` 直接选出第 n 个匹配项，
        # 这样按一次回车就能执行。
        indexed = parse_index(text)
        if indexed is not None:
            base, number = indexed
            matches = self._catalog.match(base)
            if matches:
                if number > len(matches):
                    return Resolution([self._error_row(ERR_BAD_INDEX)])
                return Resolution([self._external_row(matches[number - 1])])

        matched = self._catalog.match(text)
        if matched:
            return Resolution([self._external_row(operation) for operation in matched])

        return self._internal(text)

    def _explore_target(self, head: str) -> Operation | None:
        """第一个空格前的词指向的文件夹操作。

        ``play#2`` 显式指定第 2 个匹配项；不带序号时用前缀匹配。
        """
        indexed = parse_index(head)
        if indexed is None:
            return self._catalog.explore_operation(head)

        base, number = indexed
        matches = self._catalog.match(base)
        if not 0 < number <= len(matches):
            return None
        candidate = matches[number - 1]
        if candidate.type == OperationType.DIR and candidate.allow_explore():
            return candidate
        return None

    # -- 内置功能 ---------------------------------------------------------
    def _internal(self, text: str) -> Resolution:
        rows = [self._row(RowKind.SEARCH, i18n.t("launcher.search", text=text), payload=text)]
        pending: list[PendingRequest] = []

        if calculator.looks_like_calculation(text):
            row = self._row(RowKind.CALCULATE, "", payload=text)
            if calculator.needs_async(text):
                row.status = RowStatus.LOADING
                row.text = i18n.t("launcher.calculating")
                pending.append(PendingRequest(row.key, RowKind.CALCULATE, text, CALC_DEBOUNCE_MS))
            else:
                try:
                    row.value = calculator.evaluate(text)
                    row.status = RowStatus.DONE
                    row.text = i18n.t("launcher.calculate", text=row.value)
                except CalcError as error:
                    row.value = str(error)
                    row.status = RowStatus.FAILED
                    row.text = i18n.t("launcher.calculate", text=error)
            rows.insert(0, row)
            return Resolution(rows, pending)

        if self._ai_api_key:
            rows.append(
                self._row(
                    RowKind.DEFINITION,
                    i18n.t("launcher.definition", text=text),
                    payload=text,
                )
            )

        if self._translate_enabled and len(text) < LIVE_TRANSLATE_MAX_LENGTH:
            row = self._row(
                RowKind.TRANSLATE,
                i18n.t("launcher.translate_waiting"),
                payload=text,
                status=RowStatus.LOADING,
            )
            rows.append(row)
            pending.append(PendingRequest(row.key, RowKind.TRANSLATE, text, TRANSLATE_DEBOUNCE_MS))
        else:
            rows.append(
                self._row(RowKind.TRANSLATE, i18n.t("launcher.translate", text=text), payload=text)
            )

        return Resolution(rows, pending)

    # -- 行工厂 -----------------------------------------------------------
    @staticmethod
    def _row(
        kind: RowKind,
        text: str,
        payload: Any = None,
        status: RowStatus = RowStatus.READY,
    ) -> ResultRow:
        return ResultRow(key=uuid.uuid4().hex, kind=kind, text=text, payload=payload, status=status)

    def _external_row(self, operation) -> ResultRow:
        return self._row(RowKind.EXTERNAL, operation.display, payload=operation)

    def _explore_row(self, entry: NavEntry, index: int) -> ResultRow:
        key = "launcher.folder" if entry.is_dir else "launcher.file"
        return self._row(
            RowKind.EXPLORE, f"[{index}] {i18n.t(key, name=entry.name)}", payload=entry
        )

    def _error_row(self, message_key: str) -> ResultRow:
        message = i18n.t(message_key)
        return self._row(RowKind.ERROR, i18n.t("launcher.error", message=message), payload=message)
