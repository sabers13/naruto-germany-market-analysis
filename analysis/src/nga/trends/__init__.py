"""Google Trends lane (trends lane): comparable German search interest per character.

Method (ANALYSIS_PLAN.md §4, archive docs/limits_and_comparability.md §6):
weekly topic series rescaled onto ONE reference batch via a shared anchor
term, single-hop only (no chained rescaling). Censored topic series fall back
to the plain term only when that term is not flagged ambiguous; otherwise the
character is missing (no row, never zero).
"""
from __future__ import annotations

# One reference batch for every rescaling. It holds the anchor ("Naruto",
# dominant: max 100, mean ~49) together with the Sasuke topic, so both topic
# batches (via "Naruto") and term batches (via "Naruto") reach it directly.
REFERENCE_BATCH = "character_topics__w5y__b01"
ANCHOR_TERM = "Naruto"

# Chosen weekly series: (character_key, term_raw, term_kind, batch_id, flag).
# Topics preferred (entity-resolved); plain terms only as the plan's fallback.
# naruto_uzumaki: topic /m/02sp46 is censored → plain term "Naruto". The term
# conflates character and franchise, which is exactly the benchmark's job
# (franchise scale); flagged term_series and documented in the lane report.
# nagato_pain: no topic, term flagged ambiguous_name → missing.
# shikamaru_nara: topic censored AND plain term censored → missing.
SERIES: list[tuple[str, str, str, str, str]] = [
    ("naruto_uzumaki", "Naruto", "query", "character_topics__w5y__b01", "term_series"),
    ("sasuke_uchiha", "/m/037b2q", "topic", "character_topics__w5y__b01", "topic_series"),
    ("itachi_uchiha", "/m/02p8p45", "topic", "character_topics__w5y__b02", "topic_series"),
    ("kakashi_hatake", "/m/0g1wjz", "topic", "character_topics__w5y__b02", "topic_series"),
    ("hinata_hyuga", "/m/04b5nh", "topic", "character_topics__w5y__b02", "topic_series"),
    ("gaara", "Gaara", "query", "characters_core__w5y__b03", "term_series"),
    ("madara_uchiha", "Madara", "query", "characters_core__w5y__b02", "term_series"),
    ("obito_uchiha", "Obito", "query", "characters_core__w5y__b02", "term_series"),
    ("minato_namikaze", "Minato", "query", "characters_secondary__w5y__b01", "term_series"),
    ("jiraiya", "Jiraiya", "query", "characters_core__w5y__b03", "term_series"),
    ("orochimaru", "Orochimaru", "query", "characters_secondary__w5y__b01", "term_series"),
    ("tsunade", "Tsunade", "query", "characters_core__w5y__b03", "term_series"),
]

MISSING: dict[str, str] = {
    "nagato_pain": "no topic series; plain term flagged ambiguous_name (plan §4: missing, not zero)",
    "shikamaru_nara": "topic /m/04b5rz censored and plain term censored at WEEK resolution (no analysable fallback)",
}

SNAPSHOT_DATE = "2026-10-22"
N_WEEKS_52W = 52
SEED = 20261023  # no sampling in this lane; fixed for the record
