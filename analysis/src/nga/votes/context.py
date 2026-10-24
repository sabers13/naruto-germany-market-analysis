"""Context sources (ANALYSIS_PLAN.md §4): Wikimedia pageviews and Instagram media.

Both are lens ``context``, non-primary (shown, never ranked), class C.

Wikimedia: granularity = 'monthly', agent = 'user', last 12 complete months
before the 2026-10-22 snapshot (2025-10 .. 2026-09), all languages summed.
Metric ``pageviews_12m``.

Instagram: media records (``record_type = 'media'``) whose ``mentions_detail``
keys name the character. Metric ``media`` (distinct media count).
"""
from __future__ import annotations

import json

import duckdb
import pandas as pd

from nga import characters
from nga.paths import dataset

# Last 12 complete months before snapshot 2026-10-22. Monthly timestamps are
# 'YYYYMM' strings (daily rows use 8 digits and are excluded by granularity).
WIKI_START = "202510"
WIKI_END = "202609"


def wikimedia_run() -> tuple[pd.DataFrame, int]:
    """Return (metrics frame, pageview rows summed) for the 12-month window."""
    con = duckdb.connect()
    df = con.execute(
        """SELECT character_key, SUM(views) AS views, COUNT(*) AS n
           FROM read_parquet(?)
           WHERE granularity = 'monthly' AND agent = 'user'
             AND timestamp BETWEEN ? AND ?
           GROUP BY character_key""",
        [str(dataset("wikimedia", "collector", "exports", "full_2026-10-22",
                     "pageviews.parquet")), WIKI_START, WIKI_END],
    ).fetch_df()
    con.close()
    smap = characters.source_map("wikimedia")
    by_key: dict[str, tuple[float, int]] = {}
    for _, r in df.iterrows():
        if r["character_key"] in smap:
            by_key[smap[r["character_key"]]] = (float(r["views"]), int(r["n"]))
    missing = set(characters.keys()) - set(by_key)
    if missing:
        raise ValueError(f"Wikimedia 12m window missing characters: {sorted(missing)}")
    rows = [{
        "character_key": key,
        "source": "wikimedia",
        "metric": "pageviews_12m",
        "period": "last_12m",
        "region": "global",  # all languages summed, worldwide readership
        "value": by_key[key][0],
        "n": by_key[key][1],  # pageview rows aggregated behind the sum
        "unit": "count",
        "evidence_class": "C",
        "lens": "context",
        "primary": False,
        "lane": "votes",
    } for key in characters.keys()]
    return pd.DataFrame(rows), int(df["n"].sum())


def _media_character_sets() -> dict[str, set[str]]:
    """Map character key -> set of media record_ids mentioning it."""
    con = duckdb.connect()
    rows = con.execute(
        """SELECT record_id, mentions_detail FROM read_parquet(?)
           WHERE record_type = 'media'""",
        [str(dataset("instagram", "raw", "parquet", "insta_records.parquet"))],
    ).fetchall()
    con.close()
    smap = characters.source_map("instagram")
    found: dict[str, set[str]] = {k: set() for k in characters.keys()}
    n_media = 0
    for record_id, detail in rows:
        n_media += 1
        try:
            keys = json.loads(detail or "{}")
        except json.JSONDecodeError:
            keys = {}
        for k in keys:
            if k in smap:
                found[smap[k]].add(record_id)
    return found, n_media


def instagram_run() -> tuple[pd.DataFrame, int]:
    """Return (metrics frame, media rows scanned) for Instagram mentions."""
    found, n_media = _media_character_sets()
    rows = [{
        "character_key": key,
        "source": "instagram",
        "metric": "media",
        "period": "snapshot",
        "region": "global",  # collection is not DE-scoped
        "value": float(len(found[key])),
        "n": len(found[key]),  # distinct media records behind the count
        "unit": "count",
        "evidence_class": "C",
        "lens": "context",
        "primary": False,
        "lane": "votes",
    } for key in characters.keys()]
    return pd.DataFrame(rows), n_media
