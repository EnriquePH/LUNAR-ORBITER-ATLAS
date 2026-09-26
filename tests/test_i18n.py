import re

import pytest

from orbiter.i18n import LANGUAGES, TEXTS, normalize_language, t
from orbiter.lpi import LpiError
from orbiter.reference import CONTENT, moon_tab, program_tab


def test_every_language_defines_the_same_keys_and_placeholders():
    spanish = TEXTS["es"]
    for lang in LANGUAGES:
        assert TEXTS[lang].keys() == spanish.keys(), lang
        for key, text in TEXTS[lang].items():
            placeholders = set(re.findall(r"{(\w+)}", text))
            assert placeholders == set(re.findall(r"{(\w+)}", spanish[key])), key


def test_every_lpi_error_has_a_translation():
    for lang in LANGUAGES:
        for key in LpiError.MESSAGES:
            assert f"error_{key}" in TEXTS[lang]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("en", "en"), ("EN-us", "en"), ("es", "es"), ("fr", "es"), (None, "es")],
)
def test_normalize_language_falls_back_to_default(value, expected):
    assert normalize_language(value) == expected


def test_t_formats_parameters():
    assert t("en", "show_hidden", count=3) == "SHOW HIDDEN (3)"
    assert t("es", "show_hidden", count=3) == "MOSTRAR OCULTAS (3)"


def test_reference_content_matches_between_languages():
    spanish, english = CONTENT["es"], CONTENT["en"]
    assert spanish.keys() == english.keys()
    for key, value in spanish.items():
        if isinstance(value, list):
            assert len(value) == len(english[key]), key
    for (_, es_facts), (_, en_facts) in zip(
        spanish["moon_facts"], english["moon_facts"], strict=True
    ):
        assert len(es_facts) == len(en_facts)


@pytest.mark.parametrize("lang", LANGUAGES)
def test_reference_tabs_link_source_and_licence(lang):
    for tab in (moon_tab(lang), program_tab(lang)):
        text = str(tab)
        assert "wikipedia.org/wiki/" in text
        assert "CC BY-SA 4.0" in text
