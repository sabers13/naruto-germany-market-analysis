"""Tests for the §13 benchmark comparison (synthetic; no archive, no network)."""

import json

import pytest
from jsonschema import validate

from nga.benchmark.compare import (
    SOURCE_SPECS,
    compare,
    franchise_correlation,
)

from .synth import (
    ITACHI,
    NARUTO,
    SASUKE,
    base_metrics,
    base_precision,
    correlated_weeks,
    metrics_frame,
    precision_frame,
    uncorrelated_weeks,
    weekly_frame,
)


def run_compare(metrics_df=None, precision_df=None, weekly=None):
    metrics_df = base_metrics() if metrics_df is None else metrics_df
    precision_df = base_precision() if precision_df is None else precision_df
    if weekly is None:
        n, f = correlated_weeks()
        weekly = weekly_frame(n, f)
    return compare(metrics_df, precision_df, weekly)


def source_of(doc, spec_id):
    return next(s for s in doc["sources"] if s["id"] == spec_id)


# --- §13 rule 1–5: each rule fires -------------------------------------------


def test_each_rule_fires_with_production_shaped_inputs():
    doc = run_compare()
    assert (source_of(doc, "kleinanzeigen")["comparable"],
            source_of(doc, "kleinanzeigen")["reason"]) == (False, "alias_restricted")
    assert (source_of(doc, "narutop99")["comparable"],
            source_of(doc, "narutop99")["reason"]) == (True, "vote")
    assert (source_of(doc, "anime2you_comments")["comparable"],
            source_of(doc, "anime2you_comments")["reason"]) == (False, "alias_restricted")
    assert (source_of(doc, "anime2you_articles")["comparable"],
            source_of(doc, "anime2you_articles")["reason"]) == (False, "not_measured")
    trends = source_of(doc, "google_trends")
    assert (trends["comparable"], trends["reason"]) == (False, "franchise_dominated")
    assert trends["detail"].startswith("r = ")
    assert (source_of(doc, "amazon")["comparable"],
            source_of(doc, "amazon")["reason"]) == (False, "precision_low")
    assert source_of(doc, "amazon")["detail"] == "Naruto precision 0.74"
    assert (source_of(doc, "ebay")["comparable"],
            source_of(doc, "ebay")["reason"]) == (False, "precision_low")
    assert source_of(doc, "ebay")["detail"] == "Naruto precision 0.66"
    assert (source_of(doc, "youtube_comments")["comparable"],
            source_of(doc, "youtube_comments")["reason"]) == (False, "precision_uncertain")
    assert (source_of(doc, "youtube_comments")["detail"]
            == "Naruto precision 0.93, 95% CI from 0.69 (n = 14)")
    assert (source_of(doc, "youtube_videos")["comparable"],
            source_of(doc, "youtube_videos")["reason"]) == (False, "not_measured")


def test_nine_sources_in_contract_enum_order():
    doc = run_compare()
    assert [s["id"] for s in doc["sources"]] == [s["id"] for s in SOURCE_SPECS]
    assert doc["benchmark"] == NARUTO


# --- rule order: first match wins --------------------------------------------


def test_kleinanzeigen_alias_restricted_whatever_its_precision():
    # §12 2026-10-23: the tagger narrows Naruto, so even perfect precision
    # cannot make Kleinanzeigen comparable.
    prec = precision_frame([("kleinanzeigen", NARUTO, 0.99, "use")])
    doc = run_compare(precision_df=prec)
    assert (source_of(doc, "kleinanzeigen")["comparable"],
            source_of(doc, "kleinanzeigen")["reason"]) == (False, "alias_restricted")


def test_alias_restricted_beats_precision_rule():
    # Even perfect anime2you Naruto precision cannot compare comment mentions.
    prec = precision_frame([("anime2you", NARUTO, 0.99, "use")])
    doc = run_compare(precision_df=prec)
    assert (source_of(doc, "anime2you_comments")["comparable"],
            source_of(doc, "anime2you_comments")["reason"]) == (False, "alias_restricted")


def test_precision_rule_fires_when_no_earlier_rule_matches():
    prec = precision_frame([("amazon", NARUTO, 0.95, "use")])
    n, f = correlated_weeks()
    doc = run_compare(precision_df=prec, weekly=weekly_frame(n, f))
    assert (source_of(doc, "amazon")["comparable"],
            source_of(doc, "amazon")["reason"]) == (True, "precision_ok")


