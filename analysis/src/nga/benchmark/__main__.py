"""Benchmark pipeline: fair benchmark comparison with Naruto (ANALYSIS_PLAN.md §13).

Reads the lane metrics, the accuracy precision table and the Trends weekly
archive table; writes work/aux/benchmark.json (gitignored).
"""
from __future__ import annotations

import json

import pandas as pd

from nga import metrics
from nga.benchmark.compare import compare
from nga.paths import check_archive, reports, work
from nga.trends.__main__ import load_weekly


def run() -> dict:
    check_archive()
    metrics_df = metrics.read_all()
    precision_df = pd.read_csv(reports("accuracy", "precision.csv"))
    doc = compare(metrics_df, precision_df, load_weekly())
    out = work("aux", "benchmark.json")
    out.write_text(json.dumps(doc, indent=2, sort_keys=False) + "\n")
    return doc


def main() -> None:
    doc = run()
    for s in doc["sources"]:
        mark = "comparable" if s["comparable"] else "not comparable"
        print(f"  {s['id']:<18} {mark:<15} {s['reason']:<20} "
              f"benchmark={s['benchmark_value']} ({s['detail']})")
    n_comp = sum(1 for s in doc["sources"] if s["comparable"])
    # §12 (2026-10-23): one comparable source is enough to publish the
    # comparison; the UI states how many sources it rests on.
    if n_comp < 1:
        raise RuntimeError(
            f"STOP (§13): no comparable source; need >= 1")
    print(f"comparable sources: {n_comp}")


if __name__ == "__main__":
    main()
