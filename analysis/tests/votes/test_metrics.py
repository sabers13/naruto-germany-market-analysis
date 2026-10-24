"""Metrics archive tests: votes_eu covers all 14; catalog totals reconcile."""
import duckdb
import pytest

from nga import characters, metrics
from nga.paths import dataset
from nga.votes import context, narutop99

archive_present = pytest.mark.skipif(
    not dataset("anime2you", "data", "external", "narutop99",
                "narutop99_rankings.parquet").exists(),
    reason="data archive not on disk")


@pytest.mark.archive
@archive_present
def test_votes_eu_present_for_all_14():
    df = narutop99.run()
    assert set(df["character_key"]) == set(characters.keys())
    assert (df["value"] > 0).all()
    assert (df["primary"]).all()
    assert (df["lens"] == "votes").all()
    assert (df["evidence_class"] == "C").all()
    metrics.validate(df)  # single-source frame validates on its own


@pytest.mark.archive
@archive_present
def test_context_metrics_cover_all_14():
    wiki, wiki_rows = context.wikimedia_run()
    assert set(wiki["character_key"]) == set(characters.keys())
    assert (wiki["value"] > 0).all()
    assert not wiki["primary"].any()
    metrics.validate(wiki)
    assert wiki_rows == 6374


@pytest.mark.archive
@archive_present
def test_t04_catalog_totals_match():
    con = duckdb.connect()
    a = str(dataset("anime2you", "data", "external", "narutop99",
                    "narutop99_rankings.parquet"))
    w = str(dataset("wikimedia", "collector", "exports", "full_2026-10-22",
                    "pageviews.parquet"))
    assert con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{a}')").fetchone()[0] == 4392
    assert con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{w}')").fetchone()[0] == 482680
    assert con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{a}') "
        "WHERE region = 'europe'").fetchone()[0] == 488
    con.close()
