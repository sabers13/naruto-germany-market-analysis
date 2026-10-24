"""the trends lane pipeline: rescale weekly Trends series, write metrics + momentum.

Reads the read-only archive in place; writes work/ files only.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nga import metrics
from nga.paths import check_archive, dataset, work
from nga.trends import (ANCHOR_TERM, MISSING, N_WEEKS_52W, REFERENCE_BATCH,
                        SERIES, SNAPSHOT_DATE)
from nga.trends.bridge import NoDirectAnchor, bridge_factor_k, rescale_series
from nga.trends.censoring import censoring_table
from nga.trends.momentum import change_12m, complete_weeks, quarterly_means


def load_weekly() -> pd.DataFrame:
    ts = pd.read_parquet(
        dataset("google_trends", "raw", "20261022T1000Z__full", "out",
                "parquet", "timeseries.parquet"),
        columns=["batch_id", "term_raw", "bucket_start_utc", "value",
                 "is_partial", "resolution", "geo", "gprop", "timeframe_resolved"])
    return ts.loc[(ts["resolution"] == "WEEK") & (ts["geo"] == "DE")
                  & (ts["gprop"] == "") & (ts["timeframe_resolved"] == "2021-10-22 2026-10-22")].copy()


def run() -> dict:
    check_archive()
    weekly = load_weekly()

    # Bucket grids must line up across batches or means are not comparable.
    grids = weekly.groupby("batch_id")["bucket_start_utc"].apply(lambda s: tuple(sorted(s.unique())))
    assert grids.nunique() == 1, f"weekly bucket grids differ across batches: {grids.nunique()}"

    ref_df = weekly.loc[weekly["batch_id"] == REFERENCE_BATCH]
    assert len(ref_df) > 0, f"reference batch {REFERENCE_BATCH} not found"

    metric_rows: list[dict] = []
    momentum_rows: list[dict] = []
    factors: dict[str, float] = {}
    corr_inputs: dict[str, pd.Series] = {}

    # Corrected censoring test (§12, 2026-10-23): a censored series is
    # missing in interest_52w scoring (plan §4) and flagged "censored" in
    # momentum. The change_12m row is kept (secondary, never scored).
    censored = censoring_table(weekly).set_index("character_key")

    for key, term, kind, batch, flag in SERIES:
        bdf = weekly.loc[weekly["batch_id"] == batch]
        assert term in set(bdf["term_raw"]), f"{term} not in {batch}"
        try:
            k = 1.0 if batch == REFERENCE_BATCH else bridge_factor_k(ref_df, bdf, ANCHOR_TERM)
        except NoDirectAnchor as e:
            raise RuntimeError(f"STOP: {key} cannot reach {REFERENCE_BATCH} without chaining: {e}")
        factors[key] = k

        s = rescale_series(bdf, term, k)
        assert len(s) >= 200, f"{key}: only {len(s)} weekly points (< 200)"
        comp = complete_weeks(s, SNAPSHOT_DATE)
        last52 = comp.sort_values("bucket_start_utc").tail(N_WEEKS_52W)
        assert len(last52) == N_WEEKS_52W, f"{key}: {len(last52)} complete weeks, need 52"
        interest_52w = float(last52["value_rescaled"].mean())
        corr_inputs[key] = comp.set_index("bucket_start_utc")["value_rescaled"]

        q = quarterly_means(comp)
        assert q["period"].min() == "2021-10" and q["period"].max() == "2026-07", \
            f"{key}: quarter range {q['period'].min()}..{q['period'].max()}"
        assert len(q) == 20, f"{key}: {len(q)} quarters, need 20"
        chg = change_12m(q)
        n_q_weeks = int(q.tail(8)["n_weeks"].sum())

        for _, r in q.iterrows():
            momentum_rows.append({"character_key": key, "period": r["period"],
                                  "value": float(r["value"]), "series_kind": kind,
                                  "flag": ("censored" if bool(censored.loc[key, "censored_momentum"])
                                           else flag)})
        if not bool(censored.loc[key, "censored_scoring"]):
            metric_rows.append({"character_key": key, "source": "google_trends",
                                "metric": "interest_52w", "period": "last_52w", "region": "DE",
                                "value": interest_52w, "n": N_WEEKS_52W, "unit": "index",
                                "evidence_class": "A", "lens": "watching",
                                "primary": True, "lane": "trends"})
        metric_rows.append({"character_key": key, "source": "google_trends",
                            "metric": "change_12m", "period": "snapshot", "region": "DE",
                            "value": chg * 100.0, "n": n_q_weeks, "unit": "pct",
                            "evidence_class": "A", "lens": "watching",
                            "primary": False, "lane": "trends"})

    metrics.write(pd.DataFrame(metric_rows), "trends")
    mom = pd.DataFrame(momentum_rows,
                       columns=["character_key", "period", "value", "series_kind", "flag"])
    mom.to_parquet(work("aux", "momentum.parquet"), index=False)

    write_regions(weekly)

    n_ts = int(sum(len(complete_weeks(rescale_series(
        weekly.loc[weekly["batch_id"] == b], t, factors[k]), SNAPSHOT_DATE))
        for k, t, _, b, _ in SERIES))
    sources = [{"id": "google_trends:timeseries", "records": n_ts, "in_score": True},
               {"id": "google_trends:geo", "records": int(len(regions_count())), "in_score": False}]
    with open(work("aux", "sources_trends.json"), "w") as f:
        json.dump(sources, f, indent=2)

    # Sanity: rescaled Sasuke topic vs rescaled Sasuke plain term, same shape?
    sasuke_term = rescale_series(
        weekly.loc[weekly["batch_id"] == "characters_core__w5y__b01"], "Sasuke",
        bridge_factor_k(ref_df, weekly.loc[weekly["batch_id"] == "characters_core__w5y__b01"], ANCHOR_TERM))
    st = sasuke_term.set_index("bucket_start_utc")["value_rescaled"]
    aligned = pd.concat([corr_inputs["sasuke_uchiha"], st], axis=1, join="inner").dropna()
    corr = float(aligned.corr().iloc[0, 1])

    return {"factors": factors, "missing": MISSING, "sasuke_topic_term_corr": corr,
            "n_series": len(SERIES), "sources": sources,
            "censored_scoring": sorted(censored.index[censored["censored_scoring"]].tolist()),
            "censored_momentum": sorted(censored.index[censored["censored_momentum"]].tolist())}


def regions_count() -> pd.DataFrame:
    return pd.read_parquet(
        dataset("google_trends", "raw", "20261022T1000Z__full", "out",
                "parquet", "geo.parquet"), columns=["geo_code"])


def write_regions(weekly: pd.DataFrame) -> None:
    """Within-batch regional shares; the two geo metric types kept separate."""
    from nga.paths import REPO
    import yaml
    states = yaml.safe_load((REPO / "config/states.yaml").read_text())
    codes = {v["code"] for v in states.values()} if isinstance(next(iter(states.values())), dict) else set(states.values())
    geo = pd.read_parquet(
        dataset("google_trends", "raw", "20261022T1000Z__full", "out",
                "parquet", "geo.parquet"),
        columns=["batch_id", "term_raw", "geo_code", "geo_metric", "value"])
    out = pd.DataFrame({"state_code": geo["geo_code"].str.removeprefix("DE-"),
                        "batch_id": geo["batch_id"],
                        "term": geo["term_raw"], "metric": geo["geo_metric"],
                        "value": geo["value"].astype(float)})
    assert set(out["metric"]) == {"share_of_compared_terms_pct", "relative_index_0_100"}, \
        f"unexpected geo metric types: {set(out['metric'])}"
    if codes:
        assert set(out["state_code"]) <= codes, "unknown state code in geo"
    out.to_parquet(work("aux", "trends_regions.parquet"), index=False)


def main() -> None:
    summary = run()
    print(f"reference batch: {REFERENCE_BATCH} (anchor {ANCHOR_TERM!r})")
    for key, k in summary["factors"].items():
        print(f"  bridge_factor_k[{key}] = {k:.6f}")
    print(f"missing: {sorted(summary['missing'])}")
    print(f"sasuke topic-vs-term correlation: {summary['sasuke_topic_term_corr']:.4f}")


if __name__ == "__main__":
    main()
