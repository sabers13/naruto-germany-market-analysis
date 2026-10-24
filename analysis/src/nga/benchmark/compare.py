"""Fair benchmark comparison with Naruto (ANALYSIS_PLAN.md §13).

Comparability is decided by the §13 rules in order (first match wins); the
``reason`` names the deciding rule and ``comparable`` carries the outcome.
Candidate values are the precision-treated primaries scoring uses
(reused from ``nga.scoring.rank``, never duplicated); Naruto's benchmark
values are his raw counts (he is never ranked, so §6 never treats him —
this matches the §13 wording example: 666/536 = 124%).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nga import characters
from nga.scoring import rank as _rank
from nga.trends import ANCHOR_TERM, N_WEEKS_52W, REFERENCE_BATCH, SERIES, SNAPSHOT_DATE
from nga.trends.bridge import NoDirectAnchor, bridge_factor_k, rescale_series
from nga.trends.momentum import complete_weeks

BENCHMARK = _rank.BENCHMARK  # "naruto_uzumaki"

#: Franchise topic for §13 rule 4.
FRANCHISE_TOPIC = "/m/01hryy"

#: Naruto's own series as used in the release (§13 rule 4 reading, §12 entry
#: 2026-10-23): the plain search term (his character topic /m/02sp46 is
#: censored in the archive), on the shared the trends lane reference scale.
NARUTO_TERM = "Naruto"
NARUTO_TOPIC = "/m/02sp46"

#: §13 rule 4 threshold: r >= 0.90 means searches for "Naruto" are
#: franchise-dominated and the series is NOT comparable.
FRANCHISE_R_THRESHOLD = 0.90

#: §13 rule 5 threshold for Naruto's own keyword precision; since the §12
#: entry of 2026-10-23 it applies to the 95% CI lower bound as well.
PRECISION_THRESHOLD = 0.90

#: The nine benchmark sources, in contract enum order.
#: ``source``/``metric`` locate the value in the metrics long table;
#: ``score_source`` is the in-score source column (None when the metric is
#: secondary and takes no §6 treatment).
SOURCE_SPECS: tuple[dict[str, str | None], ...] = (
    {"id": "amazon", "source": "amazon", "metric": "asins", "score_source": "amazon"},
    {"id": "ebay", "source": "ebay", "metric": "items", "score_source": "ebay"},
    {"id": "kleinanzeigen", "source": "kleinanzeigen", "metric": "offer_ads",
     "score_source": "kleinanzeigen"},
    {"id": "youtube_comments", "source": "youtube", "metric": "comments_de",
     "score_source": "youtube"},
    {"id": "youtube_videos", "source": "youtube", "metric": "videos_de",
     "score_source": None},
    {"id": "google_trends", "source": "google_trends", "metric": "interest_52w",
     "score_source": "google_trends"},
    {"id": "anime2you_comments", "source": "anime2you", "metric": "comment_mentions",
     "score_source": "anime2you"},
    {"id": "anime2you_articles", "source": "anime2you", "metric": "articles",
     "score_source": None},
    {"id": "narutop99", "source": "narutop99", "metric": "votes_eu",
     "score_source": "narutop99"},
)

#: Precision-table source holding Naruto's row for §13 rule 5.
NARUTO_PRECISION_SOURCE: dict[str, str | None] = {
    "amazon": "amazon",
    "ebay": "ebay",
    "youtube_comments": "youtube",
    # youtube_videos: deliberately None — no Naruto precision was measured
    # for videos (§13 rule 5), so it maps to NOT comparable / not_measured.
    "youtube_videos": None,
}


def _raw_values(metrics_df: pd.DataFrame, source: str, metric: str) -> pd.Series:
    """Raw value per character for one (source, metric); missing → NaN."""
    sub = metrics_df[(metrics_df["source"] == source) & (metrics_df["metric"] == metric)]
    if sub.duplicated("character_key").any():
        bad = sorted(sub.loc[sub.duplicated("character_key", keep=False), "character_key"].unique())
        raise ValueError(f"duplicate metric rows for {(source, metric)}: {bad}")
    return sub.set_index("character_key")["value"].astype(float)


def franchise_correlation(weekly: pd.DataFrame) -> tuple[float | None, str]:
    """Pearson r between Naruto's the trends lane series and the franchise topic.

    Both series go on the reference batch with the the trends lane anchor rescaling
    (reused from ``nga.trends``, never reimplemented); r is over the last
    52 complete weeks. Returns (r, batch_used); (None, "") when the
    franchise topic cannot reach the reference without chaining.
    """
    nar_entry = next(e for e in SERIES if e[0] == BENCHMARK)
    nar_term, nar_batch = nar_entry[1], nar_entry[3]
    ref_df = weekly.loc[weekly["batch_id"] == REFERENCE_BATCH]
    if len(ref_df) == 0:
        return None, ""
    nar_k = 1.0 if nar_batch == REFERENCE_BATCH else None
    if nar_k is None:
        try:
            nar_k = bridge_factor_k(
                ref_df, weekly.loc[weekly["batch_id"] == nar_batch], ANCHOR_TERM)
        except NoDirectAnchor:
            return None, ""
    nar = rescale_series(
        weekly.loc[weekly["batch_id"] == nar_batch], nar_term, nar_k)
    nar52 = complete_weeks(nar, SNAPSHOT_DATE).sort_values(
        "bucket_start_utc").tail(N_WEEKS_52W)

    batches = sorted(weekly.loc[weekly["term_raw"] == FRANCHISE_TOPIC, "batch_id"].unique())
    if REFERENCE_BATCH in batches:
        batches = [REFERENCE_BATCH] + [b for b in batches if b != REFERENCE_BATCH]
    for batch in batches:
        try:
            k = (1.0 if batch == REFERENCE_BATCH else bridge_factor_k(
                ref_df, weekly.loc[weekly["batch_id"] == batch], ANCHOR_TERM))
        except NoDirectAnchor:
            continue  # chaining would be needed: not a fair bridge, try next
        fr = rescale_series(weekly.loc[weekly["batch_id"] == batch], FRANCHISE_TOPIC, k)
        fr52 = complete_weeks(fr, SNAPSHOT_DATE).sort_values(
            "bucket_start_utc").tail(N_WEEKS_52W)
        if len(nar52) != N_WEEKS_52W or len(fr52) != N_WEEKS_52W:
            continue
        joined = pd.concat(
            [nar52.set_index("bucket_start_utc")["value_rescaled"],
             fr52.set_index("bucket_start_utc")["value_rescaled"]],
            axis=1, join="inner").dropna()
        if len(joined) < 2:
            continue
        return float(joined.corr().iloc[0, 1]), batch
    return None, ""


def _naruto_precision(precision_df: pd.DataFrame,
                      precision_source: str | None) -> tuple[float, float, int] | None:
    """Naruto's (precision, 95% CI lower bound, n) for a keyword source; None when not measured."""
    if precision_source is None or precision_df is None or len(precision_df) == 0:
        return None
    rows = precision_df[(precision_df["source"] == precision_source)
                        & (precision_df["character_key"] == BENCHMARK)]
    if len(rows) == 0:
        return None
    row = rows.iloc[0]
    return float(row["precision"]), float(row["ci_low"]), int(row["n"])


