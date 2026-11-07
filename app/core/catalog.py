"""Operation catalog: prefix matching and directory-explore lookup."""

from __future__ import annotations

from app.core.matching import normalize_alnum
from app.models import Operation, OperationType


class Catalog:
    """Read-only view over the configured operations.

    Matching rules are inherited from the old ``filter_operations``:

    * ``dir`` operations normalise both keyword and query to ``[a-z0-9]``;
    * every other type compares the raw keyword with ``startswith``;
    * keywords are separated by ``|``.
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
        """First explorable directory operation whose keyword prefixes ``token``."""
        normalized = normalize_alnum(token)
        if not normalized:
            return None
        for operation, normalized_keywords in zip(self._operations, self._normalized):
            if operation.type != OperationType.DIR or not operation.allow_explore():
                continue
            if any(keyword.startswith(normalized) for keyword in normalized_keywords):
                return operation
        return None
