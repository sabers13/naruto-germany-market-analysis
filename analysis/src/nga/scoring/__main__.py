"""CLI: uv run python -m nga.scoring.

Reads work/metrics/*.parquet (+ work/accuracy/precision.parquet when present)
and writes work/score/characters.parquet, work/score/robustness.json and
work/score/source_ranks.parquet.
"""

from __future__ import annotations

import json

import pandas as pd

from nga import metrics as metrics_mod
from nga.paths import reports, work
from nga.scoring import check_precision_floor, score


def write_outputs(result, score_dir) -> None:
    score_dir.mkdir(parents=True, exist_ok=True)
    result.characters.to_parquet(score_dir / "characters.parquet", index=False)
    result.source_ranks.to_parquet(score_dir / "source_ranks.parquet", index=False)
    (score_dir / "robustness.json").write_text(
        json.dumps(result.robustness, indent=2) + "\n"
    )


def stop(message: str) -> None:
    reports_dir = reports()
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "STOP.md").write_text(
        "# STOP\n\n"
        f"Triggered by `uv run python -m nga.scoring`: {message}\n"
    )
    raise RuntimeError(message)


def main() -> None:
    metrics_df = metrics_mod.read_all()
    precision_path = work("accuracy", "precision.parquet")
    precision_df = (
        pd.read_parquet(precision_path) if precision_path.exists() else None
    )
    if precision_df is not None:
        try:
            check_precision_floor(precision_df)
        except RuntimeError as exc:
            stop(str(exc))
    result = score(metrics_df, precision_df)
    n_scored = int(result.characters["rank"].notna().sum())
    if n_scored < 10:
        stop(
            f"fewer than 10 of 13 candidates scored ({n_scored}; "
            "ANALYSIS_PLAN.md Section 10.5)"
        )
    score_dir = work("score")
    write_outputs(result, score_dir)
    print(
        f"scored {len(result.characters)} candidates "
        f"({n_scored} with a score); "
        f"Kendall W={result.robustness['kendall_w']:.3f} "
        f"({result.robustness['agreement_label']}); "
        f"LOO same_top3={result.robustness['leave_one_out']['same_top3']}/7"
    )


if __name__ == "__main__":
    main()
