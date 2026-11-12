from __future__ import annotations

from app import i18n
from app.manager import api as api_module
from app.models import Operation, OperationGroup


def make_group(name: str, count: int = 0, enabled: bool = True) -> OperationGroup:
    return OperationGroup(
        name=name,
        enabled=enabled,
        operations=[
            Operation(
                display=f"{name}{index}",
                keywords=f"k{index}",
                arguments={"path": "C:/Windows/notepad.exe"},
            )
            for index in range(count)
        ],
    )


def make_api(monkeypatch, groups: list[OperationGroup]):
    config = api_module.settings_module.AppConfig()
    monkeypatch.setattr(api_module.settings_module, "load_app_config", lambda path=None: config)
    monkeypatch.setattr(api_module.settings_module, "load_groups", lambda path=None: groups)
    monkeypatch.setattr(api_module.settings_module, "save_groups", lambda *a, **k: None)
    monkeypatch.setattr(api_module.settings_module, "save_app_config", lambda *a, **k: None)
    return api_module.ManagerApi()


def test_add_operation_targets_the_explicit_group(monkeypatch):
    api = make_api(monkeypatch, [make_group("A", 2), make_group("B", 1)])

    state = api.add_operation(1)

    assert [group["count"] for group in state["groups"]] == [2, 2]
    assert state["selection"] == {"kind": "operation", "group": 1, "index": 0}


def test_add_operation_has_no_default_group_fallback(monkeypatch):
    # A group that happens to be called 默认分组 must not attract new operations.
    api = make_api(monkeypatch, [make_group("默认分组", 1), make_group("工作", 0)])

    state = api.add_operation(1)

    assert state["groups"][0]["count"] == 1
    assert state["groups"][1]["count"] == 1


def test_add_operation_with_unknown_group_is_a_noop(monkeypatch):
    api = make_api(monkeypatch, [make_group("A", 1)])

    state = api.add_operation(9)

    assert state["groups"][0]["count"] == 1
    assert state["dirty"] is False


def test_add_operation_into_disabled_group_warns(monkeypatch):
    api = make_api(monkeypatch, [make_group("A", 0, enabled=False)])

    state = api.add_operation(0)

    assert state["ok"] is True
    assert "已关闭" in state["message"]


def test_save_uses_a_neutral_name_for_an_empty_group(monkeypatch):
    api = make_api(monkeypatch, [make_group("", 0)])

    api.save()

    assert api.get_state()["groups"][0]["name"] == i18n.t(api_module.FALLBACK_GROUP_NAME_KEY)
    assert i18n.t(api_module.FALLBACK_GROUP_NAME_KEY) != i18n.t("default.group")


def test_state_does_not_advertise_a_default_group(monkeypatch):
    state = make_api(monkeypatch, [make_group("A", 1)]).get_state()

    assert "default_group_name" not in state


def test_update_settings_clamps_the_animation_duration(monkeypatch):
    api = make_api(monkeypatch, [make_group("A", 1)])

    api.update_settings({"animation_ms": 9999})
    assert api.get_settings()["animation_ms"] == api_module.settings_module.ANIMATION_RANGE[1]

    api.update_settings({"animation_ms": -1})
    assert api.get_settings()["animation_ms"] == 0

    api.update_settings({"animation_ms": 250})
    assert api.get_settings()["animation_ms"] == 250


def test_answer_close_confirm_releases_the_window(monkeypatch):
    api = make_api(monkeypatch, [make_group("A", 1)])

    api.answer_close("close")

    assert api.close_confirmed is True


def test_answer_close_cancel_keeps_editing(monkeypatch):
    api = make_api(monkeypatch, [make_group("A", 1)])

    api.answer_close("cancel")

    assert api.close_confirmed is False


class _FakeWindow:
    """只记录标题，不建真窗口。"""

    def __init__(self) -> None:
        self.titles: list[str] = []

    def set_title(self, title: str) -> None:
        self.titles.append(title)


def test_set_language_retitles_the_window(monkeypatch):
    """窗口标题要跟着界面语言走，不能停在启动时那一种。"""
    api = make_api(monkeypatch, [make_group("A", 1)])
    window = _FakeWindow()
    api.attach(window)

    api.set_language("en-US")
    api.set_language("zh-CN")

    assert window.titles == ["Quick Run Manager", "快捷运行操作管理器"]
