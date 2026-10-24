"""Unit tests for rank.py: source ranks, lens ranks, score, index, precision."""

import math

import pandas as pd
import pytest

from nga.scoring import rank as R
from nga.scoring import score

from .synth import H, I, K, S, metrics_frame, precision_frame


def test_ties_get_average_rank():
    df = metrics_frame(
        [("a", "amazon", 10), ("b", "amazon", 10), ("c", "amazon", 5)]
    )
    ranks = R.rank_sources(R.candidate_values(df))
    assert ranks.loc["a", "amazon"] == pytest.approx(1.5)
    assert ranks.loc["b", "amazon"] == pytest.approx(1.5)
    assert ranks.loc["c", "amazon"] == pytest.approx(3.0)


def test_missing_not_ranked_and_lens_null_below_half():
    # "a" is ranked by only 1 of 3 shoppers sources -> shoppers lens null.
    df = metrics_frame(
        [
            ("a", "amazon", 10),
            ("b", "amazon", 5),
            ("b", "ebay", 5),
            ("b", "kleinanzeigen", 5),
        ]
    )
    values = R.candidate_values(df)
    ranks = R.rank_sources(values)
    assert pd.isna(ranks.loc["a", "ebay"])
    assert ranks.loc["a", "amazon"] == pytest.approx(1.0)
    lens = R.lens_ranks_from_source_ranks(ranks)
    assert pd.isna(lens.loc["a", "shoppers"])
    assert lens.loc["b", "shoppers"] == pytest.approx((2.0 + 1.0 + 1.0) / 3)


def test_lens_rank_kept_at_half_coverage():
    # 2 of 3 shoppers sources rank "a" -> 2 >= 1.5 -> lens rank kept.
    df = metrics_frame(
        [("a", "amazon", 10), ("a", "ebay", 20), ("b", "amazon", 5)]
    )
    lens = R.lens_ranks_from_source_ranks(
        R.rank_sources(R.candidate_values(df))
    )
    assert lens.loc["a", "shoppers"] == pytest.approx((1.0 + 1.0) / 2)


def test_votes_lens_null_when_narutop99_missing():
    df = metrics_frame([("a", "amazon", 10)])
    lens = R.lens_ranks_from_source_ranks(
        R.rank_sources(R.candidate_values(df))
    )
    assert pd.isna(lens.loc["a", "votes"])


def test_weights_renormalise_when_lens_null():
    # Only shoppers sources present -> score == shoppers lens rank exactly.
    df = metrics_frame(
        [
            ("a", "amazon", 30),
            ("b", "amazon", 10),
            ("a", "ebay", 30),
            ("b", "ebay", 10),
            ("a", "kleinanzeigen", 30),
            ("b", "kleinanzeigen", 10),
        ]
    )
    result = score(df)
    row = result.characters.set_index("character_key")
    assert row.loc["a", "score"] == pytest.approx(1.0)
    assert row.loc["b", "score"] == pytest.approx(2.0)
    assert row.loc["a", "index"] == 100  # (13-1)/12*100
    assert row.loc["b", "index"] == 92  # round(11/12*100) = 92


def test_index_endpoints():
    assert R.evidence_index(1.0) == 100
    assert R.evidence_index(13.0) == 0
    assert R.evidence_index(float("nan")) is None


def test_precision_adjust_changes_rank_and_flags():
    # ebay/kleinanzeigen tie so only the adjusted amazon values decide.
    df = metrics_frame(
        [
            ("a", "amazon", 100),
            ("b", "amazon", 90),
            ("a", "ebay", 50),
            ("b", "ebay", 50),
            ("a", "kleinanzeigen", 50),
            ("b", "kleinanzeigen", 50),
        ]
    )
    prec = precision_frame([("amazon", "a", 0.8, "adjust")])
    result = score(df, prec)
    rows = result.characters.set_index("character_key")
    # 100*0.8=80 < 90, so "b" takes rank 1.
    assert rows.loc["b", "rank"] == 1
    assert rows.loc["a", "rank"] == 2
    assert rows.loc["b", "shoppers"] == pytest.approx((1.0 + 1.5 + 1.5) / 3)
    assert rows.loc["a", "shoppers"] == pytest.approx((2.0 + 1.5 + 1.5) / 3)
    assert "low_precision" in rows.loc["a", "flags"]
    assert rows.loc["b", "flags"] == []


def test_precision_source_overall_row_applies_to_all_characters():
    df = metrics_frame(
        [
            ("a", "amazon", 100),
            ("b", "amazon", 90),
            ("a", "ebay", 50),
            ("b", "ebay", 50),
            ("a", "kleinanzeigen", 50),
            ("b", "kleinanzeigen", 50),
        ]
    )
    prec = precision_frame([("amazon", "_all", 0.8, "adjust")])
    result = score(df, prec)
    rows = result.characters.set_index("character_key")
    assert rows.loc["a", "rank"] == 1  # relative order kept under uniform scaling
    assert "low_precision" in rows.loc["a", "flags"]
    assert "low_precision" in rows.loc["b", "flags"]


def test_precision_specific_row_beats_overall_row():
    df = metrics_frame(
        [
            ("a", "amazon", 100),
            ("b", "amazon", 90),
            ("a", "ebay", 50),
            ("b", "ebay", 50),
            ("a", "kleinanzeigen", 50),
            ("b", "kleinanzeigen", 50),
        ]
    )
    prec = precision_frame(
        [
            ("amazon", "_all", 0.8, "adjust"),
            ("amazon", "a", 0.5, "exclude"),
        ]
    )
    result = score(df, prec)
    rows = result.characters.set_index("character_key")
    ranks = result.source_ranks.set_index("character_key")
    assert pd.isna(ranks.loc["a", "amazon"])  # excluded: treated as missing
    assert rows.loc["b", "rank"] == 1
    assert rows.loc["a", "rank"] == 2
    assert "excluded_source" in rows.loc["a", "flags"]


