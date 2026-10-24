"""Single-hop anchor rescaling (archive docs/limits_and_comparability.md §6.3).

Every non-reference batch is rescaled DIRECTLY onto the reference batch via
one shared anchor term present in both batches:

    k = mean(anchor in reference) / mean(anchor in batch)

over the overlapping non-partial buckets, then value_rescaled = value_raw * k.
Batches without the anchor are refused (caller marks the series missing);
chained/multi-hop bridges are never built.
"""
from __future__ import annotations

import pandas as pd


class NoDirectAnchor(Exception):
    """A batch shares no anchor term with the reference: cannot rescale."""


def anchor_mean(df: pd.DataFrame, anchor: str) -> float:
    """Mean raw value of the anchor term over non-partial buckets."""
    vals = df.loc[(df["term_raw"] == anchor) & (~df["is_partial"]), "value"]
    if len(vals) == 0:
        raise NoDirectAnchor(f"anchor {anchor!r} has no complete buckets")
    mean = float(vals.mean())
    if mean <= 0:
        raise NoDirectAnchor(f"anchor {anchor!r} mean is {mean}: degenerate scale")
    return mean


def bridge_factor_k(ref_df: pd.DataFrame, other_df: pd.DataFrame, anchor: str) -> float:
    """Direct single-hop factor placing other_df on ref_df's scale.

    Raises NoDirectAnchor if the anchor is absent from either frame, so a
    chained rescale can never silently happen here.
    """
    if anchor not in set(ref_df["term_raw"]):
        raise NoDirectAnchor(f"anchor {anchor!r} not in reference batch")
    if anchor not in set(other_df["term_raw"]):
        raise NoDirectAnchor(f"anchor {anchor!r} not in batch")
    return anchor_mean(ref_df, anchor) / anchor_mean(other_df, anchor)


def rescale_series(df: pd.DataFrame, term: str, k: float) -> pd.DataFrame:
    """Rescaled weekly series for one term (raw values kept alongside)."""
    out = df.loc[df["term_raw"] == term,
                 ["bucket_start_utc", "value", "is_partial"]].copy()
    out = out.rename(columns={"value": "value_raw"})
    out["value_rescaled"] = out["value_raw"] * k
    return out.sort_values("bucket_start_utc").reset_index(drop=True)
