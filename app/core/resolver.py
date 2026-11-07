"""Query -> result rows.

This is the state machine that used to live inside ``SearchWindow.filter_operations``.
It is deliberately pure: given a query it returns the rows to show plus the
asynchronous requests that should be scheduled. The precedence is unchanged:

    1. empty query            -> nothing
    2. query ending with `    -> internal rows only
    3. contains a space       -> directory navigation if the head matches
    4. any operation matches  -> those operations
    5. otherwise              -> search / calculate / definition / translate
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app import paths
from app.core import calculator
from app.core.catalog import Catalog
from app.core.navigation import ERR_BAD_INDEX, DirectoryNavigator, NavEntry
from app.core.rows import ResultRow, RowKind, RowStatus
from app.errors import CalcError
from app.models import Operation, OperationType

LIVE_TRANSLATE_MAX_LENGTH = 30
CALC_DEBOUNCE_MS = 50
TRANSLATE_DEBOUNCE_MS = 500


def parse_index(text: str) -> tuple[str, int] | None:
    """Split ``keyword#3`` into ``("keyword", 3)``.

    Returns ``None`` when the suffix is missing, not a positive number, or has
    no keyword in front of it -- so a lone ``#`` is simply ignored.
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
        # A query of only whitespace is "nothing typed": it used to fall into
        # the calculator (space is a valid calculator character) and show a
        # syntax error.
        if not text.strip():
            return Resolution()

        stripped = text.strip()
        if stripped.endswith("`"):
            return self._internal(stripped[:-1].strip())

        if " " in text:
            head, _, nav_text = text.partition(" ")
            operation = self._explore_target(head)
            raw_root = str(operation.arguments.get("dir", "")).strip() if operation else ""
            if operation is not None and raw_root:
                root = paths.resolve_user_path(raw_root)
                if self._navigator.can_explore(root):
                    result = self._navigator.navigate(
                        root, nav_text, operation.explore_depth()
                    )
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
                return Resolution(
                    [self._external_row(operation) for operation in matched]
                )
            return self._internal(text)

        # Outside folder navigation, ``keyword#n`` picks the n-th match so it
        # can be executed directly with Enter.
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
        """Directory operation addressed by the token before the first space.

        ``play#2`` addresses the second match explicitly; a bare token keeps the
        old prefix behaviour.
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

    # -- internal rows ----------------------------------------------------
    def _internal(self, text: str) -> Resolution:
        rows = [self._row(RowKind.SEARCH, f"搜索：{text}", payload=text)]
        pending: list[PendingRequest] = []

        if calculator.looks_like_calculation(text):
            row = self._row(RowKind.CALCULATE, "", payload=text)
            if calculator.needs_async(text):
                row.status = RowStatus.LOADING
                row.text = "计算：计算中..."
                pending.append(
                    PendingRequest(row.key, RowKind.CALCULATE, text, CALC_DEBOUNCE_MS)
                )
            else:
                try:
                    row.value = calculator.evaluate(text)
                    row.status = RowStatus.DONE
                    row.text = f"计算：{row.value}"
                except CalcError as error:
                    row.value = str(error)
                    row.status = RowStatus.FAILED
                    row.text = f"计算：{error}"
            rows.insert(0, row)
            return Resolution(rows, pending)

        if self._ai_api_key:
            rows.append(
                self._row(
                    RowKind.DEFINITION,
                    f"查词：{text}（回车或双击开始查词）",
                    payload=text,
                )
            )

        if self._translate_enabled and len(text) < LIVE_TRANSLATE_MAX_LENGTH:
            row = self._row(
                RowKind.TRANSLATE, "翻译：等待中...", payload=text, status=RowStatus.LOADING
            )
            rows.append(row)
            pending.append(
                PendingRequest(row.key, RowKind.TRANSLATE, text, TRANSLATE_DEBOUNCE_MS)
            )
        else:
            rows.append(self._row(RowKind.TRANSLATE, f"翻译：{text}", payload=text))

        return Resolution(rows, pending)

    # -- row factories ----------------------------------------------------
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
        prefix = "文件夹：" if entry.is_dir else "文件："
        return self._row(
            RowKind.EXPLORE, f"[{index}] {prefix}{entry.name}", payload=entry
        )

    def _error_row(self, message: str) -> ResultRow:
        return self._row(RowKind.ERROR, f"错误：{message}", payload=message)
