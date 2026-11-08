"""操作目录：前缀匹配与文件夹浏览用的查找。"""

from __future__ import annotations

from app.core.matching import normalize_alnum
from app.models import Operation, OperationType


class Catalog:
    """已配置操作之上的只读视图。

    匹配规则：

    * ``dir`` 类型会把关键词和查询都压成 ``[a-z0-9]`` 再比；
    * 其他类型直接用原始关键词做 ``startswith``；
    * 多个关键词用 ``|`` 分隔。
    """

    def __init__(self, operations: list[Operation]) -> None:
        self._operations = list(operations)
        self._normalized: list[list[str]] = [
            [normalize_alnum(keyword) for keyword in operation.keyword_list()]
            for operation in self._operations
        ]

    @property
    def operations(self) -> list[Operation]:
        return self._operations

    def match(self, query: str) -> list[Operation]:
        if not query:
            return []

        lowered = query.lower()
        normalized = normalize_alnum(query)
        matched: list[Operation] = []

        for operation, normalized_keywords in zip(self._operations, self._normalized):
            if operation.type == OperationType.DIR:
                if not normalized:
                    continue
                if any(keyword.startswith(normalized) for keyword in normalized_keywords):
                    matched.append(operation)
            else:
                if any(
                    keyword.startswith(lowered) for keyword in operation.keyword_list()
                ):
                    matched.append(operation)
        return matched

    def explore_operation(self, token: str) -> Operation | None:
        """第一个关键词能前缀匹配 ``token`` 且允许浏览的文件夹操作。"""
        normalized = normalize_alnum(token)
        if not normalized:
            return None
        for operation, normalized_keywords in zip(self._operations, self._normalized):
            if operation.type != OperationType.DIR or not operation.allow_explore():
                continue
            if any(keyword.startswith(normalized) for keyword in normalized_keywords):
                return operation
        return None
