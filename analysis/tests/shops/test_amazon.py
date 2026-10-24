"""Amazon unit tests (synthetic) + archive reconciliation tests."""
import pandas as pd
import pytest

from nga import characters
from nga.paths import dataset
from nga.shops import amazon

archive_present = pytest.mark.skipif(
    not dataset("amazon", "out", "amazon_search_cards.parquet").exists(),
    reason="data archive not on disk")


def _cards(rows):
    return pd.DataFrame(rows, columns=["asin", "title", "price_value",
                                       "review_count", "character_matches"])


def test_dedupe_unions_tags_across_cards():
    cards = _cards([
        ("A1", "Naruto Figure", 10.0, 5, "naruto_uzumaki"),
        ("A1", "Naruto Figure", 12.0, 7, "naruto_uzumaki; sasuke_uchiha"),
        ("A2", "Sakura Poster", 8.0, None, ""),
    ])
    asins = amazon.dedupe_cards(cards)
    assert len(asins) == 2
    a1 = asins[asins["asin"] == "A1"].iloc[0]
    assert a1["keys"] == {"naruto_uzumaki", "sasuke_uchiha"}
    assert a1["price_value"] == pytest.approx(11.0)
    assert a1["review_count"] == pytest.approx(6.0)
    a2 = asins[asins["asin"] == "A2"].iloc[0]
    assert a2["keys"] == set()


def test_multi_character_attribution_and_solo():
    cards = _cards([
        ("A1", "T1", 10.0, 1, "naruto_uzumaki; sasuke_uchiha"),
        ("A2", "T2", 10.0, 1, "sasuke_uchiha"),
        ("A3", "T3", 10.0, 1, "sakura_haruno"),  # excluded character: nobody's solo spoiled
        ("A4", "T4", 10.0, 1, "sasuke_uchiha; itachi_uchiha"),
    ])
    asins = amazon.dedupe_cards(cards)
    attr = amazon.attribute(asins)
    assert attr["counts"]["sasuke_uchiha"] == 3
    assert attr["counts"]["itachi_uchiha"] == 1
    # A1 (benchmark co-occurs) and A2 are solo Sasuke; A4 is not solo anyone
    assert attr["solo"]["sasuke_uchiha"] == 2
    assert attr["solo"]["itachi_uchiha"] == 0
    # A3 has no candidate: benchmark-only solo bucket stays empty here
    assert attr["solo"]["naruto_uzumaki"] == 0


def test_median_reviews_excludes_missing():
    cards = _cards([
        ("A1", "T1", 10.0, None, "gaara"),
        ("A2", "T2", 10.0, 4, "gaara"),
        ("A3", "T3", 10.0, 8, "gaara"),
    ])
    asins = amazon.dedupe_cards(cards)
    m = amazon.build_metrics(asins)
    rev = m[(m["character_key"] == "gaara") & (m["metric"] == "median_reviews")].iloc[0]
    assert rev["value"] == pytest.approx(6.0)
    assert rev["n"] == 2


def test_matches_one_row_per_asin_character():
    cards = _cards([("A1", "x" * 300, 10.0, 1, "naruto_uzumaki; sasuke_uchiha")])
    matches = amazon.build_matches(amazon.dedupe_cards(cards))
    assert len(matches) == 2
    assert (matches["record_hash"].str.len() == 40).all()
    assert (matches["snippet"].str.len() <= 200).all()


@archive_present
@pytest.mark.archive
def test_archive_asin_total_within_1pc():
    import duckdb
    con = duckdb.connect()
    n = con.execute("SELECT COUNT(DISTINCT asin) FROM read_parquet(?)",
                    [str(dataset("amazon", "out", "amazon_search_cards.parquet"))]).fetchone()[0]
    assert abs(n - 4956) / 4956 <= 0.01, n


@archive_present
@pytest.mark.archive
def test_archive_every_candidate_has_asins():
    asins = amazon.dedupe_cards(amazon.load_cards())
    attr = amazon.attribute(asins)
    missing = [k for k in characters.keys("candidate") if attr["counts"][k] == 0]
    assert missing == []
