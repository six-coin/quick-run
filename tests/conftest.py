from __future__ import annotations

import pytest

from app import i18n


@pytest.fixture(autouse=True)
def chinese_locale():
    """测试统一用中文，断言里的文案才是确定的。"""
    i18n.set_language("zh-CN")
    yield
    i18n.set_language("zh-CN")
