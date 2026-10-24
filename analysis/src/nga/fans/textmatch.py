"""Whole-word, case-sensitive text matching for Anime2You comments (fans lane).

Rules (ANALYSIS_PLAN.md §4, Anime2You row):
- Match ``characters.text_aliases()`` against ``content_text``, whole word,
  case-sensitive.
- German genitive exception: a trailing "s" still counts
  ("Sasukes Sharingan" -> Sasuke), but longer extensions do not ("Sasukeee").
- Bare ambiguous aliases (``Hinata``, ``Pain``) count only when a
  ``naruto_context_words`` term appears in the same comment (case-insensitive,
  whole word). Bare "Naruto" is never a character match (franchise name).
- One comment naming several characters yields one result per character.
"""
from __future__ import annotations

import re

from nga import characters

# Bare aliases that are too ambiguous to count on their own. They are NOT in
# text_aliases in config/characters.yaml; they are added here gated on context.
# (Hinata = also Shoyo Hinata of Haikyuu!!; Pain = an ordinary English word.)
AMBIGUOUS_BARE: dict[str, list[str]] = {
    "hinata_hyuga": ["Hinata"],
    "nagato_pain": ["Pain"],
}

_SEED = 20261023  # determinism seed; matching itself is deterministic


def _word_pattern(alias: str) -> "re.Pattern[str]":
    # Whole-word, case-sensitive; a single trailing genitive "s" is allowed.
    # Spaces inside multi-word aliases match any whitespace run.
    body = re.escape(alias).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){body}s?(?!\w)")


def _context_pattern(word: str) -> "re.Pattern[str]":
    return re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.IGNORECASE)


def compile_patterns() -> dict[str, list[tuple[str, "re.Pattern[str]", bool]]]:
    """Per character: list of (alias, regex, needs_context)."""
    out: dict[str, list[tuple[str, "re.Pattern[str]", bool]]] = {}
    for key in characters.keys():
        pats = [(a, _word_pattern(a), False) for a in characters.text_aliases(key)]
        for bare in AMBIGUOUS_BARE.get(key, []):
            pats.append((bare, _word_pattern(bare), True))
        out[key] = pats
    return out


def compile_context() -> list[tuple[str, "re.Pattern[str]"]]:
    return [(w, _context_pattern(w)) for w in characters.context_words()]


def find_matches(
    text: str | None,
    patterns: dict[str, list[tuple[str, "re.Pattern[str]", bool]]] | None = None,
    context: list[tuple[str, "re.Pattern[str]"]] | None = None,
) -> list[tuple[str, str, int]]:
    """Return [(character_key, matched_alias, start)] for one comment.

    At most one row per character: the earliest match. Empty/None text matches
    nothing.
    """
    if not text:
        return []
    patterns = patterns if patterns is not None else compile_patterns()
    context = context if context is not None else compile_context()
    has_context = any(rx.search(text) for _, rx in context)
    out: list[tuple[str, str, int]] = []
    for key, pats in patterns.items():
        best: tuple[str, int] | None = None
        for alias, rx, needs_context in pats:
            if needs_context and not has_context:
                continue
            m = rx.search(text)
            if m and (best is None or m.start() < best[1]):
                best = (alias, m.start())
        if best is not None:
            out.append((key, best[0], best[1]))
    return out
