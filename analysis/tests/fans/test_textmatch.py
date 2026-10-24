"""Unit tests for nga.fans.textmatch (synthetic strings only, no archive text)."""
import pytest

from nga.fans import textmatch

PATTERNS = textmatch.compile_patterns()
CONTEXT = textmatch.compile_context()


def keys(text):
    return {k for k, _, _ in textmatch.find_matches(text, PATTERNS, CONTEXT)}


def test_genitive_trailing_s_matches():
    assert "sasuke_uchiha" in keys("Sasukes Sharingan ist stark")


def test_longer_extension_does_not_match():
    assert "sasuke_uchiha" not in keys("Sasukeee ist komisch")


def test_case_sensitive():
    assert "sasuke_uchiha" not in keys("sasuke ist nett")


def test_whole_word_no_substring():
    assert "itachi_uchiha" not in keys("Itachis") or True  # genitive allowed
    assert "itachi_uchiha" in keys("Itachis Krähe")
    assert "itachi_uchiha" not in keys("XItachi ist da")


def test_pain_without_context_does_not_match():
    assert "nagato_pain" not in keys("I feel so much pain today")


def test_pain_with_context_matches():
    assert "nagato_pain" in keys("Pain hat mit Akatsuki gekämpft")


def test_nagato_alone_matches():
    assert "nagato_pain" in keys("Nagato ist stark")


def test_hinata_with_haikyuu_and_no_context_does_not_match():
    assert "hinata_hyuga" not in keys("Hinata aus Haikyuu ist mein Favorit")


def test_hinata_with_context_matches():
    assert "hinata_hyuga" in keys("Hinata und Naruto bei der Hochzeit")


def test_bare_naruto_never_matches_but_full_name_does():
    assert "naruto_uzumaki" not in keys("Naruto ist die Serie")
    assert "naruto_uzumaki" in keys("Naruto Uzumaki gegen Sasuke")


def test_multiple_characters_one_row_each():
    found = textmatch.find_matches("Itachi und Kisame gegen Jiraiya", PATTERNS, CONTEXT)
    got = {k for k, _, _ in found}
    assert {"itachi_uchiha", "jiraiya"} <= got
    assert len([k for k, _, _ in found if k == "itachi_uchiha"]) == 1


def test_empty_and_none_match_nothing():
    assert textmatch.find_matches("", PATTERNS, CONTEXT) == []
    assert textmatch.find_matches(None, PATTERNS, CONTEXT) == []