def test_precision_exclude_drops_value():
    df = metrics_frame(
        [
            ("a", "amazon", 100),
            ("b", "amazon", 10),
            ("a", "ebay", 100),
            ("b", "ebay", 10),
            ("a", "kleinanzeigen", 100),
            ("b", "kleinanzeigen", 10),
        ]
    )
    prec = precision_frame([("amazon", "a", 0.6, "exclude")])
    result = score(df, prec)
    ranks = result.source_ranks.set_index("character_key")
    assert pd.isna(ranks.loc["a", "amazon"])
    assert ranks.loc["b", "amazon"] == pytest.approx(1.0)
    rows = result.characters.set_index("character_key")
    assert "excluded_source" in rows.loc["a", "flags"]
    # "a" still scores from the other two shoppers sources.
    assert rows.loc["a", "shoppers"] == pytest.approx(1.0)


def test_unknown_treatment_raises():
    df = metrics_frame([("a", "amazon", 100)])
    prec = precision_frame([("amazon", "a", 0.8, "shrink")])
    with pytest.raises(ValueError):
        score(df, prec)


def test_benchmark_rows_are_ignored():
    df = metrics_frame(
        [
            ("naruto_uzumaki", "amazon", 10**9),
            ("a", "amazon", 100),
            ("b", "amazon", 10),
            ("naruto_uzumaki", "ebay", 10**9),
            ("a", "ebay", 100),
            ("b", "ebay", 10),
            ("naruto_uzumaki", "kleinanzeigen", 10**9),
            ("a", "kleinanzeigen", 100),
            ("b", "kleinanzeigen", 10),
        ]
    )
    result = score(df)
    assert "naruto_uzumaki" not in set(result.characters["character_key"])
    assert "naruto_uzumaki" not in set(result.source_ranks["character_key"])
    assert "naruto_uzumaki" not in result.robustness["leave_one_out"]["top3"]
    assert result.characters.set_index("character_key").loc["a", "rank"] == 1


def test_secondary_and_context_rows_are_ignored():
    df = metrics_frame([(S, "amazon", 40), (I, "amazon", 30)])
    extra = pd.DataFrame(
        [
            {
                "character_key": S,
                "source": "youtube",
                "metric": "videos_de",
                "period": "snapshot",
                "region": "DE",
                "value": 1.0,
                "n": 1,
                "unit": "count",
                "evidence_class": "B",
                "lens": "watching",
                "primary": False,  # secondary metric: shown, not ranked
                "lane": "fans",
            },
            {
                "character_key": S,
                "source": "wikimedia",
                "metric": "pageviews_12m",
                "period": "snapshot",
                "region": "DE",
                "value": 999999.0,
                "n": 999,
                "unit": "count",
                "evidence_class": "C",
                "lens": "context",
                "primary": True,  # primary but context lens: not in score
                "lane": "fans",
            },
        ]
    )
    result = score(pd.concat([df, extra], ignore_index=True))
    assert list(result.source_ranks.columns) == ["character_key"] + list(
        R.IN_SCORE_SOURCES
    )
    assert set(result.characters["character_key"]) == {S, I}


def test_tiebreak_shoppers_then_alphabetical():
    # X wins shoppers, Y wins watching+votes; weighted scores tie at 1.5,
    # so shoppers (not the alphabet) decides: sasuke first although
    # kakashi_hatake < sasuke_uchiha alphabetically.
    X, Y = "sasuke_uchiha", "kakashi_hatake"
    entries = []
    for s in ("amazon", "ebay", "kleinanzeigen"):
        entries += [(X, s, 100), (Y, s, 10)]
    for s in ("youtube", "google_trends", "anime2you", "narutop99"):
        entries += [(X, s, 10), (Y, s, 100)]
    result = score(metrics_frame(entries))
    rows = result.characters.set_index("character_key")
    assert rows.loc[X, "score"] == pytest.approx(rows.loc[Y, "score"])
    assert rows.loc[X, "score"] == pytest.approx(1.5)
    assert list(result.characters["character_key"]) == [X, Y]
    assert rows.loc[X, "rank"] == 1
    assert rows.loc[Y, "rank"] == 2


def test_tiebreak_alphabetical_when_lenses_tie():
    # Identical values everywhere: scores and shoppers tie -> alphabetical.
    entries = []
    for s in R.IN_SCORE_SOURCES:
        entries += [(I, s, 50), (K, s, 50)]
    result = score(metrics_frame(entries))
    assert list(result.characters["character_key"]) == [I, K]
    assert list(result.characters["rank"]) == [1, 2]


def test_duplicate_character_source_rows_raise():
    df = metrics_frame([("a", "amazon", 10), ("a", "amazon", 20)])
    with pytest.raises(ValueError):
        score(df)


def test_empty_metrics_raise():
    df = metrics_frame([("a", "amazon", 10)]).iloc[0:0]
    with pytest.raises(ValueError):
        score(df)


def test_check_precision_floor():
    R.check_precision_floor(None)
    R.check_precision_floor(
        precision_frame([("amazon", "_all", 0.50, "use")])
    )
    with pytest.raises(RuntimeError):
        R.check_precision_floor(
            precision_frame([("amazon", "_all", 0.49, "use")])
        )
    # Per-character rows alone do not trigger the source-level stop.
    R.check_precision_floor(
        precision_frame([("amazon", "a", 0.10, "exclude")])
    )
