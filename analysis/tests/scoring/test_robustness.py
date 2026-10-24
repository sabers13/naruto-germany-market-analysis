"""Tests for robustness.py and the end-to-end fixture (hand-computed)."""

import json

import pandas as pd
import pytest
from jsonschema import Draft202012Validator

from nga import paths
from nga.scoring import robustness as B
from nga.scoring import score

from .synth import FIXTURE_ENTRIES, H, I, K, S, metrics_frame, precision_frame


def _judges(cols):
    """Build a subjects x judges rank frame from column lists."""
    return pd.DataFrame(
        {f"j{k}": v for k, v in enumerate(cols)},
        index=[f"s{i}" for i in range(len(cols[0]))],
    )


def test_kendall_w_perfect_agreement_is_one():
    ranks = _judges([[1, 2, 3, 4], [1, 2, 3, 4], [1, 2, 3, 4]])
    w, n = B.kendall_w(ranks)
    assert w == pytest.approx(1.0)
    assert n == 4
    assert B.agreement_label(w) == "strong"


def test_kendall_w_small_example():
    # Hand computation: R = (2, 5, 5), mean = 4, S = 6, denom = 4*24 = 96.
    ranks = _judges([[1, 2, 3], [1, 3, 2]])
    w, n = B.kendall_w(ranks)
    assert w == pytest.approx(72 / 96)  # 0.75
    assert n == 3
    assert B.agreement_label(w) == "strong"


def test_kendall_w_tie_correction():
    # Judge A ties s1/s2 at 1.5. S = 6.5; tie term = 8-2 = 6;
    # denom = 4*24 - 2*6 = 84.
    ranks = _judges([[1.5, 1.5, 3], [1, 2, 3]])
    w, _ = B.kendall_w(ranks)
    assert w == pytest.approx(78 / 84)
    # Without the correction the answer would be 78/96 = 0.8125.
    assert w != pytest.approx(78 / 96)


def test_kendall_w_degenerate_inputs():
    w, n = B.kendall_w(_judges([[1]]))
    assert (w, n) == (0.0, 1)
    w, n = B.kendall_w(_judges([[1, 2, 3]]))
    assert w == 0.0 and n == 3


def test_agreement_label_boundaries():
    assert B.agreement_label(0.0) == "weak"
    assert B.agreement_label(0.2999) == "weak"
    assert B.agreement_label(0.3) == "moderate"
    assert B.agreement_label(0.6) == "moderate"
    assert B.agreement_label(0.6001) == "strong"


def test_fixture_main_ranking():
    result = score(metrics_frame(FIXTURE_ENTRIES))
    rows = result.characters.set_index("character_key")
    assert list(result.characters["character_key"]) == [S, I, K, H]
    assert list(result.characters["rank"]) == [1, 2, 3, 4]
    assert rows.loc[S, "score"] == pytest.approx(1.0)
    assert rows.loc[I, "score"] == pytest.approx(2.0)
    assert rows.loc[K, "score"] == pytest.approx(3.4666667)
    assert rows.loc[H, "score"] == pytest.approx(3.5333333)
    assert rows.loc[S, "index"] == 100
    assert rows.loc[I, "index"] == 92
    assert rows.loc[K, "index"] == 79
    assert rows.loc[H, "index"] == 79
    assert rows.loc[S, "top3_sources"] == 7
    assert rows.loc[I, "top3_sources"] == 7
    assert rows.loc[K, "top3_sources"] == 3
    assert rows.loc[H, "top3_sources"] == 3


def test_fixture_leave_one_out():
    result = score(metrics_frame(FIXTURE_ENTRIES))
    loo = result.robustness["leave_one_out"]
    assert loo["runs"] == 7
    assert loo["top3"] == [S, I, K]
    # Hand-verified: dropping amazon, ebay or google_trends promotes H to 3rd;
    # the other four drops keep {S, I, K}.
    assert loo["same_top3"] == 4
    by_drop = {r["dropped"]: r["top3"] for r in result.detail["loo_runs"]}
    assert len(by_drop) == 7
    for dropped in ("amazon", "ebay", "google_trends"):
        assert by_drop[dropped] == [S, I, H], dropped
    for dropped in (
        "kleinanzeigen",
        "youtube",
        "anime2you",
        "narutop99",
    ):
        assert by_drop[dropped] == [S, I, K], dropped


def test_fixture_alt_weights():
    result = score(metrics_frame(FIXTURE_ENTRIES))
    alts = {a["name"]: a for a in result.robustness["alt_weights"]}
    assert set(alts) == {"equal", "shoppers_only", "german_only"}
    # Equal weights tie K/H at 3.5; shoppers lens rank breaks it for K.
    assert alts["equal"]["top3"] == [S, I, K]
    assert alts["equal"]["same_top3"] is True
    assert alts["shoppers_only"]["top3"] == [S, I, K]
    assert alts["shoppers_only"]["same_top3"] is True
    assert alts["german_only"]["top3"] == [S, I, K]
    assert alts["german_only"]["same_top3"] is True
    assert alts["german_only"]["weights"] == {
        "shoppers": 0.625,
        "watching": 0.375,
        "votes": 0.0,
    }


def test_fixture_confidence_labels():
    result = score(metrics_frame(FIXTURE_ENTRIES))
    rows = result.characters.set_index("character_key")
    # S and I survive every perturbation; K falls out of 3 LOO runs; H is 4th.
    assert rows.loc[S, "confidence"] == "robust"
    assert rows.loc[I, "confidence"] == "robust"
    assert rows.loc[K, "confidence"] == "mixed"
    assert rows.loc[H, "confidence"] == "mixed"


