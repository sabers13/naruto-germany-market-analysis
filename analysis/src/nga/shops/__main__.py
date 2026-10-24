"""Run the shops lane end to end: metrics, matches, aux, kpis, sources."""
from __future__ import annotations

import json

import pandas as pd

from nga import metrics
from nga.paths import check_archive, work

from . import amazon, ebay, kleinanzeigen


def main() -> None:
    check_archive()
    amz = amazon.run()
    eb = ebay.run()
    kl = kleinanzeigen.run()

    metrics.write(pd.concat([amz["metrics"], eb["metrics"], kl["metrics"]],
                            ignore_index=True), "shops")

    matches = pd.concat([amz["matches"], eb["matches"], kl["matches"]], ignore_index=True)
    for source, frame in matches.groupby("source"):
        frame.to_parquet(work("matches", f"{source}.parquet"), index=False)

    prices = pd.concat([
        pd.DataFrame([{"character_key": k, "platform": "amazon",
                       "median_eur": r["value"], "n": r["n"]}
                      for _, r in amz["metrics"]
                      [amz["metrics"]["metric"] == "median_price_eur"].iterrows()
                      for k in [r["character_key"]]]),
        eb["prices"],
        kl["prices"],
    ], ignore_index=True)
    prices.to_parquet(work("aux", "prices.parquet"), index=False)
    eb["merch"].to_parquet(work("aux", "merch.parquet"), index=False)
    kl["regions"].to_parquet(work("aux", "regions.parquet"), index=False)

    shop_listings_checked = (int(amz["total_asins"].iloc[0]["asins"])
                             + int(eb["total_items_before_filter"].iloc[0]["items"])
                             + int(kl["total_ads"].iloc[0]["ads"]))
    work("aux", "kpis_shops.json").write_text(json.dumps(
        {"shop_listings_checked": shop_listings_checked}, indent=2) + "\n")
    work("aux", "sources_shops.json").write_text(json.dumps([
        {"id": "amazon", "records": int(amz["total_asins"].iloc[0]["asins"]), "in_score": True},
        {"id": "ebay", "records": int(eb["total_items"].iloc[0]["items"]), "in_score": True},
        {"id": "kleinanzeigen", "records": int(kl["total_ads"].iloc[0]["ads"]), "in_score": True},
    ], indent=2) + "\n")

    prim = pd.concat([amz["metrics"], eb["metrics"], kl["metrics"]], ignore_index=True)
    prim = prim[prim["primary"]]
    print(prim.pivot_table(index="character_key", columns="source", values="value",
                           aggfunc="first").to_string())
    print(f"shop_listings_checked={shop_listings_checked} "
          f"(amazon_asins={int(amz['total_asins'].iloc[0]['asins'])} "
          f"ebay_items_before_filter={int(eb['total_items_before_filter'].iloc[0]['items'])} "
          f"ebay_relevant={int(eb['total_items'].iloc[0]['items'])} "
          f"kleinanzeigen_ads={int(kl['total_ads'].iloc[0]['ads'])}) "
          f"matches_rows={len(matches)}")


if __name__ == "__main__":
    main()
