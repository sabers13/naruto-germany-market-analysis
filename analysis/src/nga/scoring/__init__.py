"""Scoring API (docs/INTERFACES.md).

result = score(metrics_df, precision_df=None, weights={...})
result.characters  # character_key, rank, index, score, lens ranks, top3_sources, confidence, flags
result.robustness  # dict shaped like the contract's `robustness` object
result.source_ranks  # character_key x source rank (highest = 1)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import rank as _rank
from . import robustness as _rob
from .rank import (
    ALT_WEIGHTS,
    DEFAULT_WEIGHTS,
    IN_SCORE_SOURCES,
    LENSES,
    apply_precision,
    candidate_values,
    check_precision_floor,
    evidence_index,
    run_ranking,
    top3_sources_from_ranks,
)


@dataclass
class ScoreResult:
    characters: pd.DataFrame
    robustness: dict
    source_ranks: pd.DataFrame
    # Extra diagnostics (not part of the contract object): weights used,
    # number of complete-case candidates for Kendall's W, per-run details.
    detail: dict = field(default_factory=dict)


def score(
    metrics_df: pd.DataFrame,
    precision_df: pd.DataFrame | None = None,
    weights: dict[str, float] | None = None,
) -> ScoreResult:
    """Rank candidates per ANALYSIS_PLAN.md Section 7 (rules 1-8)."""
    weights = dict(DEFAULT_WEIGHTS) if weights is None else dict(weights)
    for lens in LENSES:
        if lens not in weights:
            raise ValueError(f"missing lens weight: {lens}")

    values = candidate_values(metrics_df)
    adjusted, flags = apply_precision(values, precision_df)

    main = run_ranking(adjusted, list(IN_SCORE_SOURCES), weights)
    source_ranks = main["source_ranks"]
    lens = main["lens"]
    table = main["table"]
    main_top3 = main["top3"]

    n_top3 = top3_sources_from_ranks(source_ranks)

    loo_runs, loo_same = _rob.leave_one_out(adjusted, weights, main_top3)
    alt_runs = _rob.alt_weight_runs(adjusted, main_top3)

    dual = _rob.kendall_dual(source_ranks)
    w, n_complete = dual["w_headline"], dual["n_headline"]

    loo_hits = {
        char: sum(1 for r in loo_runs if char in set(r["top3"]))
        for char in source_ranks.index
    }
    alt_hits = {
        char: sum(1 for r in alt_runs if char in set(r["top3"]))
        for char in source_ranks.index
    }

    # Section 7.5 ranks: sequential over the ordered table; unscored get null.
    tidx = table.set_index("character_key")
    rank_of: dict[str, int | None] = {}
    for i, char in enumerate(table["character_key"], start=1):
        rank_of[char] = i if pd.notna(tidx.loc[char, "score"]) else None

    rows = []
    for char in sorted(source_ranks.index):
        sc = tidx.loc[char, "score"]
        rows.append(
            {
                "character_key": char,
                "rank": rank_of[char],
                "index": evidence_index(sc),
                "score": float(sc) if pd.notna(sc) else np.nan,
                "shoppers": float(lens.loc[char, "shoppers"])
                if pd.notna(lens.loc[char, "shoppers"])
                else np.nan,
                "watching": float(lens.loc[char, "watching"])
                if pd.notna(lens.loc[char, "watching"])
                else np.nan,
                "votes": float(lens.loc[char, "votes"])
                if pd.notna(lens.loc[char, "votes"])
                else np.nan,
                "top3_sources": int(n_top3.loc[char]),
                "confidence": _rob.label_confidence(
                    char,
                    main_top3,
                    loo_hits[char],
                    alt_hits[char],
                    len(alt_runs),
                    rank_of[char],
                    int(n_top3.loc[char]),
                ),
                "flags": sorted(flags.get(char, set())),
            }
        )
    characters = pd.DataFrame(rows)
    # Ranked first (by rank), then unscored alphabetically.
    characters["rank"] = characters["rank"].astype("Int64")
    characters["index"] = characters["index"].astype("Int64")
    characters = characters.sort_values(
        ["rank", "character_key"], na_position="last"
    ).reset_index(drop=True)

    robustness = {
        "kendall_w": float(w),
        "agreement_label": _rob.agreement_label(float(w)),
        "leave_one_out": {
            "runs": len(loo_runs),
            "same_top3": int(loo_same),
            "top3": list(main_top3),
        },
        "alt_weights": [
            {
                "name": r["name"],
                "weights": {k: float(v) for k, v in r["weights"].items()},
                "top3": list(r["top3"]),
                "same_top3": bool(r["same_top3"]),
            }
            for r in alt_runs
        ],
    }

    source_ranks_out = source_ranks.reset_index().rename(
        columns={"index": "character_key"}
    )
    if "character_key" not in source_ranks_out.columns:
        source_ranks_out = source_ranks_out.rename(
            columns={source_ranks_out.columns[0]: "character_key"}
        )

    detail = {
        "weights": {k: float(v) for k, v in weights.items()},
        "n_complete": int(n_complete),
        "kendall_w_all7": float(dual["w_all7"]),
        "n_complete_all7": int(dual["n_all7"]),
        "main_top3": list(main_top3),
        "loo_runs": [
            {"dropped": r["dropped"], "top3": list(r["top3"])} for r in loo_runs
        ],
    }
    return ScoreResult(
        characters=characters, robustness=robustness,
        source_ranks=source_ranks_out, detail=detail,
    )


__all__ = [
    "ALT_WEIGHTS",
    "DEFAULT_WEIGHTS",
    "IN_SCORE_SOURCES",
    "ScoreResult",
    "apply_precision",
    "check_precision_floor",
    "score",
]
