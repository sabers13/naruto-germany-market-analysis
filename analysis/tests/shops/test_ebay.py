"""eBay unit tests (synthetic) + archive reconciliation tests."""
import pandas as pd
import pytest

from nga import characters
from nga.paths import dataset
from nga.shops import ebay

archive_present = pytest.mark.skipif(
    not dataset("ebay", "data", "ebay_de_observations.parquet").exists(),
    reason="data archive not on disk")


def _obs(rows):
    return pd.DataFrame(rows, columns=["item_id", "observed_at", "observation_type",
                                       "title", "price_value", "character_matches",
                                       "merch_category", "naruto_relevant"])


def test_relevant_only_and_newest_wins():
    obs = _obs([
        ("I1", "2024-11-26 23:48:41+01:00", "historical_card", "Old title", 10.0,
         '["sasuke_uchiha"]', "figure", True),
        ("I1", "2026-10-22 10:40:52+02:00", "live_active_card", "New title", 12.0,
         '["sasuke_uchiha"]', "figure", True),
        ("I2", "2026-10-22 10:40:52+02:00", "live_active_card", "Irrelevant", 5.0,
         "[]", "other", False),
    ])
    items = ebay.dedupe_items(obs)
    assert len(items) == 1
    assert items.iloc[0]["title"] == "New title"
    assert items.iloc[0]["is_live"] == True  # noqa: E712


def test_live_historical_split_and_price_cap():
    obs = _obs([
        ("I1", "2026-10-22 10:40:52+02:00", "live_active_card", "T1", 6000.0,
         '["gaara"]', "figure", True),
        ("I2", "2026-10-22 10:40:52+02:00", "live_active_card", "T2", 20.0,
         '["gaara"]', "figure", True),
        ("I3", "2024-11-26 23:48:41+01:00", "historical_card", "T3", 30.0,
         '["gaara"]', "figure", True),
    ])
    items = ebay.dedupe_items(obs)
    attr = ebay.attribute(items)
    assert attr["counts"]["gaara"] == 3  # outlier kept in counts
    assert attr["live"]["gaara"] == 2
    assert attr["historical"]["gaara"] == 1
    m = ebay.build_metrics(items)
    med = m[(m["character_key"] == "gaara") & (m["metric"] == "median_price_eur")].iloc[0]
    assert med["value"] == pytest.approx(25.0)  # 6000 excluded from median
    assert med["n"] == 2


def test_merch_mapping_covers_contract_categories():
    obs = _obs([
        ("I1", "2026-10-22 10:40:52+02:00", "live_active_card", "T1", 1.0,
         '["sasuke_uchiha"]', "funko", True),
        ("I2", "2026-10-22 10:40:52+02:00", "live_active_card", "T2", 1.0,
         '["sasuke_uchiha"]', "cosplay", True),
        ("I3", "2024-11-26 23:48:41+01:00", "historical_card", "T3", 1.0,
         '["sasuke_uchiha"]', "trading_cards", True),
        ("I4", "2024-11-26 23:48:41+01:00", "historical_card", "T4", 1.0,
         '["sasuke_uchiha"]', "manga", True),
        ("I5", "2024-11-26 23:48:41+01:00", "historical_card", "T5", 1.0,
         '["sasuke_uchiha"]', "plush", True),
        ("I6", "2024-11-26 23:48:41+01:00", "historical_card", "T6", 1.0,
         '["sasuke_uchiha"]', "other", True),
    ])
    merch = ebay.build_merch(ebay.dedupe_items(obs))
    got = dict(zip(merch["category"], merch["items"]))
    assert got == {"figures": 1, "clothing": 1, "cards": 1,
                   "manga_media": 1, "accessories": 1, "other": 1}


def test_unknown_merch_category_maps_to_other():
    assert ebay.MERCH_MAP.get("mystery_gadget", "other") == "other"


@archive_present
@pytest.mark.archive
def test_archive_item_totals_within_1pc():
    import duckdb
    con = duckdb.connect()
    parquet = str(dataset("ebay", "data", "ebay_de_observations.parquet"))
    total = con.execute("SELECT COUNT(DISTINCT item_id) FROM read_parquet(?)",
                        [parquet]).fetchone()[0]
    assert abs(total - 8801) / 8801 <= 0.01, total
    rel = con.execute("SELECT COUNT(DISTINCT item_id) FROM read_parquet(?) "
                      "WHERE naruto_relevant", [parquet]).fetchone()[0]
    assert abs(rel - 8331) / 8331 <= 0.01, rel


@archive_present
@pytest.mark.archive
def test_archive_every_candidate_has_items():
    items = ebay.dedupe_items(ebay.load_observations())
    attr = ebay.attribute(items)
    missing = [k for k in characters.keys("candidate") if attr["counts"][k] == 0]
    assert missing == []
