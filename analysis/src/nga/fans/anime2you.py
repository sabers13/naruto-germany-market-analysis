"""Anime2You lane (fans lane): comment text matching (primary) and article tags.

- Comments: dedupe ``id``; whole-word, case-sensitive ``text_aliases``
  matching on ``content_text`` (see :mod:`nga.fans.textmatch`); bare
  ``Hinata``/``Pain`` only with a ``naruto_context_words`` term.
  Metric ``comment_mentions`` (primary).
- Posts: ``characters_mentioned`` tags mapped back to canonical keys via the
  ``anime2you`` source spellings (``Pain`` -> ``nagato_pain``); names outside
  the locked set of 14 are ignored. Secondary metric ``articles``.
"""
from __future__ import annotations

import hashlib
import json

import duckdb
import pandas as pd

from nga import characters, paths
from nga.fans import textmatch
from nga.fans.youtube import snippet_around

SOURCE = "anime2you"


def load_comments() -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(
        "SELECT id, content_text FROM read_parquet(?)",
        [str(paths.dataset("anime2you", "data", "full", "comments.parquet"))],
    ).df()
    return df.drop_duplicates(subset="id", keep="first")


def load_posts() -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(
        "SELECT id, characters_mentioned FROM read_parquet(?)",
        [str(paths.dataset("anime2you", "data", "full", "posts.parquet"))],
    ).df()
    return df.drop_duplicates(subset="id", keep="first")


def run() -> dict:
    """Run the Anime2You lane. Writes ``work/matches/anime2you.parquet``."""
    locked = set(characters.keys())
    # Reverse map: archive display name -> canonical key, e.g. "Pain" -> nagato_pain.
    display_to_key = dict(characters.source_map(SOURCE))
    patterns = textmatch.compile_patterns()
    context = textmatch.compile_context()

    comments = load_comments()
    counts: dict[str, set] = {k: set() for k in locked}
    comment_keys: dict = {}
    match_rows: list[dict] = []
    for row in comments.itertuples():
        text = row.content_text or ""
        found = textmatch.find_matches(text, patterns, context)
        if not found:
            continue
        keys = {k for k, _, _ in found}
        comment_keys[row.id] = keys
        for key, alias, start in found:
            counts[key].add(row.id)
            match_rows.append({
                "record_hash": hashlib.sha1(str(row.id).encode()).hexdigest(),
                "source": SOURCE,
                "character_key": key,
                "matched_on": alias,
                "snippet": snippet_around(text, start),
            })

    candidates = set(characters.keys("candidate"))
    solo_counts = {k: 0 for k in locked}
    for keys in comment_keys.values():
        cand = keys & candidates
        if len(cand) == 1:
            solo_counts[next(iter(cand))] += 1

    posts = load_posts()
    article_counts: dict[str, set] = {k: set() for k in locked}
    for row in posts.itertuples():
        try:
            tags = json.loads(row.characters_mentioned) if row.characters_mentioned else []
        except (json.JSONDecodeError, TypeError):
            continue
        for tag in tags:
            if tag in display_to_key and display_to_key[tag] in locked:
                article_counts[display_to_key[tag]].add(row.id)

    matches = pd.DataFrame(match_rows, columns=[
        "record_hash", "source", "character_key", "matched_on", "snippet"])
    paths.work("matches", "anime2you.parquet").parent.mkdir(parents=True, exist_ok=True)
    matches.to_parquet(paths.work("matches", "anime2you.parquet"), index=False)

    return {
        "total_comments": int(comments["id"].nunique()),
        "total_posts": int(posts["id"].nunique()),
        "comment_counts": {k: len(v) for k, v in counts.items()},
        "solo_counts": solo_counts,
        "article_counts": {k: len(v) for k, v in article_counts.items()},
        "match_rows": len(matches),
    }
