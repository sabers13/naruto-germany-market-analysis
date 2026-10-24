"""Context source (ANALYSIS_PLAN.md §4): Wikimedia pageviews.

Lens ``context``, non-primary (shown, never ranked), class C.

Wikimedia: granularity = 'monthly', agent = 'user', last 12 complete months
before the 2026-10-22 snapshot (2025-10 .. 2026-09), all languages summed.
Metric ``pageviews_12m``.
"""
from __future__ import annotations

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