def test_precision_with_wide_interval_is_uncertain():
    prec = precision_frame([("amazon", NARUTO, 0.95, "use", 0.80, 20)])
    doc = run_compare(precision_df=prec)
    amazon = source_of(doc, "amazon")
    assert (amazon["comparable"], amazon["reason"]) == (False, "precision_uncertain")
    assert amazon["detail"] == "Naruto precision 0.95, 95% CI from 0.80 (n = 20)"


def test_precision_ok_needs_lower_bound_at_threshold():
    prec = precision_frame([("amazon", NARUTO, 0.97, "use", 0.90, 200)])
    doc = run_compare(precision_df=prec)
    assert (source_of(doc, "amazon")["comparable"],
            source_of(doc, "amazon")["reason"]) == (True, "precision_ok")


def test_missing_naruto_precision_row_is_not_measured():
    prec = precision_frame([("amazon", SASUKE, 1.0, "use")])  # no Naruto row
    doc = run_compare(precision_df=prec)
    assert (source_of(doc, "amazon")["comparable"],
            source_of(doc, "amazon")["reason"]) == (False, "not_measured")


# --- rule 4: franchise correlation -------------------------------------------


def test_trends_comparable_when_correlation_below_threshold():
    n, f = uncorrelated_weeks()
    r, _ = franchise_correlation(weekly_frame(n, f))
    assert r is not None and r < 0.90
    doc = run_compare(weekly=weekly_frame(n, f))
    trends = source_of(doc, "google_trends")
    assert trends["comparable"] is True
    assert trends["reason"] == "franchise_dominated"
    assert trends["detail"].startswith(f"r = {r:.2f} between search term 'Naruto'")
    assert "Naruto topic /m/02sp46 censored" in trends["detail"]
    assert len(trends["detail"]) <= 120


def test_trends_detail_names_series_and_censored_topic():
    # §12 amendment: the detail states the series actually used and
    # records that Naruto's character topic /m/02sp46 is censored.
    n, f = correlated_weeks()
    r, _ = franchise_correlation(weekly_frame(n, f))
    doc = run_compare()
    detail = source_of(doc, "google_trends")["detail"]
    assert detail == (f"r = {r:.2f} between search term 'Naruto' and franchise "
                      "topic; Naruto topic /m/02sp46 censored")
    assert len(detail) <= 120


def test_trends_not_measured_when_franchise_missing():
    n, _ = correlated_weeks()
    weekly = weekly_frame(n, [0.0] * len(n)).query("term_raw != '/m/01hryy'")
    r, _ = franchise_correlation(weekly)
    assert r is None
    doc = run_compare(weekly=weekly)
    trends = source_of(doc, "google_trends")
    assert (trends["comparable"], trends["reason"]) == (False, "not_measured")


def test_trends_not_measured_when_franchise_batch_has_no_anchor():
    n, f = correlated_weeks()
    weekly = weekly_frame(n, f, franchise_batch="other__b99", with_anchor=False)
    r, _ = franchise_correlation(weekly)
    assert r is None  # no chained rescale: refused, not approximated
    doc = run_compare(weekly=weekly)
    assert source_of(doc, "google_trends")["comparable"] is False


def test_trends_bridges_single_hop_from_another_batch():
    n, f = correlated_weeks()
    weekly = weekly_frame(n, f, franchise_batch="other__b99", with_anchor=True)
    r, batch = franchise_correlation(weekly)
    assert batch == "other__b99"
    assert r is not None and r > 0.90


# --- values: treated candidates over raw Naruto, rounding, nulls -------------


def test_vote_ratio_and_kept_benchmark_values():
    doc = run_compare()
    assert doc["by_character"][ITACHI]["ratios"]["narutop99"] == 3.7
    # Not comparable, but Naruto's own value is still reported.
    assert source_of(doc, "kleinanzeigen")["benchmark_value"] == 536.0
    assert doc["by_character"][SASUKE]["ratios"]["kleinanzeigen"] is None


def test_ratios_use_precision_treated_candidate_values():
    # Kakashi amazon is adjusted (0.8947…); the ratio must use 494.79,
    # not the raw 553.
    m = metrics_frame([
        (NARUTO, "amazon", "asins", 100.0, True),
        ("kakashi_hatake", "amazon", "asins", 553.0, True),
    ])
    prec = precision_frame([
        ("amazon", NARUTO, 0.97, "use", 0.92, 200),
        ("amazon", "kakashi_hatake", 0.8947368421052632, "adjust"),
    ])
    n, f = correlated_weeks()
    doc = compare(m, prec, weekly_frame(n, f))
    assert doc["by_character"]["kakashi_hatake"]["ratios"]["amazon"] == 4.95


