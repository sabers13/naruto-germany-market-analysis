"""Assemble release/dashboard.json from the score result plus aux files.

Implements ANALYSIS_PLAN.md §8 (other outputs) and §9 (release), exactly in
the shape of contract/dashboard.schema.json. Built against synthetic inputs
shaped like contract/preview.fixture.json; the pipeline runs it for real.

Public API (docs/INTERFACES.md):
    from nga.release import build
    doc = build(result, aux_dir=work("aux"))  # validated before return
CLI: uv run python -m nga.release
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import yaml
from jsonschema import validate as schema_validate

from nga import characters as charlib
from nga.paths import REPO, release as release_path, work
from nga.trends import ANCHOR_TERM, SERIES as TRENDS_SERIES

from . import provenance

SCHEMA = json.loads((REPO / "contract/dashboard.schema.json").read_text())

REQUIRED_AUX = [
    "prices.parquet",
    "merch.parquet",
    "regions.parquet",
    "trends_regions.parquet",
    "momentum.parquet",
    "events.json",
]
# The benchmark output, loaded separately so a missing file raises a clear error
# (values are never invented here). Not in REQUIRED_AUX for that reason.
BENCHMARK_FILE = "benchmark.json"

LENSES = ("shoppers", "watching", "votes")

# (source, metric) in the long metrics table -> contract counts field.
METRIC_TO_COUNT = {
    ("amazon", "asins"): "amazon_products",
    ("ebay", "items"): "ebay_items",
    ("kleinanzeigen", "offer_ads"): "kleinanzeigen_ads",
    ("youtube", "videos_de"): "youtube_videos_de",
    ("youtube", "comments_de"): "youtube_comments_de",
    ("anime2you", "articles"): "anime2you_articles",
    ("anime2you", "comment_mentions"): "anime2you_comment_mentions",
    ("narutop99", "votes_eu"): "fan_votes_eu",
    ("google_trends", "interest_52w"): "google_interest",
}
COUNT_FIELDS = (
    "amazon_products",
    "ebay_items",
    "kleinanzeigen_ads",
    "youtube_videos_de",
    "youtube_comments_de",
    "anime2you_articles",
    "anime2you_comment_mentions",
    "fan_votes_eu",
    "google_interest",
)
REQUIRED_COUNTS = [f for f in COUNT_FIELDS if f != "anime2you_comment_mentions"]

MERCH_CATEGORIES = ["figures", "clothing", "cards", "manga_media", "accessories", "other"]
MERCH_MIN_ITEMS = 100
SUPPRESS_BELOW = 10
PERIOD_RE = re.compile(r"^\d{4}-\d{2}$")
URL_RE = re.compile(r"https?://", re.IGNORECASE)


def _records(table) -> list[dict]:
    if table is None:
        return []
    if isinstance(table, pd.DataFrame):
        return [dict(r) for r in table.to_dict("records")]
    return [dict(r) for r in table]


def _num(x, nd: int):
    """Round a scalar to nd decimals (None/NaN → None).

    The single place where release rounding lives: every rounded contract
    field goes through _r1/_r2/_r3/_ri below.
    """
    if x is None:
        return None
    if not isinstance(x, str) and pd.isna(x):
        return None
    return round(float(x), nd)


def _r1(x):
    return _num(x, 1)


def _r2(x):
    return _num(x, 2)


def _r3(x):
    return _num(x, 3)


def _ri(x):
    """Integer field (index, counts): None/NaN → None, else rounded int."""
    v = _num(x, 0)
    return None if v is None else int(v)


def _result_get(result, key: str, default=None):
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def _load_aux(aux_dir: Path) -> dict:
    missing = [f for f in REQUIRED_AUX if not (aux_dir / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"release aux missing: {', '.join(missing)} (looked in {aux_dir})"
        )
    kpis_files = sorted(aux_dir.glob("kpis_*.json"))
    if not kpis_files:
        raise FileNotFoundError(f"release aux missing: kpis_*.json (looked in {aux_dir})")
    sources_files = sorted(aux_dir.glob("sources_*.json"))
    if not sources_files:
        raise FileNotFoundError(f"release aux missing: sources_*.json (looked in {aux_dir})")
    kpis: dict = {}
    for f in kpis_files:
        part = json.loads(f.read_text())
        if not isinstance(part, dict):
            raise ValueError(f"release aux malformed: {f.name} must hold a JSON object")
        kpis.update(part)
    sources: list[dict] = []
    for f in sources_files:
        part = json.loads(f.read_text())
        if not isinstance(part, list):
            raise ValueError(f"release aux malformed: {f.name} must hold a JSON list")
        sources.extend(part)
    sources = _merge_sources(sources)
    momentum = pd.read_parquet(aux_dir / "momentum.parquet")
    sources = _exclude_censored_trends_rows(sources, momentum)
    return {
        "prices": pd.read_parquet(aux_dir / "prices.parquet"),
        "merch": pd.read_parquet(aux_dir / "merch.parquet"),
        "regions": pd.read_parquet(aux_dir / "regions.parquet"),
        "trends_regions": pd.read_parquet(aux_dir / "trends_regions.parquet"),
        "momentum": momentum,
        "events": json.loads((aux_dir / "events.json").read_text()),
        "kpis": kpis,
        "sources": sources,
    }


def _load_benchmark(aux_dir: Path) -> dict:
    """Load the benchmark_comparison, rounded to the contract's 2 dp.

    Missing file → clear error naming the benchmark command. Values are never
    invented here: without work/aux/benchmark.json there is no release.
    """
    path = aux_dir / BENCHMARK_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"release aux missing: {BENCHMARK_FILE} (looked in {aux_dir}); "
            "run `uv run python -m nga.benchmark` first"
        )
    doc = json.loads(path.read_text())
    if not isinstance(doc, dict) or doc.get("benchmark") != "naruto_uzumaki":
        raise ValueError(f"release aux malformed: {BENCHMARK_FILE} must hold the contract's benchmark_comparison object")
    for src in doc.get("sources", []):
        src["benchmark_value"] = _r2(src.get("benchmark_value"))
    for entry in doc.get("by_character", {}).values():
        entry["ratios"] = {
            k: _r2(v) for k, v in (entry.get("ratios") or {}).items()
        }
    return doc


def _characters_table(result) -> dict[str, dict]:
    """Normalise the score result to {key: row}. Accepts a ScoreResult-like
    object (result.characters DataFrame) or a plain dict."""
    rows = _records(_result_get(result, "characters", []))
    if not rows:
        raise ValueError("release: score result holds no characters")
    out: dict[str, dict] = {}
    for r in rows:
        key = r.get("character_key", r.get("key"))
        if key is None:
            raise ValueError(f"release: character row without a key: {sorted(r)}")
        lr = r.get("lens_ranks")
        if lr is None:
            vals = [r.get(f"lens_{lens}", r.get(lens)) for lens in LENSES]
            lr = None if all(v is None for v in vals) else dict(zip(LENSES, vals))
        elif not isinstance(lr, dict):
            raise ValueError(f"release: lens_ranks for {key} must be a mapping or null")
        out[key] = {
            "key": key,
            "rank": r.get("rank"),
            "index": r.get("index"),
            "lens_ranks": lr,
            "top3_sources": r.get("top3_sources"),
            "confidence": r.get("confidence"),
            "flags": list(r.get("flags") or []),
            "counts": dict(r.get("counts") or {}),
        }
    return out


def _metrics_counts(result) -> dict[str, dict[str, float]]:
    """{character_key: {counts_field: value}} from the long metrics table."""
    tables = []
    for key in ("metrics", "metrics_df"):
        t = _result_get(result, key)
        if t is not None:
            tables.append(t)
    if not tables:
        return {}
    df = pd.concat(
        [t if isinstance(t, pd.DataFrame) else pd.DataFrame(list(t)) for t in tables],
        ignore_index=True,
    )
    out: dict[str, dict[str, float]] = {}
    for (source, metric), field in METRIC_TO_COUNT.items():
        sub = df[(df["source"] == source) & (df["metric"] == metric)]
        if sub.empty:
            continue
        pref = sub[sub["period"].isin(["snapshot", "last_52w"])]
        pick = pref if not pref.empty else sub
        for _, row in pick.sort_values("period").drop_duplicates("character_key").iterrows():
            if pd.notna(row["value"]):
                out.setdefault(str(row["character_key"]), {})[field] = float(row["value"])
    return out


def _precision_maps(result, aux: dict) -> tuple[dict, dict]:
    """(({source: {key: precision}}), ({key: {extra flags}})).

    From work/accuracy/precision.parquet (the pipeline columns) when present in aux,
    else from result["precision"]. Rows for "_all" apply to every character.
    """
    table = aux.get("precision")
    if table is None:
        table = _result_get(result, "precision")
    rows = [r for r in _records(table) if r.get("source") and r.get("character_key")]
    benchmark = set(charlib.keys("benchmark"))
    exact_keys = {
        (str(r["source"]), str(r["character_key"]))
        for r in rows
        if str(r["character_key"]) != "_all"
    }
    prec: dict[str, dict[str, float]] = {}
    flags: dict[str, set[str]] = {}
    for r in rows:
        source, key = str(r["source"]), str(r["character_key"])
        if r.get("precision") is None:
            continue
        if key == "_all":
            # Fallback: only characters without an exact cell actually receive
            # this row's value and treatment (mirrors scoring lookup).
            value_targets = [
                k for k in charlib.keys() if (source, k) not in exact_keys
            ]
        else:
            value_targets = [key]
        # Treatments (and their flags) apply to scoring, which never includes
        # the benchmark; the accuracy *values* are measurements shown for all.
        flag_targets = [k for k in value_targets if k not in benchmark]
        for k in value_targets:
            if k == key or k not in prec.get(source, {}):
                prec.setdefault(source, {})[k] = float(r["precision"])
        treatment = r.get("treatment")
        add = {"adjust": "low_precision", "exclude": "excluded_source"}.get(treatment)
        if add:
            for k in flag_targets:
                flags.setdefault(k, set()).add(add)
    return prec, {k: sorted(v) for k, v in flags.items()}


def _build_characters(char_rows, metrics_counts, result_counts, prec, prec_flags, prices) -> list[dict]:
    by_price: dict[str, dict[str, float | None]] = {}
    if prices is not None and not prices.empty:
        for _, r in prices.iterrows():
            n = r.get("n")
            if n is not None and not (isinstance(n, float) and n != n) and int(n) >= 10 and pd.notna(r["median_eur"]):
                by_price.setdefault(str(r["character_key"]), {})[str(r["platform"])] = _r2(
                    r["median_eur"]
                )
    entries = []
    ranked = sorted(
        [r for r in char_rows.values() if r["rank"] is not None], key=lambda r: r["rank"]
    )
    order = ranked + [r for r in char_rows.values() if r["rank"] is None]
    for r in order:
        key = r["key"]
        role = "benchmark" if key in charlib.keys("benchmark") else "candidate"
        counts = {}
        for field in COUNT_FIELDS:
            v = r["counts"].get(field)
            if v is None:
                v = result_counts.get(key, {}).get(field)
            if v is None:
                v = metrics_counts.get(key, {}).get(field)
            if field == "google_interest":
                counts[field] = _r2(v)
            else:
                counts[field] = _ri(v)
        if role == "benchmark":
            rank = index = lens = top3 = conf = None
        else:
            rank = r["rank"]
            index = _ri(r["index"])
            lens = None if r["lens_ranks"] is None else {k: _r2(v) for k, v in r["lens_ranks"].items()}
            top3, conf = r["top3_sources"], r["confidence"]
        accuracy = {
            source: _r3(per_key[key]) for source, per_key in prec.items() if key in per_key
        }
        entry = {
            "key": key,
            "name": charlib.name(key),
            "role": role,
            "rank": rank,
            "index": index,
            "lens_ranks": lens,
            "top3_sources": top3,
            "confidence": conf,
            "counts": counts,
            "prices_eur": {
                plat: by_price.get(key, {}).get(plat) for plat in ("amazon", "ebay", "kleinanzeigen")
            },
            "flags": sorted(set(charlib.flags(key)) | set(r["flags"]) | set(prec_flags.get(key, []))),
        }
        if accuracy:
            entry["accuracy"] = accuracy
        entries.append(entry)
    return entries


def _momentum_eligible(key: str) -> bool:
    """Plan §4/§8: every candidate with a topic series, plus Madara whose
    plain term is unambiguous. Pain has neither topic nor usable term."""
    src = charlib.load()["characters"][key]["source_keys"]
    if src.get("trends_topic"):
        return True
    return "ambiguous_name" not in charlib.flags(key)


def _reference_label(momentum: pd.DataFrame) -> tuple[str, str | None]:
    """Name + term/topic word for the shared Trends scale, from the trends lane's outputs.

    The scale anchor is Naruto's own matched series (the trends lane SERIES table): the
    plain term (its topic is censored), so the word is "term" — never
    "franchise term" (that would mean the /m/01hryy franchise topic).
    """
    name = charlib.name("naruto_uzumaki")
    nar = momentum[momentum["character_key"].astype(str) == "naruto_uzumaki"]
    if nar.empty:
        return name, None
    kinds = set(nar["series_kind"].astype(str))
    if kinds <= {"query", "term"}:
        return name, "term"
    if kinds == {"topic"}:
        return name, "topic"
    return name, None


def _build_momentum(char_rows, momentum: pd.DataFrame, metrics_counts: dict, result_counts: dict | None = None) -> dict:
    ranked_keys = [r["key"] for r in sorted(char_rows.values(), key=lambda r: (r["rank"] is None, r["rank"]))]
    candidates = [k for k in ranked_keys if k not in charlib.keys("benchmark")]
    six = [k for k in candidates[:3]]
    six += [k for k in candidates[3:] if k not in six and _momentum_eligible(k)][: 6 - len(six)]
    have = set(momentum["character_key"].astype(str))
    six = [k for k in six if k in have][:6]
    if len(six) < 6:
        raise ValueError(
            f"release: momentum needs 6 covered series, found {len(six)}: {six}"
        )
    sub = momentum[momentum["character_key"].astype(str).isin(six)].copy()
    bad = sorted({str(p) for p in sub["period"].unique() if not PERIOD_RE.match(str(p))})
    if bad:
        raise ValueError(f"release: momentum periods must be YYYY-MM, got {bad}")
    periods = sorted({str(p) for p in sub["period"].unique()})
    series, change, flags = {}, {}, {}
    for key in six:
        rows = sub[sub["character_key"].astype(str) == key].drop_duplicates("period")
        by_period = {str(r["period"]): r for _, r in rows.iterrows()}
        vals = [
            None if p not in by_period or pd.isna(by_period[p]["value"])
            else _r2(by_period[p]["value"])
            for p in periods
        ]
        series[key] = vals
        nums = [v for v in vals if v is not None]
        if len(nums) >= 8 and abs(sum(nums[-8:-4]) / 4) > 0:
            base, last = sum(nums[-8:-4]) / 4, sum(nums[-4:]) / 4
            change[key] = _r1((last - base) / base * 100)
        kinds = {str(by_period[p]["series_kind"]) for p in periods if p in by_period}
        rflags = set()
        for p in periods:
            if p in by_period and "flag" in by_period[p].index:
                f = by_period[p]["flag"]
                if pd.notna(f) and str(f) not in ("None", "nan", ""):
                    rflags.add(str(f))
        # ANALYSIS_PLAN.md §4: every shown series gets exactly one flag.
        # ambiguous_name takes precedence (Hinata); then censored; otherwise
        # the series kind from the trends lane's own flag column, falling back to
        # series_kind (the trends lane writes "query" for plain terms, synth uses "term").
        if "ambiguous_name" in charlib.flags(key):
            flags[key] = "ambiguous_name"
        elif "censored" in rflags:
            flags[key] = "censored"
        elif rflags and len(rflags) == 1 and next(iter(rflags)) in ("term_series", "topic_series"):
            flags[key] = next(iter(rflags))
        elif kinds and kinds <= {"term", "query"}:
            flags[key] = "term_series"
        elif kinds == {"topic"}:
            flags[key] = "topic_series"
        else:
            raise ValueError(
                f"release: momentum series flag undeterminable for {key}: "
                f"kinds={sorted(kinds)} flags={sorted(rflags)}"
            )
    scale_lookup: dict[str, dict] = {k: dict(v) for k, v in metrics_counts.items()}
    for k, v in (result_counts or {}).items():
        if isinstance(v, dict):
            for f, val in v.items():
                scale_lookup.setdefault(k, {}).setdefault(f, val)
    naruto_scale = scale_lookup.get("naruto_uzumaki", {}).get("google_interest")
    # The unit names the real reference from the trends lane's own outputs — the
    # plain search term (Naruto's character topic is censored) — never the
    # franchise term. kind_word ("term"/"topic") comes from the trends lane's
    # momentum.parquet series_kind for Naruto's own series.
    _ref_name, kind_word = _reference_label(momentum)
    if naruto_scale is not None and kind_word is not None:
        scale_txt = str(_r2(naruto_scale))
        unit = (f"Google search index on one shared scale (reference: search "
                f"{kind_word} {ANCHOR_TERM!r} = {scale_txt})")
    else:
        unit = "index (rescaled German search interest)"
    return {
        "source": "google_trends_de",
        "unit": unit,
        "periods": periods,
        "partial_last": False,
        "series": series,
        "change_12m": change,
        "flags": flags,
    }


def _build_regions(char_rows, regions: pd.DataFrame) -> dict:
    top3 = [
        r["key"]
        for r in sorted(char_rows.values(), key=lambda r: (r["rank"] is None, r["rank"]))
        if r["rank"] is not None
    ][:3]
    if len(top3) < 3:
        raise ValueError("release: regions needs a top 3 by score")
    states_cfg = yaml.safe_load((REPO / "config/states.yaml").read_text())
    by_code = {v["code"]: (name, tuple(v["grid"])) for name, v in states_cfg.items()}
    totals: dict[str, int] = {}
    cells: dict[str, dict[str, int]] = {}
    for _, r in regions.iterrows():
        code, ckey = str(r["state_code"]), str(r["character_key"])
        if ckey == "_all":
            totals[code] = int(r["ads"])
        elif ckey in top3:
            cells.setdefault(code, {})[ckey] = int(r["ads"])
    ordered = sorted(by_code, key=lambda c: (by_code[c][1][1], by_code[c][1][0]))
    if len(ordered) != 16:
        raise ValueError(f"release: config/states.yaml must hold 16 states, got {len(ordered)}")
    states = []
    for code in ordered:
        name, grid = by_code[code]
        if code not in totals:
            raise ValueError(f"release: regions.parquet lacks _all row for {code}")
        by_character = {
            k: v for k, v in cells.get(code, {}).items() if v >= SUPPRESS_BELOW
        }
        states.append(
            {
                "code": code,
                "name": name,
                "grid": list(grid),
                "total": totals[code],
                "by_character": by_character,
            }
        )
    return {
        "source": "kleinanzeigen",
        "suppress_below": SUPPRESS_BELOW,
        "full_edition_only": True,
        "characters": top3,
        "states": states,
    }


#: Request window of the regional Trends batches (the trends lane archive run).
TRENDS_REGION_WINDOW = "2021-10-22 2026-10-22"
#: §12 (2026-10-23): a candidate's regional shares count as "flat" when
#: highest minus lowest state is at most this many whole-percent points.
FLAT_SPREAD = 2


def _build_regions_trends(trends_regions: pd.DataFrame) -> dict:
    """Google Trends DE by state (§8, §12 2026-10-23); context, never scored.

    naruto_index: the single-term "Naruto" request (strongest state = 100).
    shares: each candidate's plain-term share of the one multi-term request
    it appears in (whole percent). Google returns 0 when searches are too
    few, which is missing, not zero.
    """
    states_cfg = yaml.safe_load((REPO / "config/states.yaml").read_text())
    by_code = {v["code"]: (name, tuple(v["grid"])) for name, v in states_cfg.items()}
    ordered = sorted(by_code, key=lambda c: (by_code[c][1][1], by_code[c][1][0]))
    df = trends_regions
    idx = df[(df["metric"] == "relative_index_0_100") & (df["term"] == ANCHOR_TERM)]
    if idx["state_code"].duplicated().any() or set(idx["state_code"]) != set(ordered):
        raise ValueError("release: trends_regions needs one 'Naruto' index row per state")
    naruto_index = dict(zip(idx["state_code"], idx["value"].astype(int)))

    shares_df = df[df["metric"] == "share_of_compared_terms_pct"]
    term_of = {k: term for term, k in charlib.source_map("trends_term").items()}
    shares: dict[str, dict[str, int | None]] = {}
    readings: dict[str, str] = {}
    missing: list[str] = []
    for key in charlib.keys("candidate"):
        rows = shares_df[shares_df["term"] == term_of.get(key)]
        if rows.empty:
            missing.append(key)
            continue
        if rows["batch_id"].nunique() != 1 or set(rows["state_code"]) != set(ordered):
            raise ValueError(f"release: {key} must come from one regional request covering 16 states")
        vals = {c: (None if v == 0 else int(v)) for c, v in zip(rows["state_code"], rows["value"])}
        shares[key] = vals
        present = [v for v in vals.values() if v is not None]
        if "ambiguous_name" in charlib.flags(key):
            readings[key] = "ambiguous"
        else:
            readings[key] = "flat" if max(present) - min(present) <= FLAT_SPREAD else "hint"
    states = [
        {
            "code": code,
            "name": by_code[code][0],
            "naruto_index": naruto_index[code],
            "shares": {k: shares[k][code] for k in shares},
        }
        for code in ordered
    ]
    return {
        "source": "google_trends_de",
        "window": TRENDS_REGION_WINDOW,
        "flat_spread": FLAT_SPREAD,
        "states": states,
        "readings": readings,
        "missing": missing,
    }


def _build_merch(char_rows, merch: pd.DataFrame) -> dict:
    totals: dict[str, int] = {}
    cats: dict[str, dict[str, int]] = {}
    for _, r in merch.iterrows():
        key = str(r["character_key"])
        totals[key] = totals.get(key, 0) + int(r["items"])
        cats.setdefault(key, {})[str(r["category"])] = int(r["items"])
    unknown = {c for per in cats.values() for c in per} - set(MERCH_CATEGORIES)
    if unknown:
        raise ValueError(f"release: merch.parquet has unknown categories: {sorted(unknown)}")
    by_character = {
        key: {c: cats[key].get(c, 0) for c in MERCH_CATEGORIES}
        for key in char_rows
        if key not in charlib.keys("benchmark")
        and totals.get(key, 0) >= MERCH_MIN_ITEMS
    }
    return {
        "source": "ebay",
        "categories": list(MERCH_CATEGORIES),
        "min_items": MERCH_MIN_ITEMS,
        "by_character": by_character,
    }


def _censored_trends_keys(momentum: pd.DataFrame | None) -> list[str]:
    """Character keys the trends lane flagged "censored" in its momentum output.

    Reuses the trends lane's own censoring outcome (the same censoring table
    the archive reproduces): a censored series feeds no scored cell, so
    its weekly rows are not "used" (plan §8) and must not count toward the
    google_trends records. No "flag" column or no censored flags (synthetic
    inputs, older aux) → no keys → totals pass through untouched.
    """
    if momentum is None or getattr(momentum, "empty", True):
        return []
    if "flag" not in momentum.columns or "character_key" not in momentum.columns:
        return []
    flagged = momentum[momentum["flag"].astype(str) == "censored"]
    return sorted({str(k) for k in flagged["character_key"].unique()})


def _exclude_censored_trends_rows(
    sources: list[dict], momentum: pd.DataFrame | None
) -> list[dict]:
    """Count only rows of Trends series that feed the score (plan §8/N5).

    the trends lane reports every requested weekly row (len(SERIES) series on one shared
    bucket grid — the trends lane asserts the grids match, so rows divide evenly);
    censored series contribute no scored row, so their share is subtracted
    from the in-score google_trends entry. kpis.records_counted is derived
    from these sources downstream, so it follows automatically.
    """
    out = [dict(s) for s in sources]
    target = next(
        (s for s in out if s.get("id") == "google_trends" and s.get("in_score")),
        None,
    )
    if target is None:
        return out
    censored = _censored_trends_keys(momentum)
    if not censored:
        return out
    n_series = len(TRENDS_SERIES)
    records = int(target.get("records", 0) or 0)
    per_series, remainder = divmod(records, n_series)
    if remainder:
        raise ValueError(
            "release: google_trends records "
            f"{records} do not divide evenly over {n_series} requested series"
        )
    target["records"] = records - len(censored) * per_series
    return out


def _merge_sources(sources: list[dict]) -> list[dict]:
    """Normalise lane sub-source ids (``base:sub``) to contract ids.

    the trends lane reports ``google_trends:timeseries`` (in score) and
    ``google_trends:geo`` (context) separately; the contract allows a single
    ``google_trends`` entry. Merge parts sharing a base id: in_score is OR,
    and records sums only the parts matching the merged flag, so context
    rows never inflate a scored entry (nor vice versa). Unknown base ids
    raise instead of guessing.
    """
    merged: dict[str, dict] = {}
    for s in sources:
        base = str(s.get("id", "")).split(":")[0]
        if base not in SOURCE_IDS:
            raise ValueError(f"release: unknown source id: {s.get('id')!r}")
        slot = merged.setdefault(base, {"in_score": False, "parts": []})
        slot["in_score"] = bool(slot["in_score"] or s.get("in_score"))
        slot["parts"].append(s)
    out = []
    for base, slot in merged.items():
        flag = slot["in_score"]
        records = sum(
            int(p.get("records", 0) or 0)
            for p in slot["parts"]
            if bool(p.get("in_score")) == flag
        )
        out.append({"id": base, "records": records, "in_score": flag})
    return out


SOURCE_IDS = frozenset(
    [
        "amazon",
        "ebay",
        "kleinanzeigen",
        "youtube",
        "google_trends",
        "anime2you",
        "narutop99",
        "wikimedia",
    ]
)


def _build_kpis(char_rows, kpis: dict, sources: list[dict]) -> dict:
    required = [
        "shop_listings_checked",
        "youtube_comments_de",
        "youtube_comments_total",
        "anime2you_articles",
    ]
    missing = [k for k in required if k not in kpis]
    if missing:
        raise ValueError(f"release: kpis_*.json lack required keys: {missing}")
    out = dict(kpis)
    if "records_counted" not in out:
        # No lane owns this contract aggregate (plan §8: sum of all in-score
        # source records), so derive it from the merged sources list.
        out["records_counted"] = sum(
            int(s.get("records", 0) or 0) for s in sources if s.get("in_score")
        )
    out["characters_ranked"] = sum(1 for r in char_rows.values() if r["rank"] is not None)
    out["sources_in_score"] = sum(1 for s in sources if s.get("in_score"))
    return out


def check_privacy(doc: dict) -> None:
    """Aggregates only (plan §11): no long strings, no non-event URLs."""
    problems: list[str] = []
    events_urls = {e.get("source_url") for e in doc.get("events", []) if isinstance(e, dict)}

    def walk(node, path: str, in_event_url: bool = False):
        if isinstance(node, dict):
            for k, v in node.items():
                exempt = k == "source_url" and re.search(r"events\[\d+\]$", path) is not None
                walk(v, f"{path}.{k}", in_event_url=exempt)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]", in_event_url=False)
        elif isinstance(node, str):
            if in_event_url:
                return
            if len(node) > 120:
                problems.append(f"{path}: string of {len(node)} chars (>120)")
            if URL_RE.search(node):
                problems.append(f"{path}: URL outside events[].source_url")

    walk(doc, "$")
    for url in events_urls:
        if not isinstance(url, str) or not URL_RE.search(url):
            problems.append(f"$.events: bad source_url {url!r}")
    if problems:
        raise ValueError("release: privacy guard failed:\n- " + "\n- ".join(problems))


def validate(doc: dict) -> None:
    schema_validate(doc, SCHEMA)


def dump_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def write_release(doc: dict, release_dir: str | Path | None = None,
                  name: str = "dashboard") -> Path:
    """Write ``<name>.json`` + ``<name>.sha256`` (full: dashboard, public: dashboard.public)."""
    check_privacy(doc)
    validate(doc)
    out = Path(release_dir) if release_dir is not None else release_path()
    out.mkdir(parents=True, exist_ok=True)
    payload = dump_bytes(doc)
    (out / f"{name}.json").write_bytes(payload)

    (out / f"{name}.sha256").write_text(hashlib.sha256(payload).hexdigest() + "\n")
    return out / f"{name}.json"


def build(
    result,
    aux_dir,
    *,
    generated_utc: str | None = None,
    snapshot_date: str | None = None,
    archive_commit: str | None = None,
    input_sha256: str | None = None,
) -> dict:
    """Assemble, privacy-check and schema-validate the dashboard document."""
    aux_path = Path(aux_dir)
    if not aux_path.is_dir():
        raise FileNotFoundError(f"release aux missing: directory {aux_path}")
    aux = _load_aux(aux_path)
    precision_path = aux_path / "precision.parquet"
    if precision_path.exists():
        aux["precision"] = pd.read_parquet(precision_path)

    char_rows = _characters_table(result)
    for bkey in charlib.keys("benchmark"):
        char_rows.setdefault(
            bkey,
            {
                "key": bkey,
                "rank": None,
                "index": None,
                "lens_ranks": None,
                "top3_sources": None,
                "confidence": None,
                "flags": [],
                "counts": {},
            },
        )
    metrics_counts = _metrics_counts(result)
    result_counts = _result_get(result, "counts") or {}
    prec, prec_flags = _precision_maps(result, aux)
    weights = _result_get(result, "weights") or {"shoppers": 0.5, "watching": 0.3, "votes": 0.2}
    robustness = dict(_result_get(result, "robustness") or {})
    if not robustness:
        raise ValueError("release: score result holds no robustness block")
    robustness["kendall_w"] = _r3(robustness.get("kendall_w"))

    characters = _build_characters(char_rows, metrics_counts, result_counts, prec, prec_flags, aux["prices"])
    if len(characters) != 14:
        raise ValueError(f"release: need 14 characters, got {len(characters)}")

    snapshot = snapshot_date or provenance.snapshot_date()
    commit = archive_commit or provenance.archive_commit()
    digest = input_sha256 or provenance.input_sha256(aux_path)
    if generated_utc is None:
        # Deterministic default (snapshot midnight UTC): the release must be
        # byte-reproducible across reruns, so no wall-clock timestamp is
        # embedded unless the caller passes one explicitly.
        generated_utc = f"{snapshot}T00:00:00Z"
    doc = {
        "meta": provenance.make_meta(
            generated_utc=generated_utc,
            snapshot=snapshot,
            commit=commit,
            digest=digest,
        ),
        "weights": dict(weights),
        "kpis": _build_kpis(char_rows, aux["kpis"], aux["sources"]),
        "characters": characters,
        "robustness": dict(robustness),
        "momentum": _build_momentum(char_rows, aux["momentum"], metrics_counts, result_counts),
        "regions_trends": _build_regions_trends(aux["trends_regions"]),
        "regions": _build_regions(char_rows, aux["regions"]),
        "merch": _build_merch(char_rows, aux["merch"]),
        "events": aux["events"],
        "sources": sorted(aux["sources"], key=lambda s: s.get("id", "")),
        "benchmark_comparison": _load_benchmark(aux_path),
    }
    # §12 amendment 2026-10-23 §7.7(b): the secondary all-7-sources Kendall's
    # W rides in meta.notes (contract unchanged). Added before the
    # release_id hash so the id covers it. Synthetic dict results without a
    # detail block simply get no note.
    detail = _result_get(result, "detail") or {}
    if "kendall_w_all7" in detail and "n_complete_all7" in detail:
        doc["meta"]["notes"] = list(doc["meta"]["notes"]) + [
            f"Kendall W (all 7 sources, n={int(detail['n_complete_all7'])} "
            f"complete cases) = {_r3(detail['kendall_w_all7']):.3f}"
        ]
    doc["meta"]["edition"] = "full"
    # Content-derived release_id: hash the document with release_id blank so
    # the id describes the content instead of the inputs.
    # Same content → same id; any value change → a different id.
    content_hash = hashlib.sha256(dump_bytes(doc)).hexdigest()
    doc["meta"]["release_id"] = provenance.release_id_for(
        doc["meta"]["contract_version"], snapshot, content_hash)
    check_privacy(doc)
    validate(doc)
    return doc
