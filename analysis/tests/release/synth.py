"""Synthetic inputs for the pipeline tests: shaped like contract/preview.fixture.json.

All numbers are invented and deterministic. No archive or row-level data.
"""
import json
import pathlib

import pandas as pd
import yaml

CANDIDATE_RANKS = [
    ("sasuke_uchiha", 1, 92.0),
    ("itachi_uchiha", 2, 87.0),
    ("kakashi_hatake", 3, 80.0),
    ("minato_namikaze", 4, 65.0),
    ("madara_uchiha", 5, 62.0),
    ("hinata_hyuga", 6, 56.0),
    ("gaara", 7, 47.0),
    ("obito_uchiha", 8, 35.0),
    ("jiraiya", 9, 34.0),
    ("orochimaru", 10, 28.0),
    ("nagato_pain", 11, 24.0),
    ("shikamaru_nara", 12, 23.0),
    ("tsunade", 13, 19.0),
]
TOP3 = ["sasuke_uchiha", "itachi_uchiha", "kakashi_hatake"]
PERIODS = [
    "2023-01", "2023-04", "2023-07", "2023-10",
    "2024-01", "2024-04", "2024-07", "2024-10",
    "2025-01", "2025-04", "2025-07", "2025-10",
]
MOMENTUM_KEYS = ["sasuke_uchiha", "itachi_uchiha", "kakashi_hatake",
                 "minato_namikaze", "madara_uchiha", "hinata_hyuga", "gaara"]


def make_result() -> dict:
    characters = [
        {
            "character_key": key,
            "rank": rank,
            "index": index,
            "lens_ranks": {"shoppers": rank, "watching": rank, "votes": rank},
            "top3_sources": 3 if rank <= 3 else 0,
            "confidence": "robust" if rank <= 3 else "mixed",
            "flags": [],
        }
        for key, rank, index in CANDIDATE_RANKS
    ]
    return {
        "weights": {"shoppers": 0.5, "watching": 0.3, "votes": 0.2},
        "characters": characters,
        "robustness": {
            "kendall_w": 0.55,
            "agreement_label": "moderate",
            "leave_one_out": {
                "runs": 7,
                "same_top3": 5,
                "top3": ["sasuke_uchiha", "itachi_uchiha", "kakashi_hatake"],
            },
            "alt_weights": [
                {"name": "equal",
                 "weights": {"shoppers": 0.334, "watching": 0.333, "votes": 0.333},
                 "top3": ["sasuke_uchiha", "itachi_uchiha", "kakashi_hatake"],
                 "same_top3": True},
                {"name": "shoppers_only",
                 "weights": {"shoppers": 1.0, "watching": 0.0, "votes": 0.0},
                 "top3": ["sasuke_uchiha", "itachi_uchiha", "kakashi_hatake"],
                 "same_top3": True},
                {"name": "german_only",
                 "weights": {"shoppers": 0.625, "watching": 0.375, "votes": 0.0},
                 "top3": ["sasuke_uchiha", "itachi_uchiha", "kakashi_hatake"],
                 "same_top3": True},
            ],
        },
        "counts": {
            key: {
                "amazon_products": 10 + rank,
                "ebay_items": 100 + rank,
                "kleinanzeigen_ads": 50 + rank,
                "youtube_videos_de": 20 + rank,
                "youtube_comments_de": 200 + rank,
                "anime2you_articles": 5 + rank,
                "fan_votes_eu": 1000 * (14 - rank),
                "google_interest": round(3.0 - rank * 0.1, 2),
            }
            for key, rank, _ in CANDIDATE_RANKS
        } | {
            "naruto_uzumaki": {
                "amazon_products": 999,
                "ebay_items": 999,
                "kleinanzeigen_ads": 999,
                "youtube_videos_de": 999,
                "youtube_comments_de": 999,
                "anime2you_articles": 99,
                "fan_votes_eu": 9999,
                "google_interest": 28.4,
            }
        },
        "precision": [
            {"source": "amazon", "character_key": "_all", "n": 40,
             "correct": 38, "precision": 0.95, "treatment": "use"},
            {"source": "ebay", "character_key": "hinata_hyuga", "n": 15,
             "correct": 12, "precision": 0.8, "treatment": "adjust"},
        ],
    }


