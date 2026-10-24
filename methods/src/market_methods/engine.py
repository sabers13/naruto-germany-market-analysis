"""Deterministic rank aggregation. No network or platform-specific dependencies."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def number(value, name, *, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return float(value)


def wilson(correct, total):
    """Observed precision and Wilson 95% interval; policy uses the point estimate."""
    if (type(correct) is not int or type(total) is not int
            or total < 1 or not 0 <= correct <= total):
        raise ValueError("quality counts need integers: 0 <= correct <= total, total > 0")
    p, z = correct / total, 1.96
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denominator
    return {"precision": p, "ci_low": max(0, centre - half), "ci_high": min(1, centre + half)}


def average_ranks(values, *, descending=True):
    """Average ties, omit missing values, use stable entity ordering."""
    ordered = sorted(((key, value) for key, value in values.items() if value is not None),
                     key=lambda item: ((-item[1] if descending else item[1]), item[0]))
    result, position = {}, 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and ordered[end][1] == ordered[position][1]:
            end += 1
        rank = (position + 1 + end) / 2
        result.update({key: rank for key, _ in ordered[position:end]})
        position = end
    return result


def kendall_w(columns):
    """Tie-corrected concordance on complete cases; undefined is null, never zero.

    Re-rank the common subset to avoid gaps from differently covered populations.
    """
    common = sorted(set.intersection(*(set(col) for col in columns))) if columns else []
    n, m = len(common), len(columns)
    result = {"w": None, "entities": n, "sources": m}
    if n < 2 or m < 2:
        return result
    ranks = [average_ranks({key: col[key] for key in common}, descending=False)
             for col in columns]
    mean = m * (n + 1) / 2
    squared = sum((sum(col[key] for col in ranks) - mean)**2 for key in common)
    ties = sum(sum(count**3 - count for count in Counter(col.values()).values())
               for col in ranks)
    denominator = m * m * (n**3 - n) - m * ties
    if denominator > 0:
        result["w"] = 12 * squared / denominator
    return result


def checked_config(config):
    sources = config.get("sources", {})
    if not sources or not all(isinstance(s, str) and s for s in sources):
        raise ValueError("sources must be a non-empty mapping")
    lenses = set()
    for spec in sources.values():
        if not isinstance(spec, dict) or not isinstance(spec.get("lens"), str) or not spec["lens"]:
            raise ValueError("every source needs a lens")
        if spec.get("direction", "higher") != "higher":
            raise ValueError("this method accepts higher-is-stronger metrics only")
        lenses.add(spec["lens"])
    def weights_valid(weights):
        if set(weights) != lenses:
            raise ValueError("weights must name every configured lens exactly once")
        total = sum(number(w, "weight") for w in weights.values())
        if not math.isfinite(total):
            raise ValueError("weight sum must be finite")
        if total <= 0:
            raise ValueError("at least one weight must be positive")
    weights_valid(config.get("weights", {}))
    for weights in config.get("alternative_weights", {}).values():
        weights_valid(weights)
    coverage = number(config.get("minimum_lens_coverage", 0.5), "coverage")
    if not 0 < coverage <= 1:
        raise ValueError("coverage must be in (0, 1]")
    return sources, coverage


def prepare(metrics, quality, sources):
    cells = {}
    for row in metrics:
        entity, source = row.get("entity"), row.get("source")
        if not isinstance(entity, str) or not entity or source not in sources:
            raise ValueError("each metric needs a non-empty entity and a configured source")
        key = (entity, source)
        if key in cells:
            raise ValueError(f"duplicate entity/source metric: {key}")
        cells[key] = None if row.get("value") is None else number(row["value"], "metric")
    if not cells:
        raise ValueError("at least one metric is required")
    checks = {}
    for row in quality:
        source, entity = row.get("source"), row.get("entity", "*")
        if source not in sources or (entity != "*" and (entity, source) not in cells):
            raise ValueError("quality row must target a known source and metric, or '*'")
        key = (entity, source)
        if key in checks:
            raise ValueError("duplicate quality assessment")
        check = wilson(row["correct"], row["total"])
        p = check["precision"]
        if entity == "*" and p < 0.5:
            raise ValueError(f"quality stop: {source} overall precision is below 0.50")
        checks[key] = {**check, "treatment": "use" if p >= .9 else "adjust" if p >= .7 else "exclude"}
    adjusted, treatments = {}, {}
    for key, value in cells.items():
        check = checks.get(key, checks.get(("*", key[1])))
        treatment = check["treatment"] if check else "unassessed"
        adjusted[key] = (None if value is None or treatment == "exclude"
                         else value * check["precision"] if treatment == "adjust" else value)
        treatments[key] = treatment
    return adjusted, treatments, checks


def rank_run(cells, sources, active, coverage, weights):
    entities = sorted({entity for entity, _ in cells})
    columns = {source: average_ranks(
        {entity: cells.get((entity, source)) for entity in entities},
        descending=sources[source].get("direction", "higher") == "higher") for source in active}
    rows = []
    for entity in entities:
        lenses = {}
        for lens in sorted(weights):
            members = [s for s in active if sources[s]["lens"] == lens]
            observed = [columns[s][entity] for s in members if entity in columns[s]]
            lenses[lens] = (sum(observed) / len(observed)
                            if members and len(observed) >= math.ceil(coverage * len(members)) else None)
        available = [(value, weights[lens]) for lens, value in lenses.items()
                     if value is not None and weights[lens] > 0]
        total_weight = sum(weight for _, weight in available)
        score = sum(value * (weight / total_weight) for value, weight in available) if available else None
        index = ((len(entities) - score) / (len(entities) - 1) * 100
                 if score is not None and len(entities) > 1 else None)
        rows.append({"entity": entity, "score": score, "index": index, "lens_ranks": lenses,
                     "source_ranks": {s: columns[s].get(entity) for s in sorted(active)}})
    rows.sort(key=lambda row: (row["score"] is None, row["score"] or 0, row["entity"]))
    ranks = average_ranks({row["entity"]: row["score"] for row in rows}, descending=False)
    for row in rows:
        row["rank"] = ranks.get(row["entity"])
    return rows, columns


def build_report(metrics, config, quality=None):
    """Rank supplied aggregate metrics and assess sensitivity; no data acquisition.

    This is a portfolio demonstration of the method, not the original study release.
    """
    sources, coverage = checked_config(config)
    quality = quality or []
    cells, treatments, checks = prepare(metrics, quality, sources)
    active = sorted(sources)
    rows, columns = rank_run(cells, sources, active, coverage, config["weights"])
    k = config.get("top_k", 3)
    if type(k) is not int or k < 1:
        raise ValueError("top_k must be a positive integer")
    def top(table):
        return [row["entity"] for row in table if row["score"] is not None][:k]
    main = top(rows)
    runs = []
    for source in active:
        table, _ = rank_run(cells, sources, [s for s in active if s != source], coverage, config["weights"])
        selected = top(table)
        runs.append({"dropped": source, "top": selected, "same_members": set(selected) == set(main)})
    alternatives = []
    for name, weights in sorted(config.get("alternative_weights", {}).items()):
        table, _ = rank_run(cells, sources, active, coverage, weights)
        selected = top(table)
        alternatives.append({"name": name, "weights": weights, "top": selected,
                             "same_members": set(selected) == set(main)})
    for row in rows:
        row["quality_treatments"] = {s: treatments.get((row["entity"], s), "missing") for s in active}
    eligible = [row for row in rows if row["score"] is not None]
    boundary_tie = len(eligible) > k and eligible[k - 1]["score"] == eligible[k]["score"]
    normalized = [{"entity": r["entity"], "source": r["source"],
                   "value": None if r.get("value") is None else float(r["value"])}
                  for r in sorted(metrics, key=lambda r: (r["entity"], r["source"]))]
    payload = {
        "schema_version": "1.0.0", "method_version": "0.1.0",
        "data_kind": "synthetic" if config.get("synthetic") is True else "user_supplied_unverified",
        "provenance": {"metrics_sha256": digest(normalized), "config_sha256": digest(config),
                       "quality_sha256": digest(sorted(quality, key=lambda r: (r["source"], r.get("entity", "*"))))},
        "ranking": rows,
        "robustness": {"top": main, "top_boundary_tie": boundary_tie,
                       "leave_one_out": runs, "alternative_weights": alternatives,
                       "kendall": kendall_w(list(columns.values()))},
        "quality": [{"entity": e, "source": s, **check} for (e, s), check in sorted(checks.items())],
        "limitations": [
            "Evidence indices are relative ranks, not sales forecasts or probabilities.",
            "Missing observations remain missing; available lens weights are renormalized.",
            "Within-source ranks may cover different entity sets; compare coverage before interpretation.",
            "Quality adjustment is a heuristic, not an unbiased correction or uncertainty propagation.",
            "Sensitivity checks are descriptive, not statistical confidence intervals.",
            "Top-k membership breaks score ties alphabetically; inspect top_boundary_tie.",
            "Input hashes establish reproducibility, not access or redistribution permission.",
        ],
    }
    return {**payload, "release_id": digest(payload)}
