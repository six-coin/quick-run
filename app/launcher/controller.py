"""Launcher interaction state machine.

Owns everything that is not pixels: the current query, the result rows, the
selection window, the input history and the debounce/async plumbing. The window
only renders what this object emits, which is what keeps the two layers
decoupled (the old code had operations mutating widgets directly).
"""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal

from app.core import calculator
from app.core.actions import ActionExecutor, Modifiers
from app.core.resolver import PendingRequest, QueryResolver
from app.core.rows import ResultRow, RowKind, RowStatus
from app.errors import CalcError
from app.launcher.tasks import TaskRunner

VISIBLE_ROWS = 5


class LauncherController(QObject):
    #: rows, selected index, index of the first visible row
    rows_changed = Signal(list, int, int)
    #: index in ``rows``, new text
    row_updated = Signal(int, str)
    hide_requested = Signal()
    history_text = Signal(str)

    def __init__(
        self,
        resolver: QueryResolver,
        executor: ActionExecutor,
        clipboard,
        translator=None,
        definition=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._resolver = resolver
        self._executor = executor
        self._clipboard = clipboard
        self._translator = translator
        self._definition = definition

        self._rows: list[ResultRow] = []
        self._selected = 0
        self._visible_start = 0
        self._query = ""
        self._generation = 0

        self._history: list[str] = []
        self._history_pos = 0
        self._history_last = 0

        self._pending: dict[RowKind, PendingRequest] = {}
        self._calc_timer = QTimer(self)
        self._calc_timer.setSingleShot(True)
        self._calc_timer.timeout.connect(lambda: self._fire_pending(RowKind.CALCULATE))
        self._translate_timer = QTimer(self)
        self._translate_timer.setSingleShot(True)
        self._translate_timer.timeout.connect(lambda: self._fire_pending(RowKind.TRANSLATE))

        self._tasks = TaskRunner(self)
        self._tasks.finished.connect(self._on_task_done)

    # -- session ----------------------------------------------------------
    def begin_session(self) -> None:
        self._history = [entry for entry in self._history if entry]
        self._history.append("")
        self._history_last = len(self._history) - 1
        self._history_pos = self._history_last

    def end_session(self) -> None:
        if self._history:
            self._history[-1] = self._query
        self._cancel_pending()
        self._generation += 1

    # -- query ------------------------------------------------------------
    def set_query(self, text: str) -> None:
        text = (text or "").replace("\n", " ")
        self._query = text

        if self._history and self._history_pos == self._history_last:
            self._history[-1] = text

        self._cancel_pending()
        self._generation += 1

        if not text:
            self._rows = []
            self._selected = 0
            self._visible_start = 0
            self.rows_changed.emit([], -1, 0)
            return

        resolution = self._resolver.resolve(text)
        self._rows = resolution.rows
        self._selected = 0
        self._visible_start = 0
        self.rows_changed.emit(self._rows, 0, 0)

        for pending in resolution.pending:
            self._schedule(pending)

    def history_move(self, delta: int) -> None:
        if not self._history:
            return
        if delta < 0 and self._history_pos > 0:
            self._history_pos -= 1
        elif delta > 0 and self._history_pos < self._history_last:
            self._history_pos += 1
        else:
            return
        self.history_text.emit(self._history[self._history_pos])

    # -- selection --------------------------------------------------------
    def move_selection(self, delta: int) -> None:
        if not self._rows:
            return
        target = self._selected + delta
        if not 0 <= target < len(self._rows):
            return

        self._selected = target
        if self._selected < self._visible_start:
            self._visible_start = self._selected
        elif self._selected >= self._visible_start + VISIBLE_ROWS:
            self._visible_start = self._selected - VISIBLE_ROWS + 1
        self.rows_changed.emit(self._rows, self._selected, self._visible_start)

    def select(self, index: int) -> None:
        if 0 <= index < len(self._rows):
            self._selected = index
            self.rows_changed.emit(self._rows, self._selected, self._visible_start)

    # -- activation -------------------------------------------------------
    def activate(self, modifiers: Modifiers | None = None) -> None:
        if not self._rows:
            return
        modifiers = modifiers or Modifiers()
        row = self._rows[self._selected]

        if row.kind is RowKind.DEFINITION and row.status in (RowStatus.READY, RowStatus.FAILED):
            self._start_definition(row)
            logger.info("操作成功执行：查词")
            return

        if row.kind is RowKind.CALCULATE and row.status is not RowStatus.DONE:
            return

        hide_first = row.kind in (
            RowKind.EXTERNAL,
            RowKind.SEARCH,
            RowKind.TRANSLATE,
            RowKind.EXPLORE,
            RowKind.ERROR,
        )
        if hide_first:
            # Hide before launching so the new window ends up in front.
            self.hide_requested.emit()
            self._cancel_pending()
            self._generation += 1

        outcome = self._executor.execute(row, modifiers)

        if outcome.clipboard_text is not None:
            self._clipboard.copy(outcome.clipboard_text)

        if outcome.hide and not hide_first:
            self.hide_requested.emit()
            self._cancel_pending()
            self._generation += 1

    # -- async ------------------------------------------------------------
    def _schedule(self, pending: PendingRequest) -> None:
        if pending.kind is RowKind.CALCULATE:
            self._pending[RowKind.CALCULATE] = pending
            self._calc_timer.start(pending.delay_ms)
        elif pending.kind is RowKind.TRANSLATE:
            self._pending[RowKind.TRANSLATE] = pending
            self._translate_timer.start(pending.delay_ms)

    def _fire_pending(self, kind: RowKind) -> None:
        pending = self._pending.pop(kind, None)
        if pending is None:
            return
        found = self._find(pending.key)
        if found is None:
            return
        _, row = found
        if kind is RowKind.CALCULATE:
            self._start_calculate(row)
        elif kind is RowKind.TRANSLATE:
            self._start_translate(row)

    def _start_calculate(self, row: ResultRow) -> None:
        expression = str(row.payload)
        generation = self._generation
        self._tasks.submit(
            row.key,
            generation,
            lambda: calculator.evaluate_with_timeout(expression),
        )

    def _start_translate(self, row: ResultRow) -> None:
        if self._translator is None:
            return
        row.status = RowStatus.LOADING
        row.text = "翻译：加载中..."
        self._emit_row(row)
        text = str(row.payload)
        generation = self._generation
        self._tasks.submit(row.key, generation, lambda: self._translator.translate(text))

    def _start_definition(self, row: ResultRow) -> None:
        if self._definition is None:
            return
        row.status = RowStatus.LOADING
        row.text = "查词：加载中..."
        self._emit_row(row)
        text = str(row.payload)
        generation = self._generation
        self._tasks.submit(row.key, generation, lambda: self._definition.lookup(text))

    def _on_task_done(self, key: str, generation: int, ok: bool, payload: object) -> None:
        if generation != self._generation:
            return
        found = self._find(key)
        if found is None:
            return

        index, row = found
        if ok:
            row.value = str(payload)
            row.status = RowStatus.DONE
            row.text = self._format_success(row.kind, row.value)
        else:
            row.status = RowStatus.FAILED
            row.text = self._format_error(row.kind, payload)

        self.row_updated.emit(index, row.text)

    # -- helpers ----------------------------------------------------------
    def _find(self, key: str) -> tuple[int, ResultRow] | None:
        for index, row in enumerate(self._rows):
            if row.key == key:
                return index, row
        return None

    def _emit_row(self, row: ResultRow) -> None:
        found = self._find(row.key)
        if found is not None:
            self.row_updated.emit(found[0], row.text)

    def _cancel_pending(self) -> None:
        self._calc_timer.stop()
        self._translate_timer.stop()
        self._pending.clear()

    @staticmethod
    def _format_success(kind: RowKind, value: str) -> str:
        if kind is RowKind.CALCULATE:
            return f"计算：{value}"
        if kind is RowKind.TRANSLATE:
            return f"翻译：{value}"
        if kind is RowKind.DEFINITION:
            return f"查词：{value}"
        return value

    @staticmethod
    def _format_error(kind: RowKind, payload: object) -> str:
        if kind is RowKind.CALCULATE:
            if isinstance(payload, CalcError):
                return f"计算：{payload}"
            return f"计算：发生错误：{payload}"
        if kind is RowKind.TRANSLATE:
            return f"翻译：{payload}"
        if kind is RowKind.DEFINITION:
            return f"查词：{payload}"
        return str(payload)

    # -- read only --------------------------------------------------------
    @property
    def query(self) -> str:
        return self._query

    @property
    def rows(self) -> list[ResultRow]:
        return self._rows