def test_label_confidence_one_source():
    assert (
        B.label_confidence("x", ["a", "b", "c"], 0, 0, 3, 7, 1) == "one_source"
    )
    # Rank 6 or better is not "buried": mixed.
    assert B.label_confidence("x", ["a", "b", "c"], 0, 0, 3, 6, 1) == "mixed"
    # Top-3 in two sources is not "one source".
    assert B.label_confidence("x", ["a", "b", "c"], 0, 0, 3, 9, 2) == "mixed"
    # Unscored characters get null.
    assert B.label_confidence("x", ["a", "b", "c"], 0, 0, 3, None, 0) is None
    # Robust needs all three conditions.
    assert B.label_confidence("a", ["a", "b", "c"], 7, 3, 3, 1, 5) == "robust"
    assert B.label_confidence("a", ["a", "b", "c"], 5, 3, 3, 1, 5) == "mixed"


def test_fixture_kendall_detail():
    result = score(metrics_frame(FIXTURE_ENTRIES))
    assert result.detail["n_complete"] == 4
    assert result.robustness["agreement_label"] == "strong"
    assert 0.0 <= result.robustness["kendall_w"] <= 1.0


def test_robustness_matches_contract_shape():
    result = score(metrics_frame(FIXTURE_ENTRIES))
    rob = result.robustness
    assert set(rob) == {"kendall_w", "agreement_label", "leave_one_out", "alt_weights"}
    assert set(rob["leave_one_out"]) == {"runs", "same_top3", "top3"}
    for alt in rob["alt_weights"]:
        assert set(alt) == {"name", "weights", "top3", "same_top3"}
        assert set(alt["weights"]) == {"shoppers", "watching", "votes"}
    schema = json.loads(
        (paths.REPO / "contract/dashboard.schema.json").read_text()
    )
    validator = Draft202012Validator(
        {
            "type": "object",
            "properties": {"robustness": schema["properties"]["robustness"]},
            "$defs": schema["$defs"],
        }
    )
    validator.validate({"robustness": rob})


def test_kendall_w_gappy_ranks_stays_in_unit_interval():
    # the pipeline regression: on real data some (source, character) cells are
    # excluded by precision, so the complete-case frame carries rank gaps
    # (e.g. amazon [1,2,3,4,6] when one candidate is excluded). Ranking the
    # gaps directly is not Kendall's W (it can exceed 1 and violates the
    # contract schema's [0, 1] range); the complete cases must be re-ranked.
    ranks = _judges([[1, 2, 3, 5, 6], [1, 3, 2, 4, 5], [2, 1, 3, 4, 5]])
    w, n = B.kendall_w(ranks)
    assert n == 5
    assert 0.0 <= w <= 1.0


def test_score_with_excluded_cell_kendall_w_valid():
    # End to end through score(): excluding one cell via precision must not
    # produce an out-of-range Kendall's W.
    entries = list(FIXTURE_ENTRIES)
    prec = precision_frame([("amazon", H, 0.5, "exclude")])
    result = score(metrics_frame(entries), precision_df=prec)
    w = result.robustness["kendall_w"]
    assert 0.0 <= w <= 1.0


def test_headline_sources_exclude_google_trends():
    from nga.scoring.rank import IN_SCORE_SOURCES

    assert "google_trends" not in B.HEADLINE_SOURCES
    assert set(B.HEADLINE_SOURCES) == set(IN_SCORE_SOURCES) - {"google_trends"}


def test_kendall_dual_values_and_complete_sets():
    # §12 amendment 2026-10-23 §7.7: (a) over the 6 headline sources,
    # (b) over all 7. google_trends missing for s2/s3 grows the (a) set.
    from nga.scoring.rank import IN_SCORE_SOURCES

    frame = pd.DataFrame(
        {
            "amazon": [1, 2, 3, 4],
            "ebay": [1, 2, 3, 4],
            "kleinanzeigen": [1, 2, 3, 4],
            "youtube": [1, 2, 3, 4],
            "google_trends": [1.0, 2.0, float("nan"), float("nan")],
            "anime2you": [1, 2, 3, 4],
            "narutop99": [1, 2, 3, 4],
        },
        index=["s0", "s1", "s2", "s3"],
    )
    dual = B.kendall_dual(frame)
    assert dual["n_headline"] == 4
    assert dual["w_headline"] == pytest.approx(1.0)
    assert dual["n_all7"] == 2
    w_direct, n_direct = B.kendall_w(frame[list(IN_SCORE_SOURCES)])
    assert dual["w_all7"] == pytest.approx(w_direct)
    assert dual["n_all7"] == n_direct


def test_score_headline_carries_contract_fields():
    # Contract unchanged: robustness.kendall_w + agreement_label carry (a).
    result = score(metrics_frame(FIXTURE_ENTRIES))
    ranks = result.source_ranks.set_index("character_key")
    w_head, n_head = B.kendall_w(ranks[list(B.HEADLINE_SOURCES)])
    assert result.robustness["kendall_w"] == pytest.approx(w_head)
    assert result.robustness["agreement_label"] == B.agreement_label(w_head)
    assert result.detail["n_complete"] == n_head


def test_score_trends_exclusion_grows_headline_set():
    # Excluding a google_trends cell shrinks the all-7 set but not (a).
    prec = precision_frame([("google_trends", H, 0.5, "exclude")])
    result = score(metrics_frame(FIXTURE_ENTRIES), precision_df=prec)
    assert result.detail["n_complete"] == 4
    assert result.detail["n_complete_all7"] == 3
    assert 0.0 <= result.detail["kendall_w_all7"] <= 1.0
    assert 0.0 <= result.robustness["kendall_w"] <= 1.0
    # The label follows (a), not (b).
    assert result.robustness["agreement_label"] == B.agreement_label(
        result.robustness["kendall_w"]
    )
