"""Synthetic tests for quarterly momentum and change_12m (no archive needed)."""
import pandas as pd
import pytest

from nga.trends.momentum import (change_12m, complete_weeks, quarter_start,
                                 quarterly_means)


def weekly(values_by_monday):
    rows = [{"bucket_start_utc": d, "value_raw": v, "value_rescaled": v, "is_partial": False}
            for d, v in values_by_monday.items()]
    return pd.DataFrame(rows)


def test_quarter_start_mapping():
    assert quarter_start(pd.Timestamp("2021-10-17", tz="UTC")) == "2021-10"
    assert quarter_start(pd.Timestamp("2021-12-31", tz="UTC")) == "2021-10"
    assert quarter_start(pd.Timestamp("2022-01-02", tz="UTC")) == "2022-01"
    assert quarter_start(pd.Timestamp("2026-09-27", tz="UTC")) == "2026-07"


def test_partial_newest_quarter_dropped_and_change_arithmetic():
    # 8 full quarters at value 10, then 4 at value 12, then a partial Q4-2026.
    mondays = pd.date_range("2024-10-07", "2026-09-27", freq="W-MON", tz="UTC")
    vals = {}
    for d in mondays:
        p = quarter_start(d)
        vals[d.isoformat()] = 10.0 if p < "2025-10" else 12.0
    # partial week inside 2026-Q4: must not leak into the quarters
    vals["2026-10-26T00:00:00+00:00"] = 999.0
    df = weekly(vals)
    df.loc[df["bucket_start_utc"] == "2026-10-26T00:00:00+00:00", "is_partial"] = True
    comp = complete_weeks(df, "2026-10-22")
    assert "2026-10-26T00:00:00+00:00" not in set(comp["bucket_start_utc"].astype(str))
    q = quarterly_means(comp)
    assert q["period"].max() == "2026-07"
    assert "2026-10" not in set(q["period"])
    assert len(q) == 8
    assert change_12m(q) == pytest.approx(12.0 / 10.0 - 1)


def test_complete_weeks_drops_buckets_past_snapshot_even_if_unflagged():
    df = weekly({"2026-10-11T00:00:00+00:00": 5.0, "2026-10-18T00:00:00+00:00": 7.0})
    comp = complete_weeks(df, "2026-10-22")
    assert len(comp) == 1  # week of Oct 18 ends Oct 25, past the snapshot


def test_change_12m_needs_eight_quarters():
    q = pd.DataFrame({"period": ["2026-01", "2026-04", "2026-07"], "value": [1.0, 1.0, 1.0]})
    with pytest.raises(ValueError):
        change_12m(q)


def test_change_12m_undefined_on_zero_base():
    q = pd.DataFrame({"period": [f"2024-{m:02d}" for m in (10,)] + [f"2025-{m:02d}" for m in (1, 4, 7, 10)] +
                      [f"2026-{m:02d}" for m in (1, 4, 7)],
                      "value": [0.0] * 8})
    with pytest.raises(ValueError):
        change_12m(q)
