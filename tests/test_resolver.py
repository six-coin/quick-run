from __future__ import annotations

from app.core.catalog import Catalog
from app.core.navigation import DirectoryNavigator
from app.core.resolver import QueryResolver
from app.core.rows import RowKind, RowStatus
from app.models import Operation


def make_resolver(operations, ai_api_key: str = "", translate: bool = False) -> QueryResolver:
    return QueryResolver(
        Catalog(operations),
        DirectoryNavigator(),
        ai_api_key=ai_api_key,
        translate_enabled=translate,
    )


def file_op(display: str = "Excel", keywords: str = "excel|xl") -> Operation:
    return Operation(
        display=display,
        type="file",
        keywords=keywords,
        arguments={"path": "p", "no_window": False},
    )


def dir_op(root, allow_explore: bool = True, depth: int = 1) -> Operation:
    return Operation(
        display="Play",
        type="dir",
        keywords="play",
        arguments={"dir": str(root), "allow_explore": allow_explore, "explore_depth": depth},
    )


def test_empty_query():
    assert make_resolver([]).resolve("").rows == []


def test_external_match():
    rows = make_resolver([file_op()]).resolve("exc").rows
    assert len(rows) == 1
    assert rows[0].kind is RowKind.EXTERNAL
    assert rows[0].text == "Excel"


def test_backtick_forces_internal_rows():
    rows = make_resolver([file_op()]).resolve("exc`").rows
    assert all(row.kind is not RowKind.EXTERNAL for row in rows)
    assert rows[0].kind is RowKind.SEARCH
    assert rows[0].text == "搜索：exc"


def test_calculation_is_inserted_first():
    rows = make_resolver([]).resolve("1+2").rows
    assert rows[0].kind is RowKind.CALCULATE
    assert rows[0].status is RowStatus.DONE
    assert rows[0].text == "计算：3"
    assert rows[1].kind is RowKind.SEARCH


def test_calculation_error_is_rendered():
    rows = make_resolver([]).resolve("1/0").rows
    assert rows[0].kind is RowKind.CALCULATE
    assert rows[0].status is RowStatus.FAILED
    assert rows[0].text == "计算：division by zero"


def test_async_calculation_is_pending():
    resolution = make_resolver([]).resolve("2**10")
    assert resolution.rows[0].status is RowStatus.LOADING
    assert resolution.rows[0].text == "计算：计算中..."
    assert resolution.pending[0].kind is RowKind.CALCULATE
    assert resolution.pending[0].delay_ms == 50


def test_live_translate_is_pending():
    resolution = make_resolver([], translate=True).resolve("hello")
    assert resolution.rows[-1].kind is RowKind.TRANSLATE
    assert resolution.rows[-1].status is RowStatus.LOADING
    assert resolution.rows[-1].text == "翻译：等待中..."
    assert resolution.pending[0].delay_ms == 500


def test_long_text_skips_live_translate():
    resolution = make_resolver([], translate=True).resolve("x" * 40)
    assert resolution.pending == []
    assert resolution.rows[-1].text == "翻译：" + "x" * 40


def test_definition_row_requires_api_key():
    without_key = make_resolver([]).resolve("abc").rows
    assert all(row.kind is not RowKind.DEFINITION for row in without_key)

    with_key = make_resolver([], ai_api_key="k").resolve("abc").rows
    definition_rows = [row for row in with_key if row.kind is RowKind.DEFINITION]
    assert len(definition_rows) == 1
    assert definition_rows[0].text == "查词：abc（回车或双击开始查词）"


def test_explore_lists_root(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.txt").write_text("x", encoding="utf-8")

    rows = make_resolver([dir_op(tmp_path)]).resolve("play ").rows

    assert len(rows) == 1
    assert rows[0].kind is RowKind.EXPLORE
    assert rows[0].text == "[1] 文件夹：sub"


def test_explore_descends(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.txt").write_text("x", encoding="utf-8")

    rows = make_resolver([dir_op(tmp_path)]).resolve("play sub ").rows

    assert rows[0].text == "[1] 文件：inner.txt"


def test_explore_error_row(tmp_path):
    rows = make_resolver([dir_op(tmp_path)]).resolve("play nothing").rows
    assert rows[0].kind is RowKind.ERROR
    assert rows[0].text == "错误：没有搜索到指定的项目"


def test_explore_disabled_falls_back_to_matching(tmp_path):
    rows = make_resolver([dir_op(tmp_path, allow_explore=False)]).resolve("play ").rows
    assert rows[0].kind is RowKind.EXTERNAL


def test_whitespace_only_query_is_empty():
    resolver = make_resolver([file_op()])
    assert resolver.resolve("   ").rows == []
    assert resolver.resolve(chr(10) + chr(9)).rows == []


def test_hash_index_selects_nth_match():
    resolver = make_resolver([file_op("Excel", "excel|xl"), file_op("Extra", "excel|ex")])
    rows = resolver.resolve("exc#2").rows
    assert len(rows) == 1
    assert rows[0].text == "Extra"


def test_hash_index_out_of_range():
    rows = make_resolver([file_op()]).resolve("exc#9").rows
    assert rows[0].kind is RowKind.ERROR
    assert rows[0].text == "错误：未知序号"


def test_lone_hash_is_ignored():
    resolver = make_resolver([file_op()])
    rows = resolver.resolve("#").rows
    assert rows[0].kind is RowKind.SEARCH
    assert rows[0].text == "搜索：#"

    rows = resolver.resolve("#2").rows
    assert rows[0].kind is RowKind.SEARCH


def test_hash_index_without_matches_falls_back_to_internal():
    rows = make_resolver([file_op()]).resolve("zzz#2").rows
    assert rows[0].kind is RowKind.SEARCH


def test_indexed_directory_operation_enters_navigation(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.txt").write_text("x", encoding="utf-8")

    rows = make_resolver([dir_op(tmp_path)]).resolve("play#1 ").rows

    assert rows[0].text == "[1] 文件夹：sub"
