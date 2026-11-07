from __future__ import annotations

import pytest

from app.core import calculator
from app.errors import CalcError


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1+2*3", "7"),
        ("(1+2)*3", "9"),
        ("2**10", "1024"),
        ("7//2", "3"),
        ("7%2", "1"),
        ("1/3", "0.3333333333333333"),
        ("-5+2", "-3"),
        (" 4 ", "4"),
    ],
)
def test_evaluate(expression, expected):
    assert calculator.evaluate(expression) == expected


def test_division_by_zero():
    with pytest.raises(CalcError):
        calculator.evaluate("1/0")


def test_invalid_syntax():
    with pytest.raises(CalcError):
        calculator.evaluate("1+")


def test_huge_exponent_is_rejected():
    with pytest.raises(CalcError):
        calculator.evaluate("9**9**9")


def test_arbitrary_code_is_rejected():
    with pytest.raises(CalcError):
        calculator.evaluate("__import__('os')")


def test_looks_like_calculation():
    assert calculator.looks_like_calculation("1+2")
    assert not calculator.looks_like_calculation("")
    assert not calculator.looks_like_calculation("1+2a")


def test_needs_async():
    assert calculator.needs_async("2**10")
    assert calculator.needs_async("1" * 20)
    assert not calculator.needs_async("1+1")


def test_evaluate_with_timeout():
    assert calculator.evaluate_with_timeout("1+1") == "2"
