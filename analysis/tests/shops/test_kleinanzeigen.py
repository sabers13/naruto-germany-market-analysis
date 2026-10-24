"""Kleinanzeigen unit tests (synthetic) + archive reconciliation tests."""
import pandas as pd
import pytest

from nga import characters
from nga.paths import dataset
from nga.shops import kleinanzeigen

archive_present = pytest.mark.skipif(
    not dataset("kleinanzeigen", "raw", "final", "listings.parquet").exists(),
    reason="data archive not on disk")


def _listings(rows):
    return pd.DataFrame(rows, columns=["ad_id", "title", "price_eur", "price_type",
                                       "price_suspect", "is_wanted",
                                       "character_tags", "state"])


def test_wanted_ads_excluded_from_primary_but_reported():
    ads = kleinanzeigen.prepare(_listings([
        ("1", "Offer", 10.0, "fixed", False, False, '["itachi_uchiha"]', "Bayern"),
        ("2", "Wanted", 10.0, "fixed", False, True, '["itachi_uchiha"]', "Bayern"),
    ]))
    attr = kleinanzeigen.attribute(ads)
    assert attr["offer"]["itachi_uchiha"] == 1
    assert attr["wanted"]["itachi_uchiha"] == 1


def test_price_median_excludes_suspect_and_free():
    ads = kleinanzeigen.prepare(_listings([
        ("1", "A", 10.0, "fixed", False, False, '["jiraiya"]', "Bayern"),
        ("2", "B", 20.0, "negotiable", False, False, '["jiraiya"]', "Bayern"),
        ("3", "C", 1.0, "fixed", True, False, '["jiraiya"]', "Bayern"),
        ("4", "D", 0.0, "free", False, False, '["jiraiya"]', "Bayern"),
        ("5", "E", None, "unknown", False, False, '["jiraiya"]', "Bayern"),
    ]))
    prices = kleinanzeigen.build_prices(ads)
    assert len(prices) == 1
    assert prices.iloc[0]["median_eur"] == pytest.approx(15.0)
    assert prices.iloc[0]["n"] == 2


def test_solo_counts_and_pain_spelling():
    ads = kleinanzeigen.prepare(_listings([
        ("1", "A", 5.0, "fixed", False, False, '["pain_nagato"]', "Bayern"),
        ("2", "B", 5.0, "fixed", False, False,
         '["pain_nagato", "naruto_uzumaki"]', "Bayern"),
        ("3", "C", 5.0, "fixed", False, False,
         '["pain_nagato", "sasuke_uchiha"]', "Bayern"),
    ]))
    attr = kleinanzeigen.attribute(ads)
    assert attr["offer"]["nagato_pain"] == 3
    assert attr["solo"]["nagato_pain"] == 2  # benchmark co-occurrence still solo
    assert attr["solo"]["sasuke_uchiha"] == 0


def test_regions_map_states_to_codes():
    ads = kleinanzeigen.prepare(_listings([
        ("1", "A", 5.0, "fixed", False, False, '["gaara"]', "Bayern"),
        ("2", "B", 5.0, "fixed", False, False, '[]', "Saarland"),
    ]))
    regions = kleinanzeigen.build_regions(ads)
    assert len(regions) == 16 * 15  # 16 states x 14 keys + _all
    by = regions[regions["state_code"] == "BY"]
    assert by[by["character_key"] == "gaara"].iloc[0]["ads"] == 1
    assert by[by["character_key"] == "_all"].iloc[0]["ads"] == 1
    assert regions["ads"].sum() >= 2


@archive_present
@pytest.mark.archive
def test_archive_ad_total_within_1pc():
    import duckdb
    con = duckdb.connect()
    n = con.execute("SELECT COUNT(DISTINCT ad_id) FROM read_parquet(?)",
                    [str(dataset("kleinanzeigen", "raw", "final", "listings.parquet"))]).fetchone()[0]
    assert abs(n - 10291) / 10291 <= 0.01, n


@archive_present
@pytest.mark.archive
def test_archive_every_candidate_has_offer_ads():
    ads = kleinanzeigen.prepare(kleinanzeigen.load_listings())
    attr = kleinanzeigen.attribute(ads)
    missing = [k for k in characters.keys("candidate") if attr["offer"][k] == 0]
    assert missing == []
