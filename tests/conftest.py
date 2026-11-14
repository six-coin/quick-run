from __future__ import annotations

import os
import tempfile
from pathlib import Path

# 在导入 app 之前把系统目录指到临时位置：paths 在导入时就会读环境变量。
_ROOT = Path(tempfile.mkdtemp(prefix="quickrun-tests-"))
os.environ.setdefault("SIXCOIN_DATA_DIR", str(_ROOT / "data"))
os.environ.setdefault("SIXCOIN_LOCAL_DIR", str(_ROOT / "local"))
os.environ.setdefault("SIXCOIN_TEMP_DIR", str(_ROOT / "temp"))

import pytest  # noqa: E402

from app import i18n  # noqa: E402


@pytest.fixture(autouse=True)
def chinese_locale():
    """测试统一用中文，断言里的文案才是确定的。"""
    i18n.set_language("zh-CN")
    yield
    i18n.set_language("zh-CN")


@pytest.fixture(autouse=True)
def fixed_defaults(monkeypatch):
    """默认语言与默认外观固定下来：首次启动的判定不能跟着开发机走。"""
    monkeypatch.setattr(i18n, "system_language", lambda: "zh-CN")
    monkeypatch.setattr("app.system.theme.system_theme", lambda: "light")
