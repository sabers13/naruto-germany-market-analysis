"""YouTube lane (fans lane): German comments (primary) and DE-channel videos.

- Comments: dedupe ``comment_id``; keep ``d_lang_guess == 'de'``; character =
  keys of ``d_mentions.entities`` mapped via ``source_map("youtube")``
  (``kakashi_mask`` -> ``kakashi_hatake``). Entity keys outside the locked
  set of 14 (clans, techniques, excluded characters) are ignored.
- Videos: ``is_naruto_relevant`` and ``channel_country == 'DE'``;
  dedupe ``video_id``; same entity mapping.
- Never reads YouTube's own view/like/comment-count statistics.
"""
from __future__ import annotations

import hashlib
import json

import duckdb
import pandas as pd

from nga import characters, paths

SOURCE = "youtube"
SNIPPET_WIDTH = 200


def snippet_around(text: str, start: int, width: int = SNIPPET_WIDTH) -> str:
    half = width // 2
    end = min(len(text), max(0, start) + half)
    begin = max(0, end - width)
    end = min(len(text), begin + width)
    return text[begin:end]


def _parse_entities(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw).get("entities", {}) or {}
    except (json.JSONDecodeError, AttributeError):
        return {}


def _first_surface(entity: dict, fallback: str) -> tuple[str, int]:
    """(matched_on surface, start) of the earliest sample, else (key, 0)."""
    best: tuple[str, int] | None = None
    for sample in entity.get("samples", []) or []:
        try:
            start = int(sample.get("start", 0))
        except (TypeError, ValueError):
            continue
        surface = str(sample.get("surface") or fallback)
        if best is None or start < best[1]:
            best = (surface, start)
    return best if best is not None else (fallback, 0)


def load_comments() -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(
        "SELECT comment_id, text, d_lang_guess, d_mentions FROM read_parquet(?)",
        [str(paths.dataset("youtube", "raw", "parquet",
                            "naruto-de-youtube-v1__comments.parquet"))],
    ).df()
    return df.drop_duplicates(subset="comment_id", keep="first")


def load_videos() -> pd.DataFrame:
    con = duckdb.connect()
    df = con.execute(
        "SELECT video_id, title, is_naruto_relevant, channel_country, d_mentions "
        "FROM read_parquet(?)",
        [str(paths.dataset("youtube", "raw", "parquet",
                            "naruto-de-youtube-v1__videos.parquet"))],
    ).df()
    return df.drop_duplicates(subset="video_id", keep="first")


def run() -> dict:
    """Run the YouTube lane. Returns aggregate counts for the report.

    Writes ``work/matches/youtube.parquet`` (comments only: the snippet is
    the comment text around the first match) and returns per-character
    comment/video counts plus lane totals.
    """
    smap = characters.source_map(SOURCE)
    locked = set(characters.keys())
    comments = load_comments()
    videos = load_videos()

    total_comments = int(comments["comment_id"].nunique())
    de = comments[comments["d_lang_guess"] == "de"].copy()
    n_de = int(de["comment_id"].nunique())

    comment_counts: dict[str, set[str]] = {k: set() for k in locked}
    comment_entities: dict[str, set[str]] = {}  # comment_id -> locked keys
    match_rows: list[dict] = []
    for row in de.itertuples():
        entities = _parse_entities(row.d_mentions)
        keys = {smap[e] for e in entities if e in smap and smap[e] in locked}
        if not keys:
            continue
        comment_entities[row.comment_id] = keys
        text = row.text or ""
        for entity_key in entities:
            key = smap.get(entity_key)
            if key not in locked or key not in keys:
                continue
            comment_counts[key].add(row.comment_id)
            surface, start = _first_surface(entities[entity_key], entity_key)
            match_rows.append({
                "record_hash": hashlib.sha1(str(row.comment_id).encode()).hexdigest(),
                "source": SOURCE,
                "character_key": key,
                "matched_on": surface,
                "snippet": snippet_around(text, start),
            })

    # solo: comments whose only candidate character is this one
    # (the benchmark naruto_uzumaki may co-occur).
    candidates = set(characters.keys("candidate"))
    solo_counts = {k: 0 for k in locked}
    for keys in comment_entities.values():
        cand = keys & candidates
        if len(cand) == 1:
            solo_counts[next(iter(cand))] += 1

    dev = videos[(videos["is_naruto_relevant"] == True)  # noqa: E712
                 & (videos["channel_country"] == "DE")].copy()
    video_counts: dict[str, set[str]] = {k: set() for k in locked}
    for row in dev.itertuples():
        for entity_key in _parse_entities(row.d_mentions):
            if entity_key in smap and smap[entity_key] in locked:
                video_counts[smap[entity_key]].add(row.video_id)

    matches = pd.DataFrame(match_rows, columns=[
        "record_hash", "source", "character_key", "matched_on", "snippet"])
    paths.work("matches", "youtube.parquet").parent.mkdir(parents=True, exist_ok=True)
    matches.to_parquet(paths.work("matches", "youtube.parquet"), index=False)

    return {
        "total_comments": total_comments,
        "total_videos": int(videos["video_id"].nunique()),
        "comments_de": n_de,
        "comment_counts": {k: len(v) for k, v in comment_counts.items()},
        "solo_counts": solo_counts,
        "videos_de": int(dev["video_id"].nunique()),
        "video_counts": {k: len(v) for k, v in video_counts.items()},
        "match_rows": len(matches),
    }
