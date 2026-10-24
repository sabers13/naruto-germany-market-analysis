"""Shared synthetic fixtures for the accuracy-harness tests.

Everything here is invented data written to tmp_path; no archive, no work/.
"""
import hashlib

import pandas as pd
import pytest

SOURCES = ["amazon", "ebay", "kleinanzeigen", "youtube", "anime2you"]


def make_matches(counts: dict[tuple[str, str], int]) -> pd.DataFrame:
    """Build a synthetic matches table.

    counts maps (source, character_key) -> number of rows. Every row gets a
    unique record_hash, mimicking one (record, character) match each.
    """
    rows = []
    for (source, char), n in sorted(counts.items()):
        for i in range(n):
            digest = hashlib.sha1(f"{source}:{char}:{i}".encode()).hexdigest()
            rows.append({"record_hash": digest, "source": source,
                         "character_key": char, "matched_on": f"alias-{char}",
                         "snippet": f"... snippet {i} about {char} ..."})
    return pd.DataFrame(rows, columns=["record_hash", "source", "character_key",
                                       "matched_on", "snippet"])


def write_matches(df: pd.DataFrame, directory) -> None:
    for source in sorted(df.source.unique()):
        df[df.source == source].to_parquet(f"{directory}/{source}.parquet", index=False)


def make_labels(sample_df: pd.DataFrame, wrong_ids=(), label="wrong_character",
                unclear_ids=(), model="test-labeller") -> pd.DataFrame:
    rows = []
    for _, r in sample_df.iterrows():
        if r["sample_id"] in unclear_ids:
            lab = "unclear"
        elif r["sample_id"] in set(wrong_ids):
            lab = label
        else:
            lab = "correct"
        rows.append({"sample_id": r["sample_id"], "source": r["source"],
                     "character_key": r["character_key"], "record_hash": r["record_hash"],
                     "label": lab, "labeller_model": model, "note": ""})
    return pd.DataFrame(rows)


@pytest.fixture
def ample_counts() -> dict[tuple[str, str], int]:
    """Per-source counts with a known global top-5 and ample strata pools."""
    per_source = {"sasuke_uchiha": 90, "itachi_uchiha": 80, "kakashi_hatake": 70,
                  "gaara": 65, "madara_uchiha": 62, "hinata_hyuga": 60,
                  "nagato_pain": 60, "obito_uchiha": 8, "minato_namikaze": 8,
                  "jiraiya": 8, "orochimaru": 5, "tsunade": 5, "shikamaru_nara": 5}
    return {(s, c): n for s in SOURCES for c, n in per_source.items()}


@pytest.fixture
def ample_matches(ample_counts) -> pd.DataFrame:
    return make_matches(ample_counts)