def test_excluded_candidate_cell_gives_null_ratio():
    m = metrics_frame([
        (NARUTO, "youtube", "comments_de", 3880.0, True),
        (SASUKE, "youtube", "comments_de", 1405.0, True),
        (ITACHI, "youtube", "comments_de", 1104.0, True),
    ])
    prec = precision_frame([
        ("youtube", NARUTO, 0.93, "use"),
        ("youtube", SASUKE, 0.40, "exclude"),
    ])
    n, f = correlated_weeks()
    doc = compare(m, prec, weekly_frame(n, f))
    assert doc["by_character"][SASUKE]["ratios"]["youtube_comments"] is None
    assert doc["by_character"][SASUKE]["comparable_sources"] == 0
    assert doc["by_character"][ITACHI]["ratios"]["youtube_comments"] == 0.28


def test_missing_naruto_value_gives_null_ratio_and_null_benchmark():
    m = base_metrics()
    m = m[~((m["character_key"] == NARUTO) & (m["metric"] == "votes_eu"))]
    doc = run_compare(metrics_df=m)
    assert source_of(doc, "narutop99")["benchmark_value"] is None
    assert source_of(doc, "narutop99")["comparable"] is True
    assert doc["by_character"][SASUKE]["ratios"]["narutop99"] is None


def test_non_comparable_sources_have_null_ratios():
    doc = run_compare()
    for char, body in doc["by_character"].items():
        for spec_id in ("amazon", "ebay", "kleinanzeigen", "youtube_comments",
                        "youtube_videos", "google_trends",
                        "anime2you_comments", "anime2you_articles"):
            assert body["ratios"][spec_id] is None, (char, spec_id)


def test_benchmark_value_rounding():
    doc = run_compare()
    assert source_of(doc, "google_trends")["benchmark_value"] == 37.73


# --- ahead_in / comparable_sources / candidate-only --------------------------


def test_ahead_in_counts_ratios_at_or_above_one():
    doc = run_compare()
    sasuke = doc["by_character"][SASUKE]
    # Sasuke narutop99 is 34797/34959 = 0.9954: displays as 1.00 but the
    # UNROUNDED ratio is below 1.00, so it does NOT count as ahead (§12).
    assert sasuke["ratios"]["narutop99"] == 1.0
    assert sasuke["comparable_sources"] == 1
    assert sasuke["ahead_in"] == 0
    itachi = doc["by_character"][ITACHI]
    assert itachi["ahead_in"] == 1  # only narutop99 3.70


def test_ahead_in_uses_unrounded_ratio():
    # 1.004 displays as 1.00 yet counts as ahead; 0.9954 does not.
    m = metrics_frame([
        (NARUTO, "narutop99", "votes_eu", 1000.0, True),
        ("gaara", "narutop99", "votes_eu", 1004.0, True),
        (SASUKE, "narutop99", "votes_eu", 995.4, True),
    ])
    n, f = correlated_weeks()
    doc = compare(m, base_precision(), weekly_frame(n, f))
    assert doc["by_character"]["gaara"]["ratios"]["narutop99"] == 1.0
    assert doc["by_character"]["gaara"]["ahead_in"] == 1
    assert doc["by_character"][SASUKE]["ratios"]["narutop99"] == 1.0
    assert doc["by_character"][SASUKE]["ahead_in"] == 0


def test_by_character_holds_candidates_only():
    from nga import characters
    doc = run_compare()
    assert sorted(doc["by_character"]) == sorted(characters.keys("candidate"))
    assert NARUTO not in doc["by_character"]


def test_detail_strings_fit_contract_limit():
    doc = run_compare()
    for s in doc["sources"]:
        assert len(s["detail"]) <= 120, s


def test_synthetic_output_validates_against_contract():
    schema = json.load(open("contract/dashboard.schema.json"))
    doc = run_compare()
    validate({"benchmark_comparison": doc}, {
        "type": "object",
        "properties": {"benchmark_comparison": schema["properties"]["benchmark_comparison"]},
        "$defs": schema["$defs"],
    })
