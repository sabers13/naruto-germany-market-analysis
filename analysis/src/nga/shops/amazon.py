"""Amazon.de lane (ANALYSIS_PLAN.md section 4).

Dedupe by ASIN; character = keys in character_matches split on '; '.
An ASIN counts for a character if ANY of its cards names it (113 ASINs have
cards with conflicting tags, almost always tagged card vs untagged card).
Per-ASIN price/review = median across its cards (nearly always constant).
Title = most frequent card title (ties: lexicographically smallest).
"""
from __future__ import annotations

import duckdb
import pandas as pd

from nga import characters
from nga.paths import dataset

from . import (
    ALL_KEYS,
    clip,
    count_rows,
    is_solo,
    map_tags,
    median_or_none,
    sha1,
    split_amazon_tags,
)

SOURCE = "amazon"


def load_cards() -> pd.DataFrame:
    con = duckdb.connect()
    return con.execute(
        "SELECT asin, title, price_value, review_count, character_matches "
        "FROM read_parquet(?)",
        [str(dataset("amazon", "out", "amazon_search_cards.parquet"))],
    ).df()


def dedupe_cards(cards: pd.DataFrame) -> pd.DataFrame:
    """One row per ASIN with unioned canonical tags."""
    sm_keys = set(characters.source_map(SOURCE).keys())
    _ = sm_keys  # mapping applied via map_tags; kept explicit for clarity
    rows = []
    for asin, group in cards.groupby("asin", sort=True):
        tags: set[str] = set()
        for raw in group["character_matches"]:
            tags |= map_tags(split_amazon_tags(raw), SOURCE)
        titles = group["title"].dropna().astype(str)
        if len(titles):
            vc = titles.value_counts()
            title = sorted(vc[vc == vc.max()].index)[0]
        else:
            title = ""
        price, _ = median_or_none(group["price_value"])
        reviews, _ = median_or_none(group["review_count"])
        raw_tags = sorted({t for raw in group["character_matches"] for t in split_amazon_tags(raw)})
        rows.append({
            "asin": asin,
            "title": title,
            "price_value": price,
            "review_count": reviews,
            "keys": tags,
            "raw_tags": raw_tags,
        })
    return pd.DataFrame(rows)


def attribute(asins: pd.DataFrame) -> dict[str, dict[str, int | float]]:
    """Per-character counts (entities, not rows)."""
    keys = [k for k in characters.keys()]  # 14 locked keys, benchmark first
    counts = {k: 0 for k in keys}
    solo = {k: 0 for k in keys}
    for tagset in asins["keys"]:
        for key in tagset & ALL_KEYS:
            counts[key] += 1
        for key in keys:
            if is_solo(tagset, key):
                solo[key] += 1
    return {"counts": counts, "solo": solo}


def build_matches(asins: pd.DataFrame) -> pd.DataFrame:
    """One row per (ASIN, character): record_hash, source, character, tag, snippet."""
    sm = characters.source_map(SOURCE)
    rows = []
    for _, row in asins.iterrows():
        matched: dict[str, str] = {}
        for tag in row["raw_tags"]:
            if tag in sm:
                key = sm[tag]
                if key not in matched or tag < matched[key]:
                    matched[key] = tag
        for key in sorted(matched):
            rows.append({
                "record_hash": sha1(str(row["asin"])),
                "source": SOURCE,
                "character_key": key,
                "matched_on": matched[key],
                "snippet": clip(row["title"]),
            })
    return pd.DataFrame(rows, columns=["record_hash", "source", "character_key", "matched_on", "snippet"])


def build_metrics(asins: pd.DataFrame) -> pd.DataFrame:
    attr = attribute(asins)
    rows: list[dict] = []
    rows += count_rows(SOURCE, "asins", attr["counts"], primary=True)
    rows += count_rows(SOURCE, "solo_asins", attr["solo"])
    for key in characters.keys():
        tagset = asins[asins["keys"].apply(lambda s: key in s)]
        med_rev, n_rev = median_or_none(tagset["review_count"])
        if med_rev is not None:
            rows.append({
                "character_key": key, "source": SOURCE, "metric": "median_reviews",
                "period": "snapshot", "region": "DE", "value": med_rev, "n": n_rev,
                "unit": "count", "evidence_class": "D", "lens": "shoppers",
                "primary": False, "lane": "shops",
            })
        med_price, n_price = median_or_none(tagset["price_value"])
        if med_price is not None:
            rows.append({
                "character_key": key, "source": SOURCE, "metric": "median_price_eur",
                "period": "snapshot", "region": "DE", "value": med_price, "n": n_price,
                "unit": "eur", "evidence_class": "A", "lens": "shoppers",
                "primary": False, "lane": "shops",
            })
    tagged = {k: v for k, v in attr["counts"].items()}
    all_n = int(asins[asins["keys"].apply(bool)].shape[0])
    rows += count_rows(SOURCE, "asins", {"_all": all_n}, primary=False)
    _ = tagged
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    cards = load_cards()
    asins = dedupe_cards(cards)
    return {
        "entities": asins,
        "metrics": build_metrics(asins),
        "matches": build_matches(asins),
        "total_asins": pd.DataFrame([{"asins": int(asins.shape[0])}]),
    }
