"""Domain exceptions.

Keeping them in one module lets the UI layers catch a single base class while
the core stays free of presentation concerns.
"""

from __future__ import annotations


class FastRunError(Exception):
    """Base class for every error raised by this application."""


class ConfigError(FastRunError):
    """The config file is missing, unreadable or structurally invalid."""


class ValidationError(FastRunError):
    """An operation failed validation before saving."""

    def __init__(self, index: int, field: str, message: str = "") -> None:
        super().__init__(message or f"第 {index + 1} 条操作的 {field} 字段不合法")
        self.index = index
        self.field = field
        self.message = message


class CalcError(FastRunError):
    """The expression could not be evaluated (syntax, overflow, timeout)."""


class ServiceError(FastRunError):
    """A remote service (translate / definition / speech) failed."""


class ActionError(FastRunError):
    """An action could not be performed (missing file, spawn failure)."""
