from __future__ import annotations

from app.core.catalog import Catalog
from app.core.matching import normalize_alnum, to_pinyin
from app.models import Operation


def _file(display: str, keywords: str) -> Operation:
    return Operation(display=display, type="file", keywords=keywords, arguments={"path": "p"})


def _dir(display: str, keywords: str, allow_explore: bool = True) -> Operation:
    return Operation(
        display=display,
        type="dir",
        keywords=keywords,
        arguments={"dir": "d", "allow_explore": allow_explore, "explore_depth": 0},
    )


def test_normalize_alnum():
    assert normalize_alnum(r"E:\Play 2024!") == "eplay2024"
    assert normalize_alnum("笔记 Biji") == "biji"
    assert normalize_alnum("") == ""


def test_to_pinyin():
    assert to_pinyin("笔记") == "biji"
    assert to_pinyin("a笔记b") == "abijib"
    assert to_pinyin("课堂 笔记") == "ketangbiji"


def test_prefix_matching_not_substring():
    catalog = Catalog([_file("Excel", "excel|xl")])
    assert len(catalog.match("exc")) == 1
    assert len(catalog.match("EXCEL")) == 1
    assert catalog.match("xce") == []
    assert catalog.match("") == []


def test_directory_keywords_are_normalized():
    catalog = Catalog([_dir("Play", "play|wan")])
    assert len(catalog.match("PLAY!")) == 1
    assert len(catalog.match("w")) == 1
    assert catalog.match("lay") == []


def test_explore_lookup_skips_disabled():
    catalog = Catalog([_dir("Play", "play", allow_explore=False), _dir("Study", "study")])
    assert catalog.explore_operation("play") is None
    found = catalog.explore_operation("stu")
    assert found is not None and found.display == "Study"


def test_explore_lookup_requires_token():
    catalog = Catalog([_dir("Play", "play")])
    assert catalog.explore_operation("") is None
