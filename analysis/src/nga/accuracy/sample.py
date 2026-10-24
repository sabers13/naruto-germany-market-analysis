"""Stratified accuracy sample (ANALYSIS_PLAN.md §6.2).

Reads work/matches/<source>.parquet (one row per (record, character) match:
record_hash, source, character_key, matched_on, snippet) and draws, per
keyword source, with seed 20261023 and no duplicates:

- 40 random matches overall (stratum "random");
- 15 matches each for the ambiguous characters Hinata and Pain/Nagato
  (strata "hinata_hyuga" / "nagato_pain");
- 10 matches each for the 5 candidates with the highest match counts
  (strata "top5:<character_key>").

A stratum that holds fewer rows than its quota contributes everything it has.
Writes work/accuracy/sample.parquet (matches columns + sample_id, stratum).
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

from nga import characters
from nga.paths import work

from . import AMBIGUOUS_CHARACTERS, KEYWORD_SOURCES, N_AMBIGUOUS, N_RANDOM, N_TOP5, SEED

MATCH_COLUMNS = ("record_hash", "source", "character_key", "matched_on", "snippet")


def load_matches(matches_dir: Path | None = None) -> pd.DataFrame:
    """Read every keyword-source matches file present in the matches dir."""
    directory = Path(matches_dir) if matches_dir is not None else work("matches", "x").parent
    frames = []
    for source in KEYWORD_SOURCES:
        f = directory / f"{source}.parquet"
        if f.exists():
            frames.append(pd.read_parquet(f))
    if not frames:
        raise FileNotFoundError(f"no matches files in {directory}; run the lanes first")
    df = pd.concat(frames, ignore_index=True)
    missing = set(MATCH_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"matches files missing columns: {sorted(missing)}")
    df = df[df.source.isin(KEYWORD_SOURCES)].copy()
    if df.empty:
        raise ValueError("matches files hold no rows for the keyword sources")
    return df


def top5_candidates(df: pd.DataFrame) -> list[str]:
    """The 5 candidates with the highest match counts across all keyword sources.

    The benchmark (naruto_uzumaki) is excluded: it is never ranked (plan §2).
    Ties broken alphabetically for determinism.
    """
    counts = df[df.character_key.isin(characters.keys("candidate"))].value_counts("character_key")
    ordered = sorted(counts.index, key=lambda k: (-counts[k], k))
    return list(ordered[:5])


def _take(rng: random.Random, pool: list[int], quota: int, taken: set[int]) -> list[int]:
    """Draw up to `quota` indices from `pool` (sorted), skipping `taken`."""
    available = [i for i in pool if i not in taken]
    return rng.sample(available, min(quota, len(available)))


def draw_sample(df: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    """Draw the stratified sample. Deterministic for a fixed seed and input."""
    top5 = top5_candidates(df)
    strata_plan: list[tuple[str, str | None]] = (
        [("random", None)]
        + [(c, c) for c in AMBIGUOUS_CHARACTERS]
        + [(f"top5:{c}", c) for c in top5]
    )
    rng = random.Random(seed)
    picks: list[tuple[int, str]] = []  # (row position, stratum)
    for source in sorted(df.source.unique()):
        idx = df.index[df.source == source].tolist()
        by_char: dict[str, list[int]] = {}
        for i in sorted(idx):
            by_char.setdefault(str(df.character_key.iloc[i]), []).append(i)
        taken: set[int] = set()
        for stratum, char in strata_plan:
            pool = sorted(idx) if char is None else by_char.get(char, [])
            for i in _take(rng, pool, N_RANDOM if char is None else (N_AMBIGUOUS if stratum in AMBIGUOUS_CHARACTERS else N_TOP5), taken):
                taken.add(i)
                picks.append((i, stratum))
    if not picks:
        raise ValueError("stratified draw is empty; matches files too small?")
    out = df.loc[[i for i, _ in picks]].copy()
    out["stratum"] = [s for _, s in picks]
    out["sample_id"] = [f"S{n:04d}" for n in range(1, len(out) + 1)]
    cols = ["sample_id", "stratum", *MATCH_COLUMNS]
    return out[cols].reset_index(drop=True)


def run(matches_dir: Path | None = None, out_path: Path | None = None,
        seed: int = SEED) -> pd.DataFrame:
    """Load matches, draw the sample, write sample.parquet, return the sample."""
    sample = draw_sample(load_matches(matches_dir), seed=seed)
    out = Path(out_path) if out_path is not None else work("accuracy", "sample.parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    sample.to_parquet(out, index=False)
    return sample
