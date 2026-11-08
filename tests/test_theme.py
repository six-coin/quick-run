from __future__ import annotations

from app.system.theme import system_theme


def test_system_theme_returns_known_value():
    assert system_theme() in ("light", "dark")