def make_aux(aux_dir, states_yaml) -> None:
    aux_dir.mkdir(parents=True, exist_ok=True)
    keys14 = [k for k, _, _ in CANDIDATE_RANKS] + ["naruto_uzumaki"]

    prices = []
    for i, key in enumerate(keys14):
        for j, plat in enumerate(("amazon", "ebay", "kleinanzeigen")):
            n = 5 if (key == "obito_uchiha" and plat == "amazon") else 20 + i
            prices.append({"character_key": key, "platform": plat,
                           "median_eur": round(19.9 + i + j, 2), "n": n})
    pd.DataFrame(prices).to_parquet(aux_dir / "prices.parquet", index=False)

    merch = []
    for i, key in enumerate(keys14):
        total = 150 if i < 6 else 12
        for c, cat in enumerate(["figures", "clothing", "cards", "manga_media",
                                 "accessories", "other"]):
            merch.append({"character_key": key, "category": cat,
                          "items": total // 6 + (1 if c < total % 6 else 0)})
    pd.DataFrame(merch).to_parquet(aux_dir / "merch.parquet", index=False)

    states = yaml.safe_load(states_yaml.read_text())
    regions = []
    for s, (name, cfg) in enumerate(states.items()):
        regions.append({"state_code": cfg["code"], "state_name": name,
                        "character_key": "_all", "ads": 300 + s})
        for t, key in enumerate(TOP3):
            ads = 4 if (cfg["code"] == "SL" and key == "kakashi_hatake") else 30 + s + t
            regions.append({"state_code": cfg["code"], "state_name": name,
                            "character_key": key, "ads": ads})
    pd.DataFrame(regions).to_parquet(aux_dir / "regions.parquet", index=False)

    # Trends by state (the trends lane trends_regions.parquet shape). Naruto's single-term
    # index; candidate terms in their own multi-term requests. "Pain" has no
    # regional series (missing); Gaara has one Google 0 (too few searches).
    terms = {"sasuke_uchiha": ("Sasuke", "b01"), "itachi_uchiha": ("Itachi", "b02"),
             "kakashi_hatake": ("Kakashi", "b01"), "hinata_hyuga": ("Hinata", "b01"),
             "gaara": ("Gaara", "b02"), "madara_uchiha": ("Madara", "s01"),
             "obito_uchiha": ("Obito", "s01"), "minato_namikaze": ("Minato", "s02"),
             "jiraiya": ("Jiraiya", "s01"), "orochimaru": ("Orochimaru", "s02"),
             "tsunade": ("Tsunade", "s02"), "shikamaru_nara": ("Shikamaru", "s02")}
    trends_regions = []
    for s, cfg in enumerate(states.values()):
        code = cfg["code"]
        trends_regions.append({"state_code": code, "batch_id": "single",
                               "term": "Naruto", "metric": "relative_index_0_100",
                               "value": float(100 - s * 2)})
        for key, (term, batch) in terms.items():
            if key == "itachi_uchiha":
                value = 5 + s % 4          # spread 3 → hint
            elif key == "gaara" and code == "BY":
                value = 0                  # Google's "too few searches"
            else:
                value = 6 + s % 2          # spread 1 → flat
            trends_regions.append({"state_code": code, "batch_id": batch, "term": term,
                                   "metric": "share_of_compared_terms_pct",
                                   "value": float(value)})
    pd.DataFrame(trends_regions).to_parquet(aux_dir / "trends_regions.parquet", index=False)

    momentum = []
    for m, key in enumerate(MOMENTUM_KEYS):
        for p, period in enumerate(PERIODS):
            momentum.append({
                "character_key": key,
                "period": period,
                "value": round(6.0 - m * 0.5 - p * 0.07, 2),
                "series_kind": "term" if key == "madara_uchiha" else "topic",
                "flag": None,
            })
    # Reference series (mirrors the trends lane: Naruto uses the plain term, topic censored).
    for p, period in enumerate(PERIODS):
        momentum.append({
            "character_key": "naruto_uzumaki",
            "period": period,
            "value": round(38.0 - p * 0.07, 2),
            "series_kind": "query",
            "flag": "term_series",
        })
    pd.DataFrame(momentum).to_parquet(aux_dir / "momentum.parquet", index=False)

    (aux_dir / "events.json").write_text(json.dumps([
        {"id": "ev_20261010_test_panel", "date": "2026-10-10",
         "owner": "franchise", "confidence": "confirmed",
         "title_en": "Test panel", "title_de": "Testpanel",
         "note_en": "Short note.", "note_de": "Kurze Notiz.",
         "source_url": "https://www.anime2you.de/news/1/test/"},
    ]))
    (aux_dir / "kpis_shops.json").write_text(json.dumps({
        "shop_listings_checked": 3000,
        "records_counted": 9000,
    }))
    (aux_dir / "kpis_fans.json").write_text(json.dumps({
        "youtube_comments_de": 2000,
        "youtube_comments_total": 5000,
        "anime2you_articles": 100,
    }))
    (aux_dir / "sources_shops.json").write_text(json.dumps([
        {"id": "amazon", "records": 1000, "in_score": True},
        {"id": "ebay", "records": 2000, "in_score": True},
    ]))
    (aux_dir / "sources_trends.json").write_text(json.dumps([
        {"id": "google_trends", "records": 6000, "in_score": False},
    ]))
    # Synthetic benchmark output (contract's benchmark_comparison object). Values
    # carry extra decimals on purpose so the release rounding test bites.
    (aux_dir / "benchmark.json").write_text(json.dumps({
        "benchmark": "naruto_uzumaki",
        "sources": [
            {"id": "amazon", "metric": "asins", "comparable": False,
             "reason": "precision_low", "detail": "Naruto precision 0.66",
             "benchmark_value": 999.456},
            {"id": "ebay", "metric": "items", "comparable": False,
             "reason": "precision_low", "benchmark_value": 999},
            {"id": "kleinanzeigen", "metric": "offer_ads", "comparable": True,
             "reason": "explicit_tags", "benchmark_value": 999},
            {"id": "youtube_comments", "metric": "comments_de", "comparable": False,
             "reason": "not_measured", "benchmark_value": None},
            {"id": "youtube_videos", "metric": "videos_de", "comparable": False,
             "reason": "not_measured", "benchmark_value": None},
            {"id": "google_trends", "metric": "interest_52w", "comparable": False,
             "reason": "franchise_dominated", "detail": "r = 0.94 with franchise topic",
             "benchmark_value": 28.402},
            {"id": "anime2you_comments", "metric": "comment_mentions", "comparable": False,
             "reason": "alias_restricted", "benchmark_value": 3},
            {"id": "anime2you_articles", "metric": "articles", "comparable": False,
             "reason": "not_measured", "benchmark_value": None},
            {"id": "narutop99", "metric": "votes_eu", "comparable": True,
             "reason": "vote", "benchmark_value": 9999},
        ],
        "by_character": {
            "sasuke_uchiha": {"ratios": {"kleinanzeigen": 1.236, "narutop99": 1.404},
                              "comparable_sources": 2, "ahead_in": 2},
            "itachi_uchiha": {"ratios": {"kleinanzeigen": 0.874, "narutop99": None},
                              "comparable_sources": 1, "ahead_in": 0},
        },
    }))


def add_kleinanzeigen(aux_dir):
    """Add a Kleinanzeigen source and make it non-comparable (alias-restricted)."""
    aux_dir = pathlib.Path(aux_dir)
    (aux_dir / "sources_ka.json").write_text(json.dumps([
        {"id": "kleinanzeigen", "records": 1500, "in_score": True}]))
    bench = json.loads((aux_dir / "benchmark.json").read_text())
    for src in bench["sources"]:
        if src["id"] == "kleinanzeigen":
            src.update(comparable=False, reason="alias_restricted")
    for body in bench["by_character"].values():
        if body["ratios"].get("kleinanzeigen") is not None:
            body["ratios"]["kleinanzeigen"] = None
            body["comparable_sources"] -= 1
    (aux_dir / "benchmark.json").write_text(json.dumps(bench))
