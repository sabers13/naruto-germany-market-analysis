"""Shared synthetic builders for scoring tests (hand-computed fixtures)."""

import pandas as pd

LENS = {
    "amazon": "shoppers",
    "ebay": "shoppers",
    "kleinanzeigen": "shoppers",
    "youtube": "watching",
    "google_trends": "watching",
    "anime2you": "watching",
    "narutop99": "votes",
}

METRIC = {
    "amazon": "asins",
    "ebay": "items",
    "kleinanzeigen": "offer_ads",
    "youtube": "comments_de",
    "google_trends": "interest_52w",
    "anime2you": "comment_mentions",
    "narutop99": "votes_eu",
}


def metrics_row(char, source, value, primary=True, lane="shops"):
    return {
        "character_key": char,
        "source": source,
        "metric": METRIC[source],
        "period": "snapshot",
        "region": "DE",
        "value": None if value is None else float(value),
        "n": 10,
        "unit": "count",
        "evidence_class": "D",
        "lens": LENS[source],
        "primary": primary,
        "lane": lane,
    }


def metrics_frame(entries):
    """entries: iterable of (character_key, source, value)."""
    return pd.DataFrame([metrics_row(c, s, v) for c, s, v in entries])


def precision_frame(entries):
    """entries: iterable of (source, character_key, precision, treatment)."""
    return pd.DataFrame(
        [
            {
                "source": s,
                "character_key": c,
                "n": 50,
                "correct": 45,
                "precision": p,
                "ci_low": 0.0,
                "ci_high": 1.0,
                "treatment": t,
            }
            for s, c, p, t in entries
        ]
    )


# Hand-verified 4-candidate fixture (ANALYSIS_PLAN.md Section 7 walk-through).
# Higher value = better. Expected outcomes are derived in test_robustness.py.
S, I, K, H = "sasuke_uchiha", "itachi_uchiha", "kakashi_hatake", "hinata_hyuga"

FIXTURE_ENTRIES = [
    (S, "amazon", 40), (I, "amazon", 30), (K, "amazon", 20), (H, "amazon", 10),
    (S, "ebay", 40), (I, "ebay", 30), (K, "ebay", 20), (H, "ebay", 10),
    (S, "kleinanzeigen", 40), (I, "kleinanzeigen", 30),
    (K, "kleinanzeigen", 10), (H, "kleinanzeigen", 20),
    (S, "youtube", 40), (I, "youtube", 30), (K, "youtube", 10), (H, "youtube", 20),
    (S, "google_trends", 40), (I, "google_trends", 30),
    (K, "google_trends", 20), (H, "google_trends", 10),
    (S, "anime2you", 40), (I, "anime2you", 30),
    (K, "anime2you", 10), (H, "anime2you", 20),
    (S, "narutop99", 40), (I, "narutop99", 30),
    (K, "narutop99", 15), (H, "narutop99", 15),
]
