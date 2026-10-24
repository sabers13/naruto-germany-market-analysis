"""The shared long-format metrics table every lane writes (ANALYSIS_PLAN.md §5).

One row = one number about one character (or "_all") from one source.
Lanes write work/metrics/<lane>.parquet with write(); scoring and release read them with read_all().
"""
from __future__ import annotations

import pandas as pd

from . import characters
from .paths import work

COLUMNS = {
    "character_key": "string",   # canonical key, or "_all" for a source total
    "source": "string",          # see SOURCES
    "metric": "string",          # see ANALYSIS_PLAN.md §5 registry
    "period": "string",          # "snapshot", "YYYY-MM", "YYYY-Qn" or "last_52w"
    "region": "string",          # "DE", a Bundesland code (e.g. "NW"), or "EU"
    "value": "float64",
    "n": "Int64",                # underlying record count behind the value (nullable)
    "unit": "string",            # "count", "eur", "index", "votes", "share", ...
    "evidence_class": "string",  # A-E, see BRIEF.md
    "lens": "string",            # shoppers | watching | votes | context
    "primary": "boolean",        # True = the one metric this source contributes to ranking
    "lane": "string",            # the shops lane..the votes lane
}
SOURCES = {"amazon", "ebay", "kleinanzeigen", "youtube", "google_trends", "anime2you",
           "narutop99", "wikimedia", "event_calendar"}
LENSES = {"shoppers", "watching", "votes", "context"}
CLASSES = {"A", "B", "C", "D", "E"}


def validate(df: pd.DataFrame) -> pd.DataFrame:
    missing = set(COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"metrics table missing columns: {sorted(missing)}")
    df = df[list(COLUMNS)].astype(COLUMNS)
    allowed_keys = set(characters.keys()) | {"_all"}
    problems = {
        "character_key": ~df.character_key.isin(allowed_keys),
        "source": ~df.source.isin(SOURCES),
        "lens": ~df.lens.isin(LENSES),
        "evidence_class": ~df.evidence_class.isin(CLASSES),
        "value": df.value.isna() & df.primary,
    }
    bad = {k: int(v.sum()) for k, v in problems.items() if v.any()}
    if bad:
        raise ValueError(f"invalid metric rows: {bad}")
    dup = df.duplicated(["character_key", "source", "metric", "period", "region"])
    if dup.any():
        raise ValueError(f"{int(dup.sum())} duplicate metric rows")
    # a source may mark at most one metric as primary
    prim = df[df.primary].groupby("source").metric.nunique()
    if (prim > 1).any():
        raise ValueError(f"more than one primary metric for: {list(prim[prim > 1].index)}")
    return df


def write(df: pd.DataFrame, lane: str) -> None:
    validate(df).to_parquet(work("metrics", f"{lane}.parquet"), index=False)


def read_all() -> pd.DataFrame:
    files = sorted(work("metrics", "x").parent.glob("*.parquet"))
    if not files:
        raise FileNotFoundError("no lane metrics in work/metrics/; run the lanes first")
    return validate(pd.concat([pd.read_parquet(f) for f in files], ignore_index=True))
