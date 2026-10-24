"""Hand-made fixtures for the §13 benchmark tests (synthetic, no archive)."""

import pandas as pd

NARUTO = "naruto_uzumaki"
SASUKE = "sasuke_uchiha"
ITACHI = "itachi_uchiha"

LENS = {
    "amazon": "shoppers",
    "ebay": "shoppers",
    "kleinanzeigen": "shoppers",
    "youtube": "watching",
    "google_trends": "watching",
    "anime2you": "watching",
    "narutop99": "votes",
}

EVIDENCE = {
    "amazon": "D",
    "ebay": "D",
    "kleinanzeigen": "A",
    "youtube": "B",
    "google_trends": "A",
    "anime2you": "B",
    "narutop99": "C",
}


def metrics_frame(entries):
    """entries: (character_key, source, metric, value, primary)."""
    rows = [{
        "character_key": c, "source": s, "metric": m,
        "period": "snapshot", "region": "DE",
        "value": None if v is None else float(v), "n": 10,
        "unit": "count", "evidence_class": EVIDENCE[s], "lens": LENS[s],
        "primary": primary, "lane": "test",
    } for c, s, m, v, primary in entries]
    return pd.DataFrame(rows)


def precision_frame(entries):
    """entries: (source, character_key, precision, treatment[, ci_low, n]).

    ci_low defaults to the precision itself (a tight interval), so a row
    only fails the §13 CI test when a test asks for it.
    """
    rows = []
    for e in entries:
        s, c, p, t = e[:4]
        ci_low = e[4] if len(e) > 4 else p
        n = e[5] if len(e) > 5 else 30
        rows.append({
            "source": s, "character_key": c, "n": n, "correct": round(p * n),
            "precision": p, "ci_low": ci_low, "ci_high": 1.0, "treatment": t,
        })
    return pd.DataFrame(rows)


def base_metrics():
    """Two candidates + Naruto across all nine benchmark (source, metric)."""
    specs = [
        ("amazon", "asins", True),
        ("ebay", "items", True),
        ("kleinanzeigen", "offer_ads", True),
        ("youtube", "comments_de", True),
        ("youtube", "videos_de", False),
        ("google_trends", "interest_52w", True),
        ("anime2you", "comment_mentions", True),
        ("anime2you", "articles", False),
        ("narutop99", "votes_eu", True),
    ]
    values = {
        NARUTO: [1459, 7086, 536, 3880, 2409, 37.730769, 3, 130, 34959],
        SASUKE: [129, 623, 666, 1405, 500, 4.057692, 157, 40, 34797],
        ITACHI: [95, 562, 431, 1104, 400, 3.096154, 49, 30, 129376],
    }
    entries = [(char, s, m, values[char][i], prim)
               for i, (s, m, prim) in enumerate(specs)
               for char in (NARUTO, SASUKE, ITACHI)]
    return metrics_frame(entries)


def base_precision():
    """Naruto rows mirroring reports/accuracy/precision.csv."""
    return precision_frame([
        ("amazon", NARUTO, 0.7419354838709677, "adjust"),
        ("ebay", NARUTO, 0.6551724137931034, "exclude"),
        ("youtube", NARUTO, 0.9285714285714286, "use", 0.6853073044604219, 14),
    ])


def weekly_frame(naruto_vals, franchise_vals, batch="character_topics__w5y__b01",
                 franchise_batch=None, with_anchor=True):
    """Two weekly series on the the trends lane grid; franchise optionally elsewhere."""
    starts = pd.date_range(end="2026-10-18", periods=len(naruto_vals),
                           freq="7D", tz="UTC")
    rows = [{"batch_id": batch, "term_raw": "Naruto",
             "bucket_start_utc": t, "value": float(v), "is_partial": False}
            for t, v in zip(starts, naruto_vals)]
    fbatch = franchise_batch or batch
    anchor_rows = [] if fbatch == batch or not with_anchor else [
        {"batch_id": fbatch, "term_raw": "Naruto",
         "bucket_start_utc": t, "value": 50.0, "is_partial": False}
        for t in starts]
    rows += anchor_rows + [
        {"batch_id": fbatch, "term_raw": "/m/01hryy",
         "bucket_start_utc": t, "value": float(v), "is_partial": False}
        for t, v in zip(starts, franchise_vals)]
    return pd.DataFrame(rows)


def correlated_weeks(n=60, noise=0.5, seed=20261023):
    """Franchise tracks Naruto (r ≈ 1): the production shape."""
    rng = __import__("numpy").random.default_rng(seed)
    base = 35 + 5 * __import__("numpy").sin(
        __import__("numpy").arange(n) / 6.0) + rng.normal(0, noise, n)
    return [float(x) for x in base], [float(x) for x in base + rng.normal(0, noise, n)]


def uncorrelated_weeks(n=60):
    """Franchise alternates while Naruto trends up (r << 0.90)."""
    naruto = [30.0 + i * 0.2 for i in range(n)]
    franchise = [20.0 if i % 2 == 0 else 40.0 for i in range(n)]
    return naruto, franchise
