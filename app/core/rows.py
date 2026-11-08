"""结果行：界面层唯一需要认识的数据结构。"""

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
    """结果列表里的一行。

    ``payload`` 放执行器需要的东西（一个 Operation、一个 NavEntry、原始查询……）。
    ``value`` 保存计算和查词的可复制结果，这样界面层不用再去解析字符串。
    """

    key: str
    kind: RowKind
    text: str
    payload: Any = None
    status: RowStatus = RowStatus.READY
    value: str | None = None
