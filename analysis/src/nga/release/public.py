"""Public edition of the release (§12 2026-10-23, contract 1.2.0).

The full release stays the complete document. The public edition is the
same document minus what is not published:

- Kleinanzeigen figures (the platform's terms require written consent for
  automated access, so its figures stay local): ad counts, prices, accuracy,
  record counts and Naruto's benchmark value become null or are dropped, and
  the KPIs leave the ads out. Kleinanzeigen still feeds the evidence index,
  and meta.notes says so.
- The Kleinanzeigen ``regions`` block (the Trends ``regions_trends`` stays).
"""
from __future__ import annotations

import copy
import hashlib

from . import provenance
from .build import dump_bytes

HIDDEN_SOURCE = "kleinanzeigen"

PUBLIC_NOTE = (
    "Public edition: Kleinanzeigen figures are not published; the source "
    "still feeds the evidence index."
)


def public_edition(doc: dict) -> dict:
    """Return the public edition of a built full release ``doc``."""
    out = copy.deepcopy(doc)
    hidden = next((s for s in out["sources"] if s["id"] == HIDDEN_SOURCE), None)
    if hidden is None or hidden["records"] is None:
        raise ValueError("public edition: needs the full release's kleinanzeigen record count")
    hidden_records = int(hidden["records"])

    out["meta"]["edition"] = "public"
    out["meta"]["notes"] = list(out["meta"]["notes"]) + [PUBLIC_NOTE]
    out.pop("regions", None)

    for c in out["characters"]:
        c["counts"]["kleinanzeigen_ads"] = None
        c["prices_eur"]["kleinanzeigen"] = None
        if isinstance(c.get("accuracy"), dict):
            c["accuracy"].pop(HIDDEN_SOURCE, None)

    hidden["records"] = None
    # shop_listings_checked = Amazon cards + eBay items + Kleinanzeigen ads
    # (plan §8); records_counted sums in-score source records. Both include
    # the same total_ads figure, which is the source's records count.
    out["kpis"]["shop_listings_checked"] -= hidden_records
    out["kpis"]["records_counted"] -= hidden_records

    for s in out["benchmark_comparison"]["sources"]:
        if s["id"] == HIDDEN_SOURCE:
            s["benchmark_value"] = None
    for body in out["benchmark_comparison"]["by_character"].values():
        if body["ratios"].get(HIDDEN_SOURCE) is not None:
            raise ValueError("public edition: Kleinanzeigen must not be comparable")

    out["meta"]["release_id"] = ""
    content_hash = hashlib.sha256(dump_bytes(out)).hexdigest()
    out["meta"]["release_id"] = provenance.release_id_for(
        out["meta"]["contract_version"], out["meta"]["snapshot_date"], content_hash)
    return out
