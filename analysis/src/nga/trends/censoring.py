"""Censoring check for Google Trends series (ANALYSIS_PLAN.md §4/§8).

Corrected test (§12 entry 2026-10-23): the archive's own
definition as term_inventory.csv applies it. A series is censored if its peak
over the FULL window of the request it comes from (the the trends lane batch/view) is
< 10, OR if more than 30% of its weekly values are zero within the window
being used (the 52 weeks for interest_52w scoring; the full momentum window
for momentum flags). Peaks are never tested on the 52-week sub-window:
every request contains the dominant anchor "Naruto", so every candidate's
recent peak is small by construction.

Censored series are missing in interest_52w scoring (plan §4) and flagged
"censored" in momentum (flag precedence: ambiguous_name > censored >
term_series > topic_series lives in nga.release).
"""
from __future__ import annotations

import pandas as pd

from nga.trends import (ANCHOR_TERM, N_WEEKS_52W, REFERENCE_BATCH, SERIES,
                        SNAPSHOT_DATE)
from nga.trends.bridge import bridge_factor_k, rescale_series
from nga.trends.momentum import complete_weeks

#: Archive definition thresholds.
PEAK_FLOOR = 10
ZERO_SHARE_LIMIT = 0.30


def is_censored(full_peak: float, zero_share: float) -> bool:
    """True when the series is censored: peak < 10 or > 30% zero weeks."""
    return bool(full_peak < PEAK_FLOOR or zero_share > ZERO_SHARE_LIMIT)


def censoring_table(weekly: pd.DataFrame, entries: list | None = None) -> pd.DataFrame:
    """One row per the trends lane SERIES entry, on the exact batch/view the trends lane uses.

    Columns: character_key, term, batch, full_peak (peak over the full
    window of the request), zero_52w (zero share in the 52-week scoring
    window), zero_full (zero share in the full momentum window),
    censored_scoring (full_peak < 10 or zero_52w > 0.30),
    censored_momentum (full_peak < 10 or zero_full > 0.30).
    ``entries`` defaults to the the trends lane SERIES table; tests pass a subset.
    """
    entries = list(SERIES) if entries is None else entries
    ref_df = weekly.loc[weekly["batch_id"] == REFERENCE_BATCH]
    if len(ref_df) == 0:
        raise ValueError(f"reference batch {REFERENCE_BATCH} not found")
    rows: list[dict] = []
    for key, term, _kind, batch, _flag in entries:
        bdf = weekly.loc[weekly["batch_id"] == batch]
        k = 1.0 if batch == REFERENCE_BATCH else bridge_factor_k(ref_df, bdf, ANCHOR_TERM)
        comp = complete_weeks(rescale_series(bdf, term, k),
                              SNAPSHOT_DATE).sort_values("bucket_start_utc")
        w52 = comp.tail(N_WEEKS_52W)
        full_peak = float(comp["value_rescaled"].max())
        zero_52w = float((w52["value_rescaled"] == 0).mean())
        zero_full = float((comp["value_rescaled"] == 0).mean())
        rows.append({
            "character_key": key,
            "term": term,
            "batch": batch,
            "full_peak": full_peak,
            "zero_52w": zero_52w,
            "zero_full": zero_full,
            "censored_scoring": is_censored(full_peak, zero_52w),
            "censored_momentum": is_censored(full_peak, zero_full),
        })
    return pd.DataFrame(rows)
