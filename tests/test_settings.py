from __future__ import annotations

import json

import pytest

from app import settings
from app.errors import ConfigError
from app.models import (
    DEFAULT_GROUP_NAME,
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


# -- loading --------------------------------------------------------------
def test_load_v2_groups(tmp_path):
    target = _write(
        tmp_path,
        {
            "version": 2,
            "groups": [
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
        },
    )
    groups = settings.load_groups(target)
    assert [group.name for group in groups] == ["工作", "娱乐"]
    assert groups[1].enabled is False
    assert groups[0].operations[0].display == "A"


def test_load_v1_array_is_migrated(tmp_path):
    target = _write(
        tmp_path,
        [
            {"display": "A", "type": "file", "keywords": "a", "arguments": {"path": "x"}},
            {"display": "B", "type": "file", "keywords": "b", "arguments": {"path": "y"}},
        ],
    )
    groups = settings.load_groups(target)
    assert len(groups) == 1
    assert groups[0].name == DEFAULT_GROUP_NAME
    assert groups[0].enabled is True
    assert [operation.display for operation in groups[0].operations] == ["A", "B"]


def test_missing_file_creates_one_default_group(tmp_path):
    target = tmp_path / "nested" / "operations.json"
    groups = settings.load_groups(target)
    assert len(groups) == 1
    assert groups[0].name == DEFAULT_GROUP_NAME
    assert len(groups[0].operations) >= 5
    assert target.exists()


def test_invalid_json_is_reported(tmp_path):
    target = tmp_path / "operations.json"
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        settings.load_groups(target)


def test_empty_group_list_is_rejected(tmp_path):
    with pytest.raises(ConfigError):
        settings.load_groups(_write(tmp_path, {"version": 2, "groups": []}))


def test_missing_operation_key_is_rejected(tmp_path):
    target = _write(
        tmp_path,
        {"groups": [{"name": "G", "operations": [{"display": "A", "type": "file"}]}]},
    )
    with pytest.raises(ConfigError):
        settings.load_groups(target)


# -- ordering -------------------------------------------------------------
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


# -- saving ---------------------------------------------------------------
def test_save_roundtrip(tmp_path):
    target = tmp_path / "operations.json"
    groups = [
        OperationGroup(name="工作", enabled=True, operations=[_operation("A")]),
        OperationGroup(name="娱乐", enabled=False, operations=[_operation("B")]),
    ]
    settings.save_groups(groups, target)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert [group["name"] for group in payload["groups"]] == ["工作", "娱乐"]
    assert payload["groups"][1]["enabled"] is False
    assert set(payload["groups"][0]["operations"][0]) == {
        "display",
        "type",
        "keywords",
        "arguments",
    }

    reloaded = settings.load_groups(target)
    assert [operation.display for operation in flatten_groups(reloaded)] == ["A"]


def test_empty_group_name_falls_back(tmp_path):
    target = tmp_path / "operations.json"
    groups = [OperationGroup(name="   ", enabled=True, operations=[_operation("A")])]
    settings.save_groups(groups, target)
    assert settings.load_groups(target)[0].name == DEFAULT_GROUP_NAME


# -- normalisation & validation -------------------------------------------
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


# -- optional services ----------------------------------------------------
def test_translate_requires_credentials(tmp_path):
    target = tmp_path / "translate.json"
    assert settings.load_translate(target) is None

    target.write_text(json.dumps({"appid": "a", "secret_key": "b"}), encoding="utf-8")
    config = settings.load_translate(target)
    assert config is not None
    assert config.appid == "a"


def test_ai_key_defaults_to_empty(tmp_path):
    assert settings.load_ai_key(tmp_path / "ai.json") == ""


# -- keyword sanitising ---------------------------------------------------
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
