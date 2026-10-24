"""Precision estimates from labels (ANALYSIS_PLAN.md §6.4–§6.6, §10.3).

Reads reports/accuracy/labels.csv (committed by the pipeline), joins it to the sample
rebuilt deterministically from the seed on sample_id + record_hash (any
mismatch refuses), and computes precision per (source, character) where n ≥ 10
else per source (`_all`), with a Wilson 95% interval. `unclear` counts as wrong.

Treatments (plan §6.5): precision ≥ 0.90 → use; 0.70–0.90 → adjust;
< 0.70 → exclude. A source whose overall precision is < 0.50 stops the run.

Writes work/accuracy/precision.parquet, reports/accuracy/precision.csv and
reports/accuracy/sample.csv (sample_id, source, character, label; no snippets).
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from nga.paths import reports, work

from . import LABELS, SEED
from .sample import draw_sample, load_matches

LABEL_COLUMNS = ("sample_id", "source", "character_key", "record_hash",
                 "label", "labeller_model", "note")

PRECISION_COLUMNS = ("source", "character_key", "n", "correct", "precision",
                     "ci_low", "ci_high", "treatment")

#: Wilson interval z-value for 95% confidence.
Z95 = 1.96

#: Stop threshold (plan §10.3): a source below this overall precision halts.
STOP_THRESHOLD = 0.50


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float, float]:
    """Wilson score interval. Returns (precision, ci_low, ci_high), clipped to [0, 1]."""
    if n <= 0:
        raise ValueError("Wilson interval needs n >= 1")
    if not 0 <= k <= n:
        raise ValueError(f"k={k} out of range for n={n}")
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centre - half), min(1.0, centre + half)


def treatment_for(precision: float) -> str:
    """Treatment per plan §6.5. Exact 0.90 → use, exact 0.70 → adjust."""
    if precision >= 0.90:
        return "use"
    if precision >= 0.70:
        return "adjust"
    return "exclude"


def _checked_labels(labels_df: pd.DataFrame, sample_df: pd.DataFrame) -> pd.DataFrame:
    """Validate labels and join them to the sample. Refuses on any mismatch."""
    missing = set(LABEL_COLUMNS) - set(labels_df.columns)
    if missing:
        raise ValueError(f"labels.csv missing columns: {sorted(missing)}")
    bad_labels = set(labels_df.label.unique()) - set(LABELS)
    if bad_labels:
        raise ValueError(f"unknown labels: {sorted(bad_labels)}")
    if labels_df.sample_id.duplicated().any():
        dupes = labels_df.sample_id[labels_df.sample_id.duplicated()].unique().tolist()
        raise ValueError(f"duplicate sample_id in labels.csv: {dupes}")
    key = ["sample_id", "record_hash"]
    merged = labels_df.merge(sample_df[key], on=key, how="outer", indicator=True)
    only_labels = merged[merged._merge == "left_only"]
    if not only_labels.empty:
        raise ValueError(
            "labels without a matching sample row: "
            + ", ".join(sorted(only_labels.sample_id.astype(str).unique())[:10]))
    only_sample = merged[merged._merge == "right_only"]
    if not only_sample.empty:
        raise ValueError(
            f"{len(only_sample)} sampled rows have no label "
            f"(e.g. {sorted(only_sample.sample_id.astype(str).unique())[:5]})")
    out = labels_df.merge(sample_df[["sample_id", "source", "character_key"]].rename(
        columns={"source": "sample_source", "character_key": "sample_character"}),
        on="sample_id", how="left")
    drifted = out[(out.source != out.sample_source)
                  | (out.character_key != out.sample_character)]
    if not drifted.empty:
        raise ValueError(
            "labels whose source/character differ from the rebuilt sample: "
            + ", ".join(sorted(drifted.sample_id.astype(str).unique())[:10]))
    return labels_df.copy()


def compute_precision(sample_df: pd.DataFrame, labels_df: pd.DataFrame) -> pd.DataFrame:
    """Precision rows: per (source, character) with n ≥ 10, else per source (`_all`).

    The `_all` row of each source always covers all its labels, so it doubles
    as the overall source precision for the §10.3 stop rule.
    """
    labels = _checked_labels(labels_df, sample_df)
    labels["is_correct"] = labels.label == "correct"
    rows: list[dict] = []
    for source in sorted(labels.source.unique()):
        sub = labels[labels.source == source]
        big = sub.value_counts("character_key")
        covered: set[str] = set()
        for char, n in big.items():
            if int(n) >= 10:
                covered.add(str(char))
                k = int(sub[sub.character_key == char].is_correct.sum())
                p, lo, hi = wilson(k, int(n))
                rows.append({"source": source, "character_key": str(char), "n": int(n),
                             "correct": k, "precision": p, "ci_low": lo, "ci_high": hi,
                             "treatment": treatment_for(p)})
        _ = covered  # per-char rows above; `_all` below always covers the whole source
        k_all = int(sub.is_correct.sum())
        p, lo, hi = wilson(k_all, len(sub))
        rows.append({"source": source, "character_key": "_all", "n": len(sub),
                     "correct": k_all, "precision": p, "ci_low": lo, "ci_high": hi,
                     "treatment": treatment_for(p)})
    return pd.DataFrame(rows, columns=list(PRECISION_COLUMNS)).sort_values(
        ["source", "character_key"]).reset_index(drop=True)


def sources_below_stop(precision_df: pd.DataFrame,
                       threshold: float = STOP_THRESHOLD) -> list[str]:
    """Sources whose overall (`_all`) precision is below the stop threshold."""
    overall = precision_df[precision_df.character_key == "_all"]
    return sorted(overall[overall.precision < threshold].source.tolist())


def _write_stop(sources: list[str], stop_path: Path) -> None:
    stop_path.parent.mkdir(parents=True, exist_ok=True)
    stop_path.write_text(
        "# STOP — keyword precision below threshold (ANALYSIS_PLAN.md §10.3)\n\n"
        f"Source(s) with overall precision < {STOP_THRESHOLD}: "
        + ", ".join(sources) + ".\n"
        "Evidence: reports/accuracy/precision.csv (`_all` rows) joined from "
        "reports/accuracy/labels.csv onto the deterministic sample (seed 20261023).\n"
        "Suggested fix: the pipeline re-checks the labelling for these sources; if the low "
        "precision stands, the lane matching rules must be repaired (shops/fans lanes) and "
        "the pipeline must relabel before scoring.\n")


def run(matches_dir: Path | None = None,
        sample_path: Path | None = None,
        labels_path: Path | None = None,
        precision_parquet: Path | None = None,
        precision_csv: Path | None = None,
        sample_csv: Path | None = None,
        stop_path: Path | None = None) -> pd.DataFrame:
    """Rebuild the sample, join labels, write precision outputs, enforce §10.3."""
    sample_df = draw_sample(load_matches(matches_dir), seed=SEED)
    stored = Path(sample_path) if sample_path is not None else work("accuracy", "sample.parquet")
    if stored.exists():
        on_disk = pd.read_parquet(stored)[["sample_id", "record_hash"]].sort_values("sample_id").reset_index(drop=True)
        rebuilt = sample_df[["sample_id", "record_hash"]].sort_values("sample_id").reset_index(drop=True)
        if not on_disk.equals(rebuilt):
            raise ValueError("rebuilt sample differs from work/accuracy/sample.parquet; "
                             "labels were made for a different sample")
    labels_file = Path(labels_path) if labels_path is not None else reports("accuracy", "labels.csv")
    if not labels_file.exists():
        raise FileNotFoundError(f"no labels at {labels_file}; the pipeline commits them first")
    labels_df = pd.read_csv(labels_file, dtype=str).convert_dtypes()
    precision_df = compute_precision(sample_df, labels_df)
    precision_file = Path(precision_parquet) if precision_parquet is not None else work("accuracy", "precision.parquet")
    precision_file.parent.mkdir(parents=True, exist_ok=True)
    precision_df.to_parquet(precision_file, index=False)
    csv_file = Path(precision_csv) if precision_csv is not None else reports("accuracy", "precision.csv")
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    precision_df.to_csv(csv_file, index=False)
    sample_out = pd.DataFrame({"sample_id": labels_df.sample_id, "source": labels_df.source,
                               "character": labels_df.character_key, "label": labels_df.label})
    sample_file = Path(sample_csv) if sample_csv is not None else reports("accuracy", "sample.csv")
    sample_out.to_csv(sample_file, index=False)
    bad = sources_below_stop(precision_df)
    if bad:
        _write_stop(bad, Path(stop_path) if stop_path is not None else reports("STOP.md"))
        raise RuntimeError(f"STOP (§10.3): overall precision < {STOP_THRESHOLD} for {bad}")
    return precision_df