def _decide(spec_id: str, precision_df: pd.DataFrame,
            trends_r: float | None) -> tuple[bool, str, str]:
    """Apply the §13 rules in order (first match wins)."""
    if spec_id == "kleinanzeigen":
        # §12 (2026-10-23): the archive tagger treats plain "Naruto" as the
        # franchise and tags Naruto only on "Uzumaki"/"Naruto Uzumaki", so his
        # count is narrowed relative to the candidates (rule 3, not rule 1).
        return (False, "alias_restricted",
                "tagger counts Naruto only as 'Uzumaki' or 'Naruto Uzumaki'")
    if spec_id == "narutop99":
        return True, "vote", "direct vote counts"
    if spec_id == "anime2you_comments":
        return (False, "alias_restricted",
                "Naruto matched only as 'Naruto Uzumaki'")
    if spec_id == "anime2you_articles":
        return (False, "not_measured",
                "archive extraction; Naruto handling unknown")
    if spec_id == "google_trends":
        if trends_r is None:
            return (False, "not_measured",
                    "franchise topic not on the reference scale")
        detail = (f"r = {trends_r:.2f} between search term {NARUTO_TERM!r} "
                  f"and franchise topic; Naruto topic {NARUTO_TOPIC} censored")
        if trends_r >= FRANCHISE_R_THRESHOLD:
            return (False, "franchise_dominated", detail)
        return (True, "franchise_dominated", detail)
    # Rule 5: keyword/entity sources (amazon, ebay, youtube_comments;
    # youtube_videos has no Naruto measurement by construction).
    row = _naruto_precision(precision_df, NARUTO_PRECISION_SOURCE.get(spec_id))
    if row is None:
        return False, "not_measured", "no Naruto precision measured"
    prec, ci_low, n = row
    if prec < PRECISION_THRESHOLD:
        return False, "precision_low", f"Naruto precision {prec:.2f}"
    # §12 (2026-10-23): the lower 95% bound must also clear the threshold,
    # so a high precision from a handful of labels is not taken as certain.
    if ci_low < PRECISION_THRESHOLD:
        return (False, "precision_uncertain",
                f"Naruto precision {prec:.2f}, 95% CI from {ci_low:.2f} (n = {n})")
    return True, "precision_ok", f"Naruto precision {prec:.2f}"


