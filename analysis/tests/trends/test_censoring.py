"""Tests for the corrected censoring check (ANALYSIS_PLAN.md §12, 2026-10-23).

Synthetic frames (no archive) pin the definition; one archive test pins the
production outcome (aggregate assertion, no row content).
"""

import pandas as pd
import pytest

from nga.trends import ANCHOR_TERM, REFERENCE_BATCH
from nga.trends.censoring import PEAK_FLOOR, ZERO_SHARE_LIMIT, censoring_table, is_censored

OTHER_BATCH = "characters_core__w5y__b02"
TERM = "Madara"
MADARA_ENTRY = ("madara_uchiha", TERM, "query", OTHER_BATCH, "term_series")


def weekly_frame(term_vals, anchor_vals=None):
    """Two batches on a weekly grid ending before the 2026-10-22 snapshot."""
    starts = pd.date_range(end="2026-10-18", periods=len(term_vals),
                           freq="7D", tz="UTC")
    anchor_vals = [50.0] * len(term_vals) if anchor_vals is None else anchor_vals
    rows = [{"batch_id": REFERENCE_BATCH, "term_raw": ANCHOR_TERM,
             "bucket_start_utc": t, "value": float(v), "is_partial": False}
            for t, v in zip(starts, anchor_vals)]
    rows += [{"batch_id": OTHER_BATCH, "term_raw": ANCHOR_TERM,
              "bucket_start_utc": t, "value": 50.0, "is_partial": False}
             for t in starts]
    rows += [{"batch_id": OTHER_BATCH, "term_raw": TERM,
              "bucket_start_utc": t, "value": float(v), "is_partial": False}
             for t, v in zip(starts, term_vals)]
    return pd.DataFrame(rows)


def madara_row(weekly):
    table = censoring_table(weekly, entries=[MADARA_ENTRY])
    return table.set_index("character_key").loc["madara_uchiha"]


def test_thresholds():
    assert is_censored(PEAK_FLOOR - 0.1, 0.0) is True
    assert is_censored(PEAK_FLOOR, 0.0) is False  # 10.0 is not < 10
    assert is_censored(100.0, ZERO_SHARE_LIMIT + 0.01) is True
    assert is_censored(100.0, ZERO_SHARE_LIMIT) is False  # exactly 30% is fine


def test_peak_is_over_full_window_not_52w():
    # Last-52-week peak is 5 (< 10) but the full-window peak is 50:
    # analysable under the corrected test (the anchor pins recent peaks).
    vals = [50.0] * 48 + [5.0] * 52
    row = madara_row(weekly_frame(vals))
    assert row["full_peak"] == pytest.approx(50.0)
    assert bool(row["censored_scoring"]) is False
    assert bool(row["censored_momentum"]) is False


def test_zero_share_uses_window_in_use():
    # Full-window peak is 50 (fine) and full-window zeros are 26/100, but
    # the last 52 weeks are half zero: censored for scoring, analysable
    # for momentum.
    vals = [50.0] * 22 + [4.0] * 26 + [0.0] * 26 + [4.0] * 26
    row = madara_row(weekly_frame(vals))
    assert row["full_peak"] == pytest.approx(50.0)
    assert bool(row["censored_scoring"]) is True
    assert bool(row["censored_momentum"]) is False


def test_low_peak_censors_both_windows():
    vals = [5.0] * 100
    row = madara_row(weekly_frame(vals))
    assert bool(row["censored_scoring"]) is True
    assert bool(row["censored_momentum"]) is True
