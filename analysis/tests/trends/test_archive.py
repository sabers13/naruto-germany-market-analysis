"""Archive tests for the trends lane: aggregate assertions only, never row content."""
import pandas as pd
import pytest

from nga.paths import archive, dataset
from nga.trends import ANCHOR_TERM, REFERENCE_BATCH, SERIES
from nga.trends.bridge import anchor_mean, bridge_factor_k

archive_present = pytest.mark.skipif(not archive().exists(), reason="data archive not on disk")


@pytest.mark.archive
@archive_present
def test_every_chosen_series_has_at_least_200_weekly_points():
    ts = pd.read_parquet(
        dataset("google_trends", "raw", "20261022T1000Z__full", "out",
                "parquet", "timeseries.parquet"),
        columns=["batch_id", "term_raw", "resolution", "geo", "gprop", "timeframe_resolved"])
    w = ts.loc[(ts["resolution"] == "WEEK") & (ts["geo"] == "DE")
               & (ts["gprop"] == "") & (ts["timeframe_resolved"] == "2021-10-22 2026-10-22")]
    for _, term, _, batch, _ in SERIES:
        n = int(((w["batch_id"] == batch) & (w["term_raw"] == term)).sum())
        assert n >= 200, (term, batch, n)


@pytest.mark.archive
@archive_present
def test_single_reference_reaches_every_chosen_batch_directly():
    vals = pd.read_parquet(
        dataset("google_trends", "raw", "20261022T1000Z__full", "out",
                "parquet", "timeseries.parquet"),
        columns=["batch_id", "term_raw", "value", "is_partial",
                 "resolution", "geo", "gprop", "timeframe_resolved"])
    w = vals.loc[(vals["resolution"] == "WEEK") & (vals["geo"] == "DE")
                 & (vals["gprop"] == "") & (vals["timeframe_resolved"] == "2021-10-22 2026-10-22")]
    ref = w.loc[w["batch_id"] == REFERENCE_BATCH]
    batches = {b for _, _, _, b, _ in SERIES}
    assert REFERENCE_BATCH in batches
    for b in sorted(batches - {REFERENCE_BATCH}):
        k = bridge_factor_k(ref, w.loc[w["batch_id"] == b], ANCHOR_TERM)
        assert k > 0, (b, k)


@pytest.mark.archive
@archive_present
def test_anchor_is_dominant_in_every_chosen_batch():
    vals = pd.read_parquet(
        dataset("google_trends", "raw", "20261022T1000Z__full", "out",
                "parquet", "timeseries.parquet"),
        columns=["batch_id", "term_raw", "value", "is_partial",
                 "resolution", "geo", "gprop", "timeframe_resolved"])
    w = vals.loc[(vals["resolution"] == "WEEK") & (vals["geo"] == "DE")
                 & (vals["gprop"] == "") & (vals["timeframe_resolved"] == "2021-10-22 2026-10-22")]
    for b in sorted({b for _, _, _, b, _ in SERIES}):
        peak = w.loc[(w["batch_id"] == b) & (w["term_raw"] == ANCHOR_TERM), "value"].max()
        assert peak >= 40, (b, peak)  # docs §6.3: anchor dominant, never at 4
        assert anchor_mean(w.loc[w["batch_id"] == b], ANCHOR_TERM) > 0


@pytest.mark.archive
@archive_present
def test_geo_covers_16_states_with_two_unmixed_metric_types():
    geo = pd.read_parquet(
        dataset("google_trends", "raw", "20261022T1000Z__full", "out",
                "parquet", "geo.parquet"),
        columns=["batch_id", "term_raw", "geo_code", "geo_metric"])
    assert set(geo["geo_metric"]) == {"share_of_compared_terms_pct", "relative_index_0_100"}
    per = geo.groupby(["batch_id", "term_raw"])["geo_code"].nunique()
    assert (per == 16).all(), per[per != 16].to_dict()


@pytest.mark.archive
@archive_present
def test_corrected_censoring_censors_exactly_the_seven_term_series():
    """Production outcome (aggregate only): the 4 topic series are
    analysable; the 7 plain-term series are censored in both windows."""
    from nga.trends.__main__ import load_weekly
    from nga.trends.censoring import censoring_table

    table = censoring_table(load_weekly()).set_index("character_key")
    for key in ("sasuke_uchiha", "itachi_uchiha", "kakashi_hatake",
                "hinata_hyuga", "naruto_uzumaki"):
        assert bool(table.loc[key, "censored_scoring"]) is False, key
        assert bool(table.loc[key, "censored_momentum"]) is False, key
    assert (sorted(table.index[table["censored_scoring"]].tolist())
            == ["gaara", "jiraiya", "madara_uchiha", "minato_namikaze",
                "obito_uchiha", "orochimaru", "tsunade"])
    assert (sorted(table.index[table["censored_momentum"]].tolist())
            == ["gaara", "jiraiya", "madara_uchiha", "minato_namikaze",
                "obito_uchiha", "orochimaru", "tsunade"])
