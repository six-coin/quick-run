from __future__ import annotations

import json

import pytest

from app import i18n, settings
from app.errors import ConfigError
from app.models import (
    FieldError,
    Operation,
    OperationGroup,
    flatten_groups,
    validate_groups,
)


def _write(tmp_path, payload):
    target = tmp_path / "operations.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target


def _operation(display: str, keywords: str = "k", **arguments):
    return Operation(
        display=display,
        type="file",
        keywords=keywords,
        arguments={"path": arguments.get("path", "p"), "no_window": False},
    )


# -- 操作列表：根层就是分组数组 -------------------------------------------
def test_load_groups_from_root_array(tmp_path):
    target = _write(
        tmp_path,
        [
            {
                "name": "工作",
                "enabled": True,
                "operations": [
                    {
                        "display": "A",
                        "type": "file",
                        "keywords": "a",
                        "arguments": {"path": "x"},
                    }
                ],
            },
            {
                "name": "娱乐",
                "enabled": False,
                "operations": [
                    {
                        "display": "B",
                        "type": "dir",
                        "keywords": "b",
                        "arguments": {"dir": "y"},
                    }
                ],
            },
        ],
    )
    groups = settings.load_groups(target)
    assert [group.name for group in groups] == ["工作", "娱乐"]
    assert groups[1].enabled is False
    assert groups[0].operations[0].display == "A"


def test_missing_file_creates_one_default_group(tmp_path):
    target = tmp_path / "nested" / "operations.json"
    groups = settings.load_groups(target)
    assert len(groups) == 1
    assert groups[0].name == i18n.t("default.group")
    assert len(groups[0].operations) >= 5
    assert target.exists()
    assert isinstance(json.loads(target.read_text(encoding="utf-8")), list)


def test_invalid_json_is_reported(tmp_path):
    target = tmp_path / "operations.json"
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        settings.load_groups(target)


def test_object_root_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        settings.load_groups(_write(tmp_path, {"groups": []}))


def test_empty_group_list_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        settings.load_groups(_write(tmp_path, []))


def test_missing_operation_key_is_rejected(tmp_path):
    target = _write(
        tmp_path,
        [{"name": "G", "operations": [{"display": "A", "type": "file"}]}],
    )
    with pytest.raises(ConfigError):
        settings.load_groups(target)


# -- 顺序 ---------------------------------------------------------------
def test_flatten_keeps_group_order_and_skips_disabled():
    groups = [
        OperationGroup(name="一", enabled=True, operations=[_operation("A"), _operation("B")]),
        OperationGroup(name="二", enabled=False, operations=[_operation("C")]),
        OperationGroup(name="三", enabled=True, operations=[_operation("D")]),
    ]
    assert [operation.display for operation in flatten_groups(groups)] == ["A", "B", "D"]
    assert [operation.display for operation in flatten_groups(groups, enabled_only=False)] == [
        "A",
        "B",
        "C",
        "D",
    ]


