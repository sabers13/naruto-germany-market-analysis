"""Quarterly momentum from rescaled weekly series (ANALYSIS_PLAN.md §4/§8).

- Quarters run 2021-Q4 → last complete quarter (2026-Q3); the partial
  2026-Q4 is dropped.
- change_12m = mean(last 4 complete quarters) / mean(4 before) − 1.
"""
from __future__ import annotations

import pandas as pd

FIRST_QUARTER_START = "2021-10"
LAST_QUARTER_START = "2026-07"


def complete_weeks(df: pd.DataFrame, snapshot_date: str) -> pd.DataFrame:
    """Drop the partial newest bucket and any bucket reaching past snapshot."""
    out = df.copy()
    out["bucket_start_utc"] = pd.to_datetime(out["bucket_start_utc"], utc=True)
    week_end = out["bucket_start_utc"] + pd.Timedelta(days=7)
    snap = pd.Timestamp(snapshot_date, tz="UTC")
    return out.loc[(~out["is_partial"]) & (week_end <= snap)].copy()


def quarter_start(ts: pd.Timestamp) -> str:
    qm = 3 * ((ts.month - 1) // 3) + 1
    return f"{ts.year}-{qm:02d}"


def quarterly_means(weekly: pd.DataFrame) -> pd.DataFrame:
    """Quarterly means of rescaled values; only full quarters in range."""
    wk = weekly.copy()
    wk["period"] = wk["bucket_start_utc"].map(quarter_start)
    q = wk.groupby("period", as_index=False).agg(value=("value_rescaled", "mean"),
                                                  n_weeks=("value_rescaled", "size"))
    return q.loc[(q["period"] >= FIRST_QUARTER_START)
                 & (q["period"] <= LAST_QUARTER_START)].sort_values("period").reset_index(drop=True)


def change_12m(quarters: pd.DataFrame) -> float:
    """Fractional change: mean(last 4 complete quarters)/mean(4 before) − 1."""
    q = quarters.sort_values("period").reset_index(drop=True)
    if len(q) < 8:
        raise ValueError(f"need 8 quarters for change_12m, have {len(q)}")
    recent = q["value"].iloc[-4:].mean()
    prev = q["value"].iloc[-8:-4].mean()
    if prev <= 0:
        raise ValueError(f"change_12m undefined: previous-4-quarter mean is {prev}")
    return float(recent / prev - 1)
