from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import i18n  # noqa: E402


@pytest.fixture(autouse=True)
def chinese_locale():
    """测试统一用中文，断言里的文案才是确定的。"""
    i18n.set_language("zh")
    yield
    i18n.set_language("zh")
