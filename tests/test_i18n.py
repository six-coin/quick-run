"""语言包的发现、回退与完整性检查。"""

from __future__ import annotations

import json
import re

from app import i18n, paths

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def load(language_code: str) -> dict[str, str]:
    target = paths.LOCALE_DIR / f"{language_code}.json"
    return json.loads(target.read_text(encoding="utf-8"))


def test_default_language_is_listed_first():
    languages = i18n.available_languages()

    assert languages[0] == i18n.DEFAULT_LANGUAGE
    assert "en-US" in languages


def test_normalize_accepts_discovered_codes_only():
    assert i18n.normalize("en-US") == "en-US"
    assert i18n.normalize("EN-us") == "en-US"
    assert i18n.normalize("fr-FR") == i18n.DEFAULT_LANGUAGE
    assert i18n.normalize("") == i18n.DEFAULT_LANGUAGE
    assert i18n.normalize(None) == i18n.DEFAULT_LANGUAGE


def test_language_names_cover_every_locale():
    names = i18n.language_names()

    assert set(names) == set(i18n.available_languages())
    assert names["zh-CN"] == "中文"
    assert names["en-US"] == "English"


def test_every_locale_has_the_same_keys():
    base = load(i18n.DEFAULT_LANGUAGE)

    for code in i18n.available_languages():
        data = load(code)
        assert sorted(set(base) - set(data)) == [], f"{code} 缺少键"
        assert sorted(set(data) - set(base)) == [], f"{code} 多出键"


def test_placeholders_match_the_default_language():
    base = load(i18n.DEFAULT_LANGUAGE)

    for code in i18n.available_languages():
        data = load(code)
        for key, text in data.items():
            assert set(PLACEHOLDER.findall(text)) == set(PLACEHOLDER.findall(base[key])), (
                f"{code} 的 {key} 占位符与默认语言不一致"
            )


def test_unknown_key_falls_back_to_itself():
    assert i18n.t("no.such.key") == "no.such.key"


def test_list_separator_follows_the_language():
    i18n.set_language("zh-CN")
    assert i18n.list_separator() == "、"

    i18n.set_language("en-US")
    assert i18n.list_separator() == ", "
