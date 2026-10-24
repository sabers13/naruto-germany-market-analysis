"""Kleinanzeigen.de lane (ANALYSIS_PLAN.md section 4).

Dedupe by ad_id (already unique in the archive). Primary metric: distinct
offer ads (is_wanted = false); wanted ads reported separately. Median
price_eur excludes price_suspect and price types other than fixed/negotiable.
Regions: offer-ad counts per state x character, plus _all = tagged offer ads.
"""
from __future__ import annotations

import duckdb
import pandas as pd
import yaml

from nga import characters
from nga.paths import REPO, dataset

from . import (
    ALL_KEYS,
    clip,
    count_rows,
    is_solo,
    map_tags,
    median_or_none,
    parse_json_tags,
    sha1,
)

SOURCE = "kleinanzeigen"
PRICE_TYPES = {"fixed", "negotiable"}


def load_listings() -> pd.DataFrame:
    con = duckdb.connect()
    return con.execute(
        "SELECT ad_id, title, price_eur, price_type, price_suspect, is_wanted, "
        "character_tags, state FROM read_parquet(?)",
        [str(dataset("kleinanzeigen", "raw", "final", "listings.parquet"))],
    ).df()


def prepare(listings: pd.DataFrame) -> pd.DataFrame:
    """Dedupe by ad_id; map tags; flag priced offer ads."""
    ads = listings.drop_duplicates("ad_id", keep="first").reset_index(drop=True)
    ads["keys"] = ads["character_tags"].apply(lambda r: map_tags(parse_json_tags(r), SOURCE))
    ads["raw_tags"] = ads["character_tags"].apply(parse_json_tags)
    ads["is_offer"] = ads["is_wanted"] == False  # noqa: E712
    ads["priced"] = (
        ads["is_offer"]
        & (ads["price_suspect"] == False)  # noqa: E712
        & ads["price_type"].isin(PRICE_TYPES)
        & ads["price_eur"].notna()
    )
    return ads


def attribute(ads: pd.DataFrame) -> dict[str, dict[str, int]]:
    keys = characters.keys()
    offer = {k: 0 for k in keys}
    solo = {k: 0 for k in keys}
    wanted = {k: 0 for k in keys}
    offers = ads[ads["is_offer"]]
    for _, row in offers.iterrows():
        tagset = row["keys"] & ALL_KEYS
        for key in tagset:
            offer[key] += 1
        for key in keys:
            if is_solo(row["keys"], key):
                solo[key] += 1
    for _, row in ads[~ads["is_offer"]].iterrows():
        for key in row["keys"] & ALL_KEYS:
            wanted[key] += 1
    return {"offer": offer, "solo": solo, "wanted": wanted}


def build_matches(ads: pd.DataFrame) -> pd.DataFrame:
    sm = characters.source_map(SOURCE)
    rows = []
    for _, row in ads.iterrows():
        matched: dict[str, str] = {}
        for tag in row["raw_tags"]:
            if tag in sm:
                key = sm[tag]
                if key not in matched or tag < matched[key]:
                    matched[key] = tag
        for key in sorted(matched):
            rows.append({
                "record_hash": sha1(str(row["ad_id"])),
                "source": SOURCE,
                "character_key": key,
                "matched_on": matched[key],
                "snippet": clip(row["title"]),
            })
    return pd.DataFrame(rows, columns=["record_hash", "source", "character_key", "matched_on", "snippet"])


def build_metrics(ads: pd.DataFrame) -> pd.DataFrame:
    attr = attribute(ads)
    rows: list[dict] = []
    rows += count_rows(SOURCE, "offer_ads", attr["offer"], primary=True)
    rows += count_rows(SOURCE, "solo_offer_ads", attr["solo"])
    rows += count_rows(SOURCE, "wanted_ads", attr["wanted"])
    for key in characters.keys():
        sub = ads[ads["is_offer"] & ads["keys"].apply(lambda s: key in s) & ads["priced"]]
        med, n = median_or_none(sub["price_eur"])
        if med is not None:
            rows.append({
                "character_key": key, "source": SOURCE, "metric": "median_price_eur",
                "period": "snapshot", "region": "DE", "value": med, "n": n,
                "unit": "eur", "evidence_class": "A", "lens": "shoppers",
                "primary": False, "lane": "shops",
            })
    offers = ads[ads["is_offer"]]
    all_n = int(offers[offers["keys"].apply(bool)].shape[0])
    rows += count_rows(SOURCE, "offer_ads", {"_all": all_n}, primary=False)
    return pd.DataFrame(rows)


def build_regions(ads: pd.DataFrame) -> pd.DataFrame:
    """Offer-ad counts per state x character (+ _all); explicit zeros included."""
    states = yaml.safe_load((REPO / "config/states.yaml").read_text())
    offers = ads[ads["is_offer"]]
    rows = []
    for state_name, info in states.items():
        sub = offers[offers["state"] == state_name]
        for key in characters.keys():
            n = int(sub[sub["keys"].apply(lambda s: key in s)].shape[0])
            rows.append({"state_code": info["code"], "state_name": state_name,
                         "character_key": key, "ads": n})
        rows.append({"state_code": info["code"], "state_name": state_name,
                     "character_key": "_all", "ads": int(sub[sub["keys"].apply(bool)].shape[0])})
    return pd.DataFrame(rows, columns=["state_code", "state_name", "character_key", "ads"])


def build_prices(ads: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key in characters.keys():
        sub = ads[ads["is_offer"] & ads["keys"].apply(lambda s: key in s) & ads["priced"]]
        med, n = median_or_none(sub["price_eur"])
        if med is not None:
            rows.append({"character_key": key, "platform": "kleinanzeigen",
                         "median_eur": med, "n": n})
    return pd.DataFrame(rows, columns=["character_key", "platform", "median_eur", "n"])


def run() -> dict[str, pd.DataFrame]:
    ads = prepare(load_listings())
    return {
        "entities": ads,
        "metrics": build_metrics(ads),
        "matches": build_matches(ads),
        "regions": build_regions(ads),
        "prices": build_prices(ads),
        "total_ads": pd.DataFrame([{"ads": int(ads.shape[0])}]),
    }
