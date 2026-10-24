"""Source ranks -> lens ranks -> score -> evidence index -> rank.

Implements ANALYSIS_PLAN.md Section 7 rules 1-6 exactly:

1. Within each in-score source: rank the candidates by the (precision-adjusted)
   primary metric, highest = 1. Ties get the average rank. Missing is not ranked.
2. Lens rank: mean of the character's source ranks within the lens; null when
   fewer than half of the lens's sources rank the character.
3. Score: weighted mean over the non-null lenses, renormalised. Lower is better.
4. Evidence index: round((13 - score) / 12 * 100).
5. Rank: ordered by score; ties broken by shoppers lens rank, then alphabetically.
6. top3_sources: number of in-score sources where the character ranks <= 3.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# ANALYSIS_PLAN.md Section 5: the 7 in-score sources (primary metric only).
IN_SCORE_SOURCES = (
    "amazon",
    "ebay",
    "kleinanzeigen",
    "youtube",
    "google_trends",
    "anime2you",
    "narutop99",
)

# ANALYSIS_PLAN.md Section 5: 3 shoppers, 3 watching, 1 votes.
LENS_SOURCES: dict[str, list[str]] = {
    "shoppers": ["amazon", "ebay", "kleinanzeigen"],
    "watching": ["youtube", "google_trends", "anime2you"],
    "votes": ["narutop99"],
}
LENSES = ("shoppers", "watching", "votes")

SOURCE_LENS: dict[str, str] = {
    source: lens for lens, sources in LENS_SOURCES.items() for source in sources
}

# ANALYSIS_PLAN.md Section 7.3.
DEFAULT_WEIGHTS: dict[str, float] = {"shoppers": 0.5, "watching": 0.3, "votes": 0.2}

# ANALYSIS_PLAN.md Section 7.7, fixed alternative weightings.
ALT_WEIGHTS: dict[str, dict[str, float]] = {
    "equal": {"shoppers": 1 / 3, "watching": 1 / 3, "votes": 1 / 3},
    "shoppers_only": {"shoppers": 1.0, "watching": 0.0, "votes": 0.0},
    "german_only": {"shoppers": 0.625, "watching": 0.375, "votes": 0.0},
}

# ANALYSIS_PLAN.md Section 2.
BENCHMARK = "naruto_uzumaki"
SOURCE_TOTAL = "_all"

# Precision treatments (ANALYSIS_PLAN.md Section 6.5) as stored in
# work/accuracy/precision.parquet `treatment` column. Tolerated aliases map to
# the same behaviour; anything else raises.
_TREAT_USE = {"use"}
_TREAT_ADJUST = {"adjust", "low_precision"}
_TREAT_EXCLUDE = {"exclude", "excluded_source"}


def candidate_values(metrics_df: pd.DataFrame) -> pd.DataFrame:
    """Pivot primary in-score values to character_key x source.

    Keeps only ``primary == True`` rows from in-score sources and candidate
    characters (never the benchmark, never source totals). Exactly one row per
    (character, source) is expected; duplicates raise.
    """
    df = metrics_df[
        (metrics_df["primary"] == True)  # noqa: E712 - handles bool/int dtypes
        & (metrics_df["source"].isin(IN_SCORE_SOURCES))
        & (~metrics_df["character_key"].isin([BENCHMARK, SOURCE_TOTAL]))
    ].copy()
    if df.empty:
        raise ValueError("no primary in-score candidate rows to score")
    dup = df.duplicated(["character_key", "source"])
    if dup.any():
        bad = sorted(df.loc[dup, ["character_key", "source"]].apply(tuple, axis=1).unique())
        raise ValueError(f"duplicate (character, source) metric rows: {bad}")
    values = df.pivot_table(
        index="character_key", columns="source", values="value", aggfunc="first"
    )
    for source in IN_SCORE_SOURCES:
        if source not in values.columns:
            values[source] = np.nan
    return values[list(IN_SCORE_SOURCES)].sort_index()


def _normalise_treatment(raw: str) -> str:
    t = str(raw).strip().lower()
    if t in _TREAT_USE:
        return "use"
    if t in _TREAT_ADJUST:
        return "adjust"
    if t in _TREAT_EXCLUDE:
        return "exclude"
    raise ValueError(f"unknown precision treatment: {raw!r}")


def apply_precision(
    values: pd.DataFrame, precision_df: pd.DataFrame | None
) -> tuple[pd.DataFrame, dict[str, set[str]]]:
    """Apply Section 6.5 treatments; return (adjusted values, flags per character).

    Lookup is per (source, character) first, else per source (``_all`` row).
    ``adjust`` multiplies the value by precision and flags ``low_precision``;
    ``exclude`` drops the value and flags ``excluded_source``. Flags are only
    set when a character actually had a value in that source.
    """
    adjusted = values.copy()
    flags: dict[str, set[str]] = {char: set() for char in values.index}
    if precision_df is None or len(precision_df) == 0:
        return adjusted, flags
    exact = {
        (str(r.source), str(r.character_key)): r
        for r in precision_df.itertuples()
        if str(r.character_key) != SOURCE_TOTAL
    }
    overall = {
        str(r.source): r
        for r in precision_df.itertuples()
        if str(r.character_key) == SOURCE_TOTAL
    }
    for source in IN_SCORE_SOURCES:
        if source not in adjusted.columns:
            continue
        for char in adjusted.index:
            row = exact.get((source, char), overall.get(source))
            if row is None:
                continue
            treatment = _normalise_treatment(row.treatment)
            if treatment == "use":
                continue
            if pd.isna(adjusted.loc[char, source]):
                continue
            if treatment == "adjust":
                if pd.isna(row.precision):
                    raise ValueError(
                        f"null precision for adjust treatment: {(source, char)}"
                    )
                adjusted.loc[char, source] = adjusted.loc[char, source] * float(
                    row.precision
                )
                flags[char].add("low_precision")
            else:  # exclude
                adjusted.loc[char, source] = np.nan
                flags[char].add("excluded_source")
    return adjusted, flags


def check_precision_floor(precision_df: pd.DataFrame | None) -> None:
    """Enforce the Section 10 stop rule: overall source precision < 0.50 stops."""
    if precision_df is None or len(precision_df) == 0:
        return
    bad = sorted(
        str(r.source)
        for r in precision_df.itertuples()
        if str(r.character_key) == SOURCE_TOTAL and float(r.precision) < 0.50
    )
    if bad:
        raise RuntimeError(
            f"STOP (ANALYSIS_PLAN.md Section 10.3): overall keyword precision < 0.50 "
            f"for source(s): {bad}"
        )


def rank_sources(values: pd.DataFrame) -> pd.DataFrame:
    """Per-source ranks: highest value = 1, ties averaged, missing unranked."""
    return values.rank(axis=0, ascending=False, method="average", na_option="keep")


def lens_ranks_from_source_ranks(source_ranks: pd.DataFrame) -> pd.DataFrame:
    """Lens rank = mean of the character's source ranks within the lens.

    Null when fewer than half of the lens's sources rank the character
    (shoppers/watching: fewer than 2 of 3; votes: missing narutop99).
    """
    out = pd.DataFrame(index=source_ranks.index)
    for lens in LENSES:
        cols = [c for c in LENS_SOURCES[lens] if c in source_ranks.columns]
        n_ranked = source_ranks[cols].notna().sum(axis=1)
        mean = source_ranks[cols].mean(axis=1, skipna=True)
        out[lens] = mean.mask(n_ranked < len(LENS_SOURCES[lens]) / 2)
    return out


def score_from_lenses(
    lens_df: pd.DataFrame, weights: dict[str, float]
) -> pd.Series:
    """Weighted mean over non-null lenses, renormalised. Lower is better."""
    w = pd.Series(weights, dtype=float).reindex(list(LENSES), fill_value=0.0)
    if (w < 0).any():
        raise ValueError(f"negative lens weight: {dict(w)}")
    if w.sum() <= 0:
        raise ValueError(f"all lens weights are zero: {dict(w)}")
    vals = lens_df[list(LENSES)]
    denom = (vals.notna() * w).sum(axis=1)
    numer = (vals.fillna(0.0) * w).sum(axis=1)
    return numer / denom.replace(0.0, np.nan)


def evidence_index(score: float) -> int | None:
    """round((13 - score) / 12 * 100); score 1 -> 100, score 13 -> 0."""
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return None
    return int(round((13.0 - float(score)) / 12.0 * 100.0))


def top3_sources_from_ranks(source_ranks: pd.DataFrame) -> pd.Series:
    """Number of in-score sources where the character ranks <= 3."""
    return (source_ranks[list(IN_SCORE_SOURCES)] <= 3).sum(axis=1).astype(int)


def run_ranking(
    values: pd.DataFrame,
    sources: list[str],
    weights: dict[str, float],
) -> dict:
    """One full ranking pass over a subset of sources with given weights.

    Returns source/lens ranks, the ordered table (score, lenses) and the top-3
    character keys in rank order.
    """
    cols = [c for c in IN_SCORE_SOURCES if c in sources and c in values.columns]
    source_ranks = rank_sources(values[cols])
    # Keep all 7 columns so top3_sources always counts the same sources.
    for missing in IN_SCORE_SOURCES:
        if missing not in source_ranks.columns:
            source_ranks[missing] = np.nan
    source_ranks = source_ranks[list(IN_SCORE_SOURCES)]
    lens = lens_ranks_from_source_ranks(source_ranks)
    scores = score_from_lenses(lens, weights)
    table = lens.copy()
    table["score"] = scores
    table = table.reset_index()  # character_key back to a plain column
    # Section 7.5: by score, then shoppers lens rank, then alphabetically.
    # NaN scores / shoppers ranks sort last.
    table = table.sort_values(
        ["score", "shoppers", "character_key"],
        ascending=[True, True, True],
        na_position="last",
    )
    scored = table[table["score"].notna()]
    top3 = list(scored["character_key"].head(3))
    return {"source_ranks": source_ranks, "lens": lens, "table": table, "top3": top3}
