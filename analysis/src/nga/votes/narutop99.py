"""NARUTOP99 fan vote (ANALYSIS_PLAN.md §4).

One 2023 snapshot, region = 'europe'. Metric ``votes_eu``: primary, unit
votes, class C, lens votes. All 14 locked characters are present.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from nga import characters
from nga.paths import dataset

REGION = "europe"
# Rankings snapshot archived 2023-04-21 (monthly precision is the finest
# honest grain: the poll ran Dec 2022 - Jan 2023, results published April).
PERIOD = "2023-04"


def run() -> pd.DataFrame:
    """Return the 14-row metrics frame for the Europe NARUTOP99 vote."""
    con = duckdb.connect()
    rows = con.execute(
        "SELECT name_en, votes FROM read_parquet(?) WHERE region = ?",
        [str(dataset("anime2you", "data", "external", "narutop99",
                     "narutop99_rankings.parquet")), REGION],
    ).fetchall()
    con.close()
    smap = characters.source_map("narutop99")
    votes: dict[str, int] = {}
    for name_en, v in rows:
        if name_en in smap:
            key = smap[name_en]
            if key in votes:
                raise ValueError(f"duplicate NARUTOP99 name_en for {key}: {name_en}")
            votes[key] = int(v)
    missing = set(characters.keys()) - set(votes)
    if missing:
        raise ValueError(f"NARUTOP99 europe missing characters: {sorted(missing)}")
    return pd.DataFrame([{
        "character_key": key,
        "source": "narutop99",
        "metric": "votes_eu",
        "period": PERIOD,
        "region": "EU",
        "value": float(votes[key]),
        "n": 1,  # one ranking row per character
        "unit": "votes",
        "evidence_class": "C",
        "lens": "votes",
        "primary": True,
        "lane": "votes",
    } for key in characters.keys()])


def europe_row_count() -> int:
    """Rows scanned in the archive table for region = 'europe'."""
    con = duckdb.connect()
    n = con.execute(
        "SELECT COUNT(*) FROM read_parquet(?) WHERE region = ?",
        [str(dataset("anime2you", "data", "external", "narutop99",
                     "narutop99_rankings.parquet")), REGION],
    ).fetchone()[0]
    con.close()
    return int(n)
