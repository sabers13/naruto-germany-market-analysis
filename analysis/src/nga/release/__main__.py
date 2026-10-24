"""CLI: uv run python -m nga.release → release/dashboard.json + .sha256."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from nga.paths import release as release_path, work


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(description="Build release/dashboard.json.")
    ap.add_argument("--aux-dir", default=str(work("aux")))
    ap.add_argument("--release-dir", default=str(release_path()))
    ap.add_argument("--result", default=None,
                    help="Synthetic result JSON (characters/robustness/weights/counts). "
                         "Without it, the real pipeline runs (needs nga.scoring).")
    args = ap.parse_args(argv)

    from .build import build, write_release

    if args.result:
        result = json.loads(Path(args.result).read_text())
    else:
        from nga.metrics import read_all

        from nga.scoring import score  # type: ignore[import-not-found]

        metrics_df = read_all()
        prec_path = work("accuracy", "precision.parquet")
        import pandas as pd

        precision = pd.read_parquet(prec_path) if prec_path.exists() else None
        scored = score(metrics_df, precision_df=precision)
        weights = getattr(scored, "weights", {"shoppers": 0.5, "watching": 0.3, "votes": 0.2})
        result = {
            "characters": scored.characters,
            "robustness": scored.robustness,
            "weights": dict(weights),
            "metrics": metrics_df,
            "precision": precision,
            "detail": dict(scored.detail),
        }
    doc = build(result, args.aux_dir)
    out = write_release(doc, args.release_dir)
    from .public import public_edition

    write_release(public_edition(doc), args.release_dir, name="dashboard.public")
    return out


if __name__ == "__main__":
    print(main())
