"""Lane-level archive tests: run all three sources, validate the joint outputs."""
import pandas as pd
import pytest

from nga import characters, metrics
from nga.paths import dataset, work
from nga.shops import amazon, ebay, kleinanzeigen

archive_present = pytest.mark.skipif(
    not dataset("kleinanzeigen", "raw", "final", "listings.parquet").exists(),
    reason="data archive not on disk")


@archive_present
@pytest.mark.archive
def test_lane_outputs_validate_and_reconcile():
    amz = amazon.run()
    eb = ebay.run()
    kl = kleinanzeigen.run()

    joint = pd.concat([amz["metrics"], eb["metrics"], kl["metrics"]], ignore_index=True)
    metrics.validate(joint)  # raises on bad rows, duplicates, >1 primary per source

    # one primary metric per source, all 14 keys covered
    for source, metric in [("amazon", "asins"), ("ebay", "items"),
                           ("kleinanzeigen", "offer_ads")]:
        prim = joint[(joint["source"] == source) & (joint["metric"] == metric)]
        assert set(prim["character_key"]) == set(characters.keys()) | {"_all"}, source

    # matches files: schema, hash length, snippet cap
    for name, frame in [("amazon", amz["matches"]), ("ebay", eb["matches"]),
                        ("kleinanzeigen", kl["matches"])]:
        assert list(frame.columns) == ["record_hash", "source", "character_key",
                                       "matched_on", "snippet"], name
        assert (frame["record_hash"].str.len() == 40).all(), name
        assert (frame["snippet"].str.len() <= 200).all(), name
        assert set(frame["character_key"]) <= set(characters.keys()), name

    # aux shapes
    assert list(eb["merch"].columns) == ["character_key", "category", "items"]
    assert set(eb["merch"]["category"]) <= {"figures", "clothing", "cards",
                                            "manga_media", "accessories", "other"}
    assert list(kl["regions"].columns) == ["state_code", "state_name",
                                           "character_key", "ads"]
    assert len(kl["regions"]) == 16 * 15
    for prices in (eb["prices"], kl["prices"]):
        assert list(prices.columns) == ["character_key", "platform", "median_eur", "n"]

    # totals reconcile with DATA_CATALOG.md (stop rule section 10.4)
    assert int(amz["total_asins"].iloc[0]["asins"]) == 4956
    assert int(eb["total_items_before_filter"].iloc[0]["items"]) == 8801
    assert int(eb["total_items"].iloc[0]["items"]) == 8331
    assert int(kl["total_ads"].iloc[0]["ads"]) == 10291

    # work/ files written by the lane CLI exist
    assert work("metrics", "shops.parquet").exists()
    for source in ["amazon", "ebay", "kleinanzeigen"]:
        assert work("matches", f"{source}.parquet").exists()
    for name in ["prices", "merch", "regions"]:
        assert work("aux", f"{name}.parquet").exists()
    assert work("aux", "kpis_shops.json").exists()
    assert work("aux", "sources_shops.json").exists()