# -- 保存 ---------------------------------------------------------------
def test_save_writes_a_bare_array(tmp_path):
    target = tmp_path / "operations.json"
    groups = [
        OperationGroup(name="工作", enabled=True, operations=[_operation("A")]),
        OperationGroup(name="娱乐", enabled=False, operations=[_operation("B")]),
    ]
    settings.save_groups(groups, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert [group["name"] for group in payload] == ["工作", "娱乐"]
    assert payload[1]["enabled"] is False
    assert set(payload[0]["operations"][0]) == {
        "display",
        "type",
        "keywords",
        "arguments",
    }

    reloaded = settings.load_groups(target)
    assert [operation.display for operation in flatten_groups(reloaded)] == ["A"]


def test_empty_group_name_falls_back_on_load(tmp_path):
    target = tmp_path / "operations.json"
    groups = [OperationGroup(name="   ", enabled=True, operations=[_operation("A")])]
    settings.save_groups(groups, target)
    assert settings.load_groups(target)[0].name == i18n.t("manager.unnamed_group")


# -- 应用配置 -------------------------------------------------------------
def test_app_config_is_created_with_system_theme(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "system_theme", lambda: "dark")
    target = tmp_path / "app.json"

    config = settings.load_app_config(target)

    assert config.theme == "dark"
    assert target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["theme"] == "dark"
    assert payload["language"] == "zh-CN"
    assert payload["navigation"] == {"max_depth": 5, "max_entries": 100}


def test_app_config_roundtrip(tmp_path):
    target = tmp_path / "app.json"
    config = settings.AppConfig(
        language="en-US",
        theme="dark",
        max_depth=3,
        max_entries=50,
        translate_appid="id",
        translate_secret="key",
        ai_api_key="token",
    )
    settings.save_app_config(config, target)

    loaded = settings.load_app_config(target)
    assert loaded == config
    assert loaded.translate is not None
    assert loaded.translate.appid == "id"


def test_app_config_clamps_out_of_range_values(tmp_path):
    target = tmp_path / "app.json"
    target.write_text(
        json.dumps(
            {
                "language": "fr",
                "theme": "neon",
                "navigation": {"max_depth": 99, "max_entries": 0},
            }
        ),
        encoding="utf-8",
    )

    config = settings.load_app_config(target)

    assert config.language == "zh-CN"
    assert config.theme == "light"
    assert config.max_depth == 5
    assert config.max_entries == 1


def test_animation_duration_is_clamped(tmp_path):
    target = tmp_path / "app.json"

    target.write_text(json.dumps({"animation_ms": 9999}), encoding="utf-8")
    assert settings.load_app_config(target).animation_ms == settings.ANIMATION_RANGE[1]

    target.write_text(json.dumps({"animation_ms": -5}), encoding="utf-8")
    assert settings.load_app_config(target).animation_ms == 0

    target.write_text(json.dumps({"animation_ms": "abc"}), encoding="utf-8")
    assert settings.load_app_config(target).animation_ms == settings.DEFAULT_ANIMATION_MS

    # 缺这个键的老配置也要能读，落到默认值。
    target.write_text(json.dumps({"language": "zh-CN"}), encoding="utf-8")
    assert settings.load_app_config(target).animation_ms == settings.DEFAULT_ANIMATION_MS


def test_translate_requires_both_fields():
    assert settings.AppConfig(translate_appid="a").translate is None
    assert settings.AppConfig(translate_secret="b").translate is None
    assert settings.AppConfig(translate_appid="a", translate_secret="b").translate is not None


# -- 归一化与校验 ---------------------------------------------------------
def test_normalize_paths_and_depth():
    operation = Operation(
        display="  A  ",
        type="file",
        arguments={"path": ' "C:/a/b" ', "no_window": 0},
        keywords=" k ",
    )
    operation.normalize()
    assert operation.display == "A"
    assert operation.keywords == "k"
    assert operation.arguments["path"] == r"C:\a\b"
    assert operation.arguments["no_window"] is False

    folder = Operation(
        type="dir",
        arguments={"dir": "D:/x", "allow_explore": True, "explore_depth": "9"},
        keywords="d",
    )
    folder.normalize()
    assert folder.arguments["dir"] == r"D:\x"
    assert folder.arguments["explore_depth"] == 5


def test_validation_reports_group_and_index():
    groups = [
        OperationGroup(name="一", operations=[_operation("A")]),
        OperationGroup(name="二", operations=[Operation(display="", keywords="k")]),
    ]
    assert validate_groups(groups) == FieldError(1, 0, "display")

    groups = [OperationGroup(name="一", operations=[_operation("A", keywords="")])]
    assert validate_groups(groups) == FieldError(0, 0, "keywords")

    groups = [
        OperationGroup(
            name="一",
            operations=[Operation(display="A", keywords="k", arguments={"path": ""})],
        )
    ]
    assert validate_groups(groups) == FieldError(0, 0, "path")


def test_change_type_carries_path():
    operation = Operation(
        type="dir",
        arguments={"dir": r"C:\x", "allow_explore": False, "explore_depth": 1},
        keywords="d",
    )
    operation.change_type("file")
    assert operation.type == "file"
    assert operation.arguments["path"] == r"C:\x"

    operation.change_type("dir")
    assert operation.arguments["dir"] == r"C:\x"


# -- 匹配字串清理 ---------------------------------------------------------
def test_sanitize_keywords():
    from app.models import sanitize_keywords

    assert sanitize_keywords("A|B") == "a|b"
    assert sanitize_keywords("a||b|") == "a|b"
    assert sanitize_keywords("|||") == ""
    assert sanitize_keywords("sys:restart|restart") == "sysrestart|restart"
    assert sanitize_keywords("a|a|b") == "a|b"
    assert sanitize_keywords("  hello  world ") == "helloworld"


def test_keywords_of_only_pipes_counts_as_empty():
    operation = Operation(display="A", keywords="|||", arguments={"path": "p"})
    groups = [OperationGroup(name="G", operations=[operation])]
    assert validate_groups(groups) == FieldError(0, 0, "keywords")


def test_normalize_cleans_keywords():
    operation = Operation(display="A", keywords="X||Y|", arguments={"path": "p"})
    operation.normalize()
    assert operation.keywords == "x|y"


# -- 默认配置模板 ---------------------------------------------------------
def test_default_operations_template():
    operations = settings.default_operations()

    assert [item["keywords"] for item in operations] == [
        "manager",
        "folder",
        "startup",
        "restart",
        "close",
    ]

    manager = operations[0]
    assert manager["type"] == "file"
    assert manager["arguments"] == {"path": "manager.bat", "no_window": True}

    program_folder = operations[1]
    assert program_folder["type"] == "dir"
    assert program_folder["arguments"] == {
        "dir": ".",
        "allow_explore": False,
        "explore_depth": 0,
    }

    assert operations[3]["arguments"] == {"function": "restart"}
    assert operations[4]["arguments"] == {"function": "close"}


def test_generated_operations_use_localized_names(tmp_path):
    target = tmp_path / "operations.json"

    settings.load_groups(target)

    data = json.loads(target.read_text(encoding="utf-8"))
    # 断言的是「生成时用的是文案而不是键名」，所以和语言包比对，不写死具体文字。
    assert data[0]["name"] == i18n.t("default.group")
    assert data[0]["operations"][0]["display"] == i18n.t("default.manager")
