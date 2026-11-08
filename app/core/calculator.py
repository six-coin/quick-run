"""给“计算：”这一行用的安全算术求值。

旧实现把用户输入丢进一个临时进程里 ``eval``。字符白名单确实让滥用变难了，
但本质仍是任意代码执行，而且每敲一个键都要起一个 ``multiprocessing.Pool``。

这里改成遍历抽象语法树：只允许数字常量、``+ - * / // % **`` 和一元 ``+ -``。
结果长度和指数都有上限，``9**9**9`` 会立刻报错而不是把界面卡死。
"""

from __future__ import annotations

import ast
import math
import operator
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from app import i18n
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
    """输入只由计算器允许的字符组成时返回 True。"""
    return bool(text) and all(char in CALC_CHARSET for char in text)


def needs_async(text: str) -> bool:
    """长表达式和 ``**`` 交给带超时的工作线程处理。"""
    return "**" in text or len(text) >= SYNC_MAX_LENGTH


def evaluate(expression: str) -> str:
    """求值并返回 ``str(结果)``，失败时抛 :class:`CalcError`。"""
    try:
        # ``eval`` 会忽略首尾空白，``ast.parse`` 不会，所以先 strip。
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as error:
        raise CalcError(str(error)) from error

    value = _eval_node(tree.body)

    text = str(value)
    if len(text) > MAX_RESULT_LENGTH:
        raise CalcError(i18n.t("calc.too_long"))
    return text


def evaluate_with_timeout(expression: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """与 :func:`evaluate` 相同，但受实际耗时上限约束。"""
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="calc")
    future = executor.submit(evaluate, expression)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError as error:
        raise CalcError(i18n.t("calc.timeout")) from error
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _eval_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise CalcError(i18n.t("calc.invalid_syntax"))
        return value

    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_eval_node(node.operand))

    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise CalcError(i18n.t("calc.too_large"))
        try:
            result = _BINARY_OPS[type(node.op)](left, right)
        except ZeroDivisionError as error:
            raise CalcError(i18n.t("calc.divide_by_zero")) from error
        except (OverflowError, ValueError) as error:
            raise CalcError(i18n.t("calc.too_large")) from error
        return _check_size(result)

    raise CalcError(i18n.t("calc.invalid_syntax"))


def _check_size(value: int | float) -> int | float:
    if isinstance(value, int):
        # 大致对应 MAX_RESULT_DIGITS 个十进制位，不转字符串就能算出来。
        if value.bit_length() > MAX_RESULT_DIGITS * 4:
            raise CalcError(i18n.t("calc.too_long"))
    elif math.isinf(value) or math.isnan(value):
        raise CalcError(i18n.t("calc.too_large"))
    return value
