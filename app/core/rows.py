"""Result rows: the only thing the UI layer knows how to render."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RowKind(str, Enum):
    EXTERNAL = "external"
    SEARCH = "search"
    CALCULATE = "calculate"
    TRANSLATE = "translate"
    DEFINITION = "definition"
    EXPLORE = "explore"
    ERROR = "error"


class RowStatus(str, Enum):
    READY = "ready"
    LOADING = "loading"
    DONE = "done"
    FAILED = "failed"


@dataclass
class ResultRow:
    """A single line in the result list.

    ``payload`` is whatever the executor needs (an Operation, a NavEntry, the
    raw query...). ``value`` holds the copyable result for calculate/definition
    rows, which keeps the view free of string parsing.
    """

    key: str
    kind: RowKind
    text: str
    payload: Any = None
    status: RowStatus = RowStatus.READY
    value: str | None = None
