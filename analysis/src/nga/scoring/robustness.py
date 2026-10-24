"""Robustness and confidence (ANALYSIS_PLAN.md Section 7 rules 7-8).

- Leave-one-source-out: 7 runs, each dropping one in-score source.
- Three fixed alternative weightings (equal / shoppers_only / german_only).
- Kendall's W twice (§12 amendment 2026-10-23 §7.7): (a) headline across the
  in-score sources EXCLUDING google_trends, on the candidates every one of
  those ranks; (b) secondary across all 7 on complete cases, with n.
- Confidence labels: robust / one_source / mixed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .rank import ALT_WEIGHTS, IN_SCORE_SOURCES, run_ranking

# §12 amendment 2026-10-23 §7.7: the headline Kendall's W excludes
# google_trends (post-Q01b censoring leaves most of its scoring cells
# missing, so the 7-source W covers almost no candidates).
HEADLINE_SOURCES = tuple(s for s in IN_SCORE_SOURCES if s != "google_trends")


def kendall_w(ranks: pd.DataFrame) -> tuple[float, int]:
    """Kendall's coefficient of concordance with tie correction.

    ``ranks`` is subjects x judges (average ranks, no NaN: pre-filter to the
    candidates every source ranks). Returns (W, n_subjects). Undefined cases
    (fewer than 2 judges or subjects, zero denominator) return 0.0.
    """
    sub = ranks.dropna()
    # Re-rank the complete cases within each judge (average ties): source
    # ranks come from ranking all candidates a source covers, so the
    # complete-case subset can carry gaps (excluded candidates elsewhere).
    # Ranking gapped ranks is not Kendall's W (it can exceed 1 and breaks the
    # contract schema's [0, 1] range); the relative order - and hence the
    # judges' ranking of this subject set - is unchanged by re-ranking.
    sub = sub.rank(axis=0, ascending=True, method="average")
    n = len(sub)
    m = sub.shape[1]
    if m < 2 or n < 2:
        return 0.0, n
    sums = sub.sum(axis=1)
    mean = m * (n + 1) / 2
    s = float(((sums - mean) ** 2).sum())
    tie = 0.0
    for col in sub.columns:
        _, counts = np.unique(sub[col].to_numpy(), return_counts=True)
        tie += sum(int(t) ** 3 - int(t) for t in counts if t > 1)
    denom = m * m * (n**3 - n) - m * tie
    if denom <= 0:
        return (1.0 if s == 0 else 0.0), n
    return float(12 * s / denom), n


def agreement_label(w: float) -> str:
    """Section 7.7: W < 0.3 weak, 0.3-0.6 moderate, > 0.6 strong."""
    if w < 0.3:
        return "weak"
    if w > 0.6:
        return "strong"
    return "moderate"


def kendall_dual(source_ranks: pd.DataFrame) -> dict:
    """Both Kendall's W values (§12 amendment 2026-10-23 §7.7).

    ``source_ranks`` is candidates x in-score sources (average ranks, NaN
    where a source doesn't rank the candidate). Returns
    {"w_headline", "n_headline", "w_all7", "n_all7"}: (a) over
    HEADLINE_SOURCES on the candidates every one of those ranks, (b) over
    all 7 on complete cases.
    """
    w_head, n_head = kendall_w(source_ranks[list(HEADLINE_SOURCES)])
    w_all7, n_all7 = kendall_w(source_ranks[list(IN_SCORE_SOURCES)])
    return {
        "w_headline": float(w_head),
        "n_headline": int(n_head),
        "w_all7": float(w_all7),
        "n_all7": int(n_all7),
    }


def leave_one_out(
    values: pd.DataFrame, weights: dict[str, float], main_top3: list[str]
) -> tuple[list[dict], int]:
    """7 runs each dropping one in-score source.

    Returns (per-run [{dropped, top3}] details, same_top3 count of runs whose
    top-3 *set* equals the main top-3 set).
    """
    main_set = set(main_top3)
    runs = []
    for dropped in IN_SCORE_SOURCES:
        kept = [s for s in IN_SCORE_SOURCES if s != dropped]
        top3 = run_ranking(values, kept, weights)["top3"]
        runs.append({"dropped": dropped, "top3": top3})
    same = sum(1 for r in runs if set(r["top3"]) == main_set)
    return runs, same


def alt_weight_runs(
    values: pd.DataFrame, main_top3: list[str]
) -> list[dict]:
    """Rank under each fixed alternative weighting; same_top3 is set equality."""
    main_set = set(main_top3)
    out = []
    for name, weights in ALT_WEIGHTS.items():
        top3 = run_ranking(values, list(IN_SCORE_SOURCES), weights)["top3"]
        out.append(
            {
                "name": name,
                "weights": dict(weights),
                "top3": top3,
                "same_top3": set(top3) == main_set,
            }
        )
    return out


def label_confidence(
    character_key: str,
    main_top3: list[str],
    loo_hits: int,
    alt_hits: int,
    n_alt: int,
    main_rank: int | None,
    n_sources_top3: int,
) -> str | None:
    """Section 7.8: robust / one_source / mixed (None when unscored)."""
    if main_rank is None:
        return None
    if character_key in set(main_top3) and loo_hits >= 6 and alt_hits == n_alt:
        return "robust"
    if n_sources_top3 == 1 and main_rank > 6:
        return "one_source"
    return "mixed"
