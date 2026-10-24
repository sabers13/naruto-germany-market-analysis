"""Synthetic tests for single-hop anchor rescaling (no archive needed)."""
import pandas as pd
import pytest

from nga.trends.bridge import (NoDirectAnchor, anchor_mean, bridge_factor_k,
                               rescale_series)


def frame(rows):
    return pd.DataFrame(rows, columns=["bucket_start_utc", "term_raw", "value", "is_partial"])


def test_rescaling_recovers_a_known_ratio_exactly():
    weeks = [f"2026-0{i}-0{j}" for i in (1, 2) for j in (4, 5)]
    ref = frame([{"bucket_start_utc": w, "term_raw": t, "value": v, "is_partial": False}
                 for w, v in zip(weeks, [40.0, 60.0])
                 for t, v in ([("Naruto", v), ("Sasuke", v / 2)])])
    assert len(ref) == 4
    other = frame([{"bucket_start_utc": w, "term_raw": t, "value": v, "is_partial": False}
                   for w, v in zip(weeks, [20.0, 30.0])
                   for t, v in ([("Naruto", v), ("Sasuke", v / 2)])])
    k = bridge_factor_k(ref, other, "Naruto")
    assert k == pytest.approx(2.0)
    s = rescale_series(other, "Sasuke", k)
    assert list(s["value_rescaled"]) == pytest.approx([20.0, 30.0])


def test_reference_batch_has_factor_one():
    df = frame([{"bucket_start_utc": "2026-01-04", "term_raw": "Naruto",
                 "value": 80.0, "is_partial": False}])
    assert bridge_factor_k(df, df, "Naruto") == pytest.approx(1.0)


def test_chained_rescale_candidate_is_refused():
    # C shares "Sasuke" with B and B shares the anchor with ref, but C has no
    # anchor: a chain C→B→ref must be refused, not built.
    ref = frame([{"bucket_start_utc": "2026-01-04", "term_raw": t, "value": v, "is_partial": False}
                 for t, v in [("Naruto", 50.0), ("Sasuke", 10.0)]])
    chained = frame([{"bucket_start_utc": "2026-01-04", "term_raw": t, "value": v, "is_partial": False}
                     for t, v in [("Sasuke", 20.0), ("Gaara", 4.0)]])
    with pytest.raises(NoDirectAnchor):
        bridge_factor_k(ref, chained, "Naruto")


def test_missing_anchor_in_reference_is_refused():
    other = frame([{"bucket_start_utc": "2026-01-04", "term_raw": "Naruto",
                    "value": 50.0, "is_partial": False}])
    empty_ref = other.iloc[0:0]
    with pytest.raises(NoDirectAnchor):
        bridge_factor_k(empty_ref, other, "Naruto")


def test_degenerate_anchor_scale_is_refused():
    ref = frame([{"bucket_start_utc": "2026-01-04", "term_raw": "Naruto",
                  "value": 50.0, "is_partial": False}])
    flat = frame([{"bucket_start_utc": "2026-01-04", "term_raw": "Naruto",
                   "value": 0.0, "is_partial": False}])
    with pytest.raises(NoDirectAnchor):
        anchor_mean(flat, "Naruto")
    with pytest.raises(NoDirectAnchor):
        bridge_factor_k(ref, flat, "Naruto")


def test_partial_buckets_excluded_from_anchor_mean():
    df = frame([{"bucket_start_utc": "2026-01-04", "term_raw": "Naruto",
                 "value": 50.0, "is_partial": False},
                {"bucket_start_utc": "2026-01-11", "term_raw": "Naruto",
                 "value": 100.0, "is_partial": True}])
    assert anchor_mean(df, "Naruto") == pytest.approx(50.0)
