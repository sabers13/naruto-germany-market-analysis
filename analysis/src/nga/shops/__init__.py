"""the shops lane shops lane: Amazon, eBay, Kleinanzeigen -> shoppers evidence.

Shared helpers only. Per-source logic lives in amazon.py, ebay.py, kleinanzeigen.py.
Conventions:
- Entity dedupe first; a record naming several characters counts once for each.
- `solo` for candidate X: entities whose only *candidate* character is X
  (benchmark naruto_uzumaki and non-candidate tags may co-occur).
  For the benchmark, `solo` = benchmark-only entities (no candidate present).
- Missing is null/absent, never 0: zero-count metrics are omitted, not written as 0.
"""
from __future__ import annotations

import hashlib
import json

import pandas as pd

from nga import characters

CANDIDATES = set(characters.keys("candidate"))
BENCHMARK = characters.keys("benchmark")[0]  # naruto_uzumaki
ALL_KEYS = set(characters.keys())  # 14 locked keys

# eBay merch_category -> the 6 contract categories (ANALYSIS_PLAN.md section 4).
MERCH_MAP = {
    "figure": "figures",
    "funko": "figures",
    "apparel": "clothing",
    "cosplay": "clothing",
    "trading_cards": "cards",
    "manga": "manga_media",
    "media": "manga_media",
    "print": "manga_media",
    "accessories": "accessories",
    "plush": "accessories",
    "other": "other",
}
MERCH_CATEGORIES = ["figures", "clothing", "cards", "manga_media", "accessories", "other"]


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def clip(text: str | None, limit: int = 200) -> str:
    if text is None:
        return ""
    text = str(text)
    return text[:limit]


def parse_json_tags(raw: str | None) -> list[str]:
    """Parse a JSON-list tag column (eBay character_matches, Kleinanzeigen character_tags)."""
    if raw is None or raw == "":
        return []
    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(items, list):
        return [str(t) for t in items]
    return [str(items)]


def split_amazon_tags(raw: str | None) -> list[str]:
    """Split an Amazon character_matches string on ';' (plan section 4)."""
    if raw is None or raw == "":
        return []
    return [t.strip() for t in str(raw).split(";") if t.strip()]


def map_tags(tags: list[str], source: str) -> set[str]:
    """Map source spellings to canonical keys; drop non-character tags."""
    sm = characters.source_map(source)
    return {sm[t] for t in tags if t in sm}


def candidate_set(keys: set[str]) -> set[str]:
    return set(keys) & CANDIDATES


def is_solo(keys: set[str], key: str) -> bool:
    """True if `key` is the lane's solo character for an entity tagged with `keys`."""
    if key == BENCHMARK:
        return BENCHMARK in keys and not candidate_set(keys)
    return candidate_set(keys) == {key}


def median_or_none(values: pd.Series) -> tuple[float | None, int]:
    """Median of non-null values; (None, 0) when empty."""
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) == 0:
        return None, 0
    return float(clean.median()), int(len(clean))


def count_rows(
    source: str,
    metric: str,
    counts: dict[str, int],
    *,
    unit: str = "count",
    evidence_class: str = "D",
    primary: bool = False,
) -> list[dict]:
    """Build metric rows, omitting zero counts (missing is not zero)."""
    rows = []
    for key, value in counts.items():
        if value is None or value <= 0:
            continue
        rows.append({
            "character_key": key,
            "source": source,
            "metric": metric,
            "period": "snapshot",
            "region": "DE",
            "value": float(value),
            "n": int(value),
            "unit": unit,
            "evidence_class": evidence_class,
            "lens": "shoppers",
            "primary": primary,
            "lane": "shops",
        })
    return rows
