"""Safe arithmetic evaluation for the ``计算：`` row.

The old code called ``eval`` on user input inside a throwaway process. The
character whitelist made it hard to abuse, but it was still arbitrary code
execution and it spawned a ``multiprocessing.Pool`` on every keystroke.

This module walks the AST instead: only numeric constants, ``+ - * / // % **``
and unary ``+ -`` are allowed. Results are capped so ``9**9**9`` fails fast
instead of hanging the UI.
"""

from __future__ import annotations

import ast
import math
import operator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from app.errors import CalcError

CALC_CHARSET = frozenset("0123456789 .+-*/()")
SYNC_MAX_LENGTH = 20
DEFAULT_TIMEOUT = 2.0
MAX_RESULT_DIGITS = 1000
MAX_EXPONENT = 10_000
MAX_RESULT_LENGTH = 5000

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def looks_like_calculation(text: str) -> bool:
    """True when the query only contains calculator characters."""
    return bool(text) and all(char in CALC_CHARSET for char in text)


def needs_async(text: str) -> bool:
    """Long expressions and ``**`` used to go through the timed worker."""
    return "**" in text or len(text) >= SYNC_MAX_LENGTH


def evaluate(expression: str) -> str:
    """Evaluate and return ``str(result)``; raise :class:`CalcError` otherwise."""
    try:
        # ``eval`` ignored surrounding whitespace, ``ast.parse`` does not.
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as error:
        raise CalcError(str(error)) from error

    value = _eval_node(tree.body)

    text = str(value)
    if len(text) > MAX_RESULT_LENGTH:
        raise CalcError("结果过长")
    return text


def evaluate_with_timeout(expression: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Same as :func:`evaluate` but bounded by a wall clock timeout."""
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="calc")
    future = executor.submit(evaluate, expression)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError as error:
        raise CalcError("计算超时") from error
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _eval_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CalcError("invalid syntax")
        return value

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))

    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise CalcError("数值过大")
        try:
            result = _BINARY_OPS[type(node.op)](left, right)
        except ZeroDivisionError as error:
            raise CalcError("division by zero") from error
        except (OverflowError, ValueError) as error:
            raise CalcError("数值过大") from error
        return _check_size(result)

    raise CalcError("invalid syntax")


def _check_size(value: int | float) -> int | float:
    if isinstance(value, int):
        # Roughly MAX_RESULT_DIGITS decimal digits, computed without str().
        if value.bit_length() > MAX_RESULT_DIGITS * 4:
            raise CalcError("结果过长")
    elif math.isinf(value) or math.isnan(value):
        raise CalcError("数值过大")
    return value
