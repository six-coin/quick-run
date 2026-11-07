from __future__ import annotations

from pathlib import Path

from app.core.navigation import (
    ERR_BAD_INDEX,
    ERR_DEPTH_LIMIT,
    ERR_EMPTY,
    ERR_NO_MATCH,
    ERR_NOT_DIR,
    ERR_TOO_MANY,
    DirectoryNavigator,
    parse_token,
    tokenize_nav,
)


def test_parse_token():
    assert parse_token("abc") == ("abc", None)
    assert parse_token("abc#2") == ("abc", 2)
    assert parse_token("abc#") == ("abc", None)
    assert parse_token("abc#0") == ("abc", -1)
    assert parse_token("abc#x") == ("abc", -1)


def test_tokenize_nav():
    assert tokenize_nav("a b") == [("a", 1), ("b", 0)]
    assert tokenize_nav("  a  ") == [("a", 2)]
    assert tokenize_nav("") == []


def test_lists_directories_before_files(tmp_path):
    (tmp_path / "zeta").mkdir()
    (tmp_path / "alpha.txt").write_text("x", encoding="utf-8")

    result = DirectoryNavigator().navigate(tmp_path, "", 0)

    assert result.error is None
    assert [entry.name for entry in result.entries] == ["zeta", "alpha.txt"]


def test_hidden_entries_are_skipped(tmp_path):
    (tmp_path / ".secret").mkdir()
    (tmp_path / "visible").mkdir()

    result = DirectoryNavigator().navigate(tmp_path, "", 0)

    assert [entry.name for entry in result.entries] == ["visible"]


def test_too_many_entries():
    def lister(_path):
        return [(f"f{index}", False) for index in range(101)]

    result = DirectoryNavigator(lister=lister).navigate(Path("/x"), "", 0)
    assert result.error == ERR_TOO_MANY


def test_empty_directory(tmp_path):
    assert DirectoryNavigator().navigate(tmp_path, "", 0).error == ERR_EMPTY


def test_ranking_by_match_position(tmp_path):
    for name in ("alpha", "beta", "gamma"):
        (tmp_path / name).mkdir()

    result = DirectoryNavigator().navigate(tmp_path, "a", 0)

    assert [entry.name for entry in result.entries] == ["alpha", "gamma", "beta"]


def test_explicit_index(tmp_path):
    for name in ("alpha", "beta", "gamma"):
        (tmp_path / name).mkdir()

    result = DirectoryNavigator().navigate(tmp_path, "a#2", 0)

    assert [entry.name for entry in result.entries] == ["gamma"]


def test_bad_index(tmp_path):
    (tmp_path / "alpha").mkdir()
    assert DirectoryNavigator().navigate(tmp_path, "a#9", 0).error == ERR_BAD_INDEX


def test_no_match(tmp_path):
    (tmp_path / "alpha").mkdir()
    assert DirectoryNavigator().navigate(tmp_path, "zzz", 0).error == ERR_NO_MATCH


def test_depth_limit(tmp_path):
    (tmp_path / "a" / "b" / "c").mkdir(parents=True)

    assert DirectoryNavigator().navigate(tmp_path, "a b", 0).error == ERR_DEPTH_LIMIT
    assert DirectoryNavigator().navigate(tmp_path, "a b", 1).error is None


def test_descend_and_list_with_trailing_spaces(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "inner.txt").write_text("x", encoding="utf-8")

    result = DirectoryNavigator().navigate(tmp_path, "a b ", 2)

    assert result.error is None
    assert [entry.name for entry in result.entries] == ["inner.txt"]


def test_file_is_not_a_directory(tmp_path):
    (tmp_path / "file.txt").write_text("x", encoding="utf-8")
    assert DirectoryNavigator().navigate(tmp_path, "file ", 1).error == ERR_NOT_DIR


def test_pinyin_navigation(tmp_path):
    (tmp_path / "笔记").mkdir()

    result = DirectoryNavigator().navigate(tmp_path, "biji", 0)

    assert result.error is None
    assert result.entries[0].name == "笔记"


def test_can_explore(tmp_path):
    navigator = DirectoryNavigator()
    assert navigator.can_explore(tmp_path) is True
    assert navigator.can_explore(tmp_path / "missing") is False