def compare(metrics_df: pd.DataFrame, precision_df: pd.DataFrame,
            trends_weekly: pd.DataFrame) -> dict:
    """Build the contract's ``benchmark_comparison`` object (§13)."""
    candidates = characters.keys("candidate")

    # Precision-treated candidate primaries, exactly as scoring uses them.
    treated, _ = _rank.apply_precision(_rank.candidate_values(metrics_df), precision_df)

    trends_r, _ = franchise_correlation(trends_weekly)

    sources: list[dict] = []
    comp_ids: list[str] = []
    benchmark_value: dict[str, float | None] = {}
    for spec in SOURCE_SPECS:
        spec_id = str(spec["id"])
        raw = _raw_values(metrics_df, str(spec["source"]), str(spec["metric"]))
        nar = float(raw.get(BENCHMARK, np.nan))
        benchmark_value[spec_id] = None if np.isnan(nar) else round(nar, 2)
        comparable, reason, detail = _decide(spec_id, precision_df, trends_r)
        if comparable:
            comp_ids.append(spec_id)
        sources.append({
            "id": spec_id,
            "metric": str(spec["metric"]),
            "comparable": comparable,
            "reason": reason,
            "detail": detail[:120],
            "benchmark_value": benchmark_value[spec_id],
        })

    by_character: dict[str, dict] = {}
    for char in candidates:
        ratios: dict[str, float | None] = {}
        ahead: dict[str, bool] = {}
        for spec in SOURCE_SPECS:
            spec_id = str(spec["id"])
            entry = next(s for s in sources if s["id"] == spec_id)
            if not entry["comparable"]:
                ratios[spec_id] = None
                continue
            nar = benchmark_value[spec_id]
            if nar is None:
                ratios[spec_id] = None
                continue
            scol = spec["score_source"]
            if scol is not None:
                cand = float(treated.loc[char, str(scol)]) if char in treated.index else np.nan
            else:  # secondary metric: raw value, no §6 treatment exists
                cand = float(_raw_values(
                    metrics_df, str(spec["source"]), str(spec["metric"])).get(char, np.nan))
            if np.isnan(cand):
                ratios[spec_id] = None
            else:
                # §12 (2026-10-23): ahead_in tests the UNROUNDED ratio;
                # rounding to 2 dp is display only (0.9954 → 1.00, not ahead).
                raw_ratio = cand / nar
                ratios[spec_id] = round(raw_ratio, 2)
                ahead[spec_id] = bool(raw_ratio >= 1.00)
        non_null = [v for k, v in ratios.items()
                    if k in comp_ids and v is not None]
        by_character[char] = {
            "ratios": ratios,
            "comparable_sources": len(non_null),
            "ahead_in": sum(1 for k in ahead if ahead[k] and ratios[k] is not None),
        }
    return {"benchmark": BENCHMARK, "sources": sources, "by_character": by_character}
