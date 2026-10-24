"""eBay.de lane (ANALYSIS_PLAN.md section 4).

naruto_relevant only. Dedupe by item_id keeping the newest observed_at
(no observed_at ties in the archive). Live = newest observation is live_*;
historical = historical_card. Median prices exclude prices > EUR 5,000.
Merch mix maps merch_category to the 6 contract categories.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from nga import characters
from nga.paths import dataset

from . import (
    ALL_KEYS,
    MERCH_CATEGORIES,
    MERCH_MAP,
    clip,
    count_rows,
    is_solo,
    map_tags,
    median_or_none,
    parse_json_tags,
    sha1,
)

SOURCE = "ebay"
PRICE_CAP = 5000.0


def load_observations() -> pd.DataFrame:
    con = duckdb.connect()
    # NB: `.df()` triggers a Pandas4Warning from a deprecated pandas
    # `inplace` drop inside duckdb's own conversion; the arrow round-trip
    # below returns identical values/dtypes/columns without the warning.
    return (
        con.sql(
            "SELECT item_id, observed_at, observation_type, title, price_value, "
            "character_matches, merch_category, naruto_relevant "
            "FROM read_parquet(?)",
            params=[str(dataset("ebay", "data", "ebay_de_observations.parquet"))],
        )
        .to_arrow_table()
        .to_pandas()
    )


def dedupe_items(obs: pd.DataFrame) -> pd.DataFrame:
    """Relevant observations only; newest observation per item_id."""
    rel = obs[obs["naruto_relevant"] == True].copy()  # noqa: E712
    rel["observed_at"] = pd.to_datetime(rel["observed_at"], utc=True)
    rel = rel.sort_values(["observed_at", "item_id"], ascending=[False, True])
    rel = rel.drop_duplicates("item_id", keep="first").reset_index(drop=True)
    rel["keys"] = rel["character_matches"].apply(lambda r: map_tags(parse_json_tags(r), SOURCE))
    rel["raw_tags"] = rel["character_matches"].apply(parse_json_tags)
    rel["is_live"] = rel["observation_type"].astype(str).str.startswith("live")
    rel["price_capped"] = rel["price_value"].where(
        (rel["price_value"].isna()) | (rel["price_value"] <= PRICE_CAP))
    rel["merch"] = rel["merch_category"].apply(lambda c: MERCH_MAP.get(c, "other"))
    return rel


def attribute(items: pd.DataFrame) -> dict[str, dict[str, int]]:
    keys = characters.keys()
    counts = {k: 0 for k in keys}
    solo = {k: 0 for k in keys}
    live = {k: 0 for k in keys}
    historical = {k: 0 for k in keys}
    for _, row in items.iterrows():
        tagset = row["keys"] & ALL_KEYS
        for key in tagset:
            counts[key] += 1
            if row["is_live"]:
                live[key] += 1
            else:
                historical[key] += 1
        for key in keys:
            if is_solo(row["keys"], key):
                solo[key] += 1
    return {"counts": counts, "solo": solo, "live": live, "historical": historical}


def build_matches(items: pd.DataFrame) -> pd.DataFrame:
    sm = characters.source_map(SOURCE)
    rows = []
    for _, row in items.iterrows():
        matched: dict[str, str] = {}
        for tag in row["raw_tags"]:
            if tag in sm:
                key = sm[tag]
                if key not in matched or tag < matched[key]:
                    matched[key] = tag
        for key in sorted(matched):
            rows.append({
                "record_hash": sha1(str(row["item_id"])),
                "source": SOURCE,
                "character_key": key,
                "matched_on": matched[key],
                "snippet": clip(row["title"]),
            })
    return pd.DataFrame(rows, columns=["record_hash", "source", "character_key", "matched_on", "snippet"])


def _median_row(key: str, values: pd.Series, metric: str) -> dict | None:
    med, n = median_or_none(values)
    if med is None:
        return None
    return {
        "character_key": key, "source": SOURCE, "metric": metric,
        "period": "snapshot", "region": "DE", "value": med, "n": n,
        "unit": "eur", "evidence_class": "A", "lens": "shoppers",
        "primary": False, "lane": "shops",
    }


def build_metrics(items: pd.DataFrame) -> pd.DataFrame:
    attr = attribute(items)
    rows: list[dict] = []
    rows += count_rows(SOURCE, "items", attr["counts"], primary=True)
    rows += count_rows(SOURCE, "solo_items", attr["solo"])
    rows += count_rows(SOURCE, "items_live", attr["live"])
    rows += count_rows(SOURCE, "items_historical", attr["historical"])
    for key in characters.keys():
        sub = items[items["keys"].apply(lambda s: key in s)]
        for metric, frame in [("median_price_eur", sub),
                              ("median_price_eur_live", sub[sub["is_live"]]),
                              ("median_price_eur_historical", sub[~sub["is_live"]])]:
            row = _median_row(key, frame["price_capped"], metric)
            if row is not None:
                rows.append(row)
    all_n = int(items[items["keys"].apply(bool)].shape[0])
    rows += count_rows(SOURCE, "items", {"_all": all_n}, primary=False)
    return pd.DataFrame(rows)


def build_merch(items: pd.DataFrame) -> pd.DataFrame:
    """One row per (character, category); all 6 categories for every char with >= 1 item."""
    rows = []
    for key in characters.keys():
        sub = items[items["keys"].apply(lambda s: key in s)]
        if len(sub) == 0:
            continue
        counts = sub["merch"].value_counts()
        for cat in MERCH_CATEGORIES:
            rows.append({"character_key": key, "category": cat,
                         "items": int(counts.get(cat, 0))})
    return pd.DataFrame(rows, columns=["character_key", "category", "items"])


def build_prices(items: pd.DataFrame) -> pd.DataFrame:
    """Median asking prices per stratum; n = priced records behind the median."""
    rows = []
    for key in characters.keys():
        sub = items[items["keys"].apply(lambda s: key in s)]
        for platform, frame in [("ebay", sub), ("ebay_live", sub[sub["is_live"]]),
                                ("ebay_historical", sub[~sub["is_live"]])]:
            med, n = median_or_none(frame["price_capped"])
            if med is not None:
                rows.append({"character_key": key, "platform": platform,
                             "median_eur": med, "n": n})
    return pd.DataFrame(rows, columns=["character_key", "platform", "median_eur", "n"])


def run() -> dict[str, pd.DataFrame]:
    obs = load_observations()
    items = dedupe_items(obs)
    return {
        "entities": items,
        "metrics": build_metrics(items),
        "matches": build_matches(items),
        "merch": build_merch(items),
        "prices": build_prices(items),
        "total_items": pd.DataFrame([{"items": int(items.shape[0])}]),
        "total_items_before_filter": pd.DataFrame(
            [{"items": int(obs["item_id"].nunique())}]),
    }
