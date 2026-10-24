"""the pipeline tests on synthetic inputs shaped like contract/preview.fixture.json."""
import json

import pytest
from jsonschema import validate as schema_validate

from nga.paths import REPO
from nga.release import build, check_privacy, dump_bytes, write_release
from nga.release.build import SCHEMA

from .synth import TOP3, add_kleinanzeigen, make_aux, make_result

FIXED = dict(generated_utc="2026-10-23T00:00:00Z", snapshot_date="2026-10-22",
             archive_commit="a" * 40, input_sha256="b" * 64)


@pytest.fixture()
def aux_dir(tmp_path):
    d = tmp_path / "aux"
    make_aux(d, REPO / "config/states.yaml")
    return d


@pytest.fixture()
def public_aux_dir(aux_dir):
    """aux_dir plus a Kleinanzeigen source and the §12 2026-10-23 benchmark rules."""
    add_kleinanzeigen(aux_dir)
    return aux_dir


def test_valid_output_validates(aux_dir):
    doc = build(make_result(), aux_dir, **FIXED)
    schema_validate(doc, SCHEMA)

    assert doc["meta"]["status"] == "validated"
    # Content-derived id: v<contract>-<YYYYMMDD>-<first 8 of content sha256>.
    assert doc["meta"]["release_id"].startswith("v1.2.0-20261022-")
    assert len(doc["meta"]["release_id"]) == len("v1.2.0-20261022-") + 8
    assert doc["meta"]["archive_commit"] == "a" * 40
    assert doc["meta"]["input_sha256"] == "b" * 64
    assert doc["meta"]["contract_version"] == "1.2.0"
    notes = "\n".join(doc["meta"]["notes"])
    assert "generated_utc is pinned" in notes
    assert "change_12m is rounded to 1 dp" in notes

    assert len(doc["characters"]) == 14
    bench = next(c for c in doc["characters"] if c["key"] == "naruto_uzumaki")
    assert bench["role"] == "benchmark"
    assert bench["rank"] is None and bench["index"] is None
    assert bench["lens_ranks"] is None and bench["confidence"] is None
    assert bench["top3_sources"] is None
    assert "franchise_name" in bench["flags"]
    cands = [c for c in doc["characters"] if c["role"] == "candidate"]
    assert len(cands) == 13
    assert sorted(c["rank"] for c in cands) == list(range(1, 14))
    first = next(c for c in cands if c["rank"] == 1)
    assert first["key"] == "sasuke_uchiha"
    for c in doc["characters"]:
        assert set(c["counts"]) >= {"amazon_products", "ebay_items", "kleinanzeigen_ads",
                                    "youtube_videos_de", "youtube_comments_de",
                                    "anime2you_articles", "fan_votes_eu", "google_interest"}
        assert set(c["prices_eur"]) == {"amazon", "ebay", "kleinanzeigen"}
    obito = next(c for c in doc["characters"] if c["key"] == "obito_uchiha")
    assert obito["prices_eur"]["amazon"] is None  # n < 10 → null
    assert obito["counts"]["amazon_products"] == 18  # missing is not zero
    hinata = next(c for c in doc["characters"] if c["key"] == "hinata_hyuga")
    assert "ambiguous_name" in hinata["flags"] and "low_precision" in hinata["flags"]
    assert hinata["accuracy"]["ebay"] == 0.8
    assert doc["characters"][0]["accuracy"]["amazon"] == 0.95

    assert doc["robustness"]["leave_one_out"]["runs"] == 7
    assert doc["weights"] == {"shoppers": 0.5, "watching": 0.3, "votes": 0.2}
    assert doc["kpis"]["characters_ranked"] == 13
    assert doc["kpis"]["sources_in_score"] == 2
    assert {s["id"] for s in doc["sources"]} == {"amazon", "ebay", "google_trends"}

    mom = doc["momentum"]
    assert set(mom["series"]) == {"sasuke_uchiha", "itachi_uchiha", "kakashi_hatake",
                                  "minato_namikaze", "madara_uchiha", "hinata_hyuga"}
    assert all(isinstance(p, str) for p in mom["periods"]) and len(mom["periods"]) == 12
    assert mom["partial_last"] is False
    assert all(len(v) == 12 for v in mom["series"].values())
    # §4: every shown series carries exactly one flag.
    assert set(mom["flags"]) == set(mom["series"])
    assert mom["flags"]["hinata_hyuga"] == "ambiguous_name"  # precedence over topic_series
    assert mom["flags"]["madara_uchiha"] == "term_series"
    assert mom["flags"]["minato_namikaze"] == "topic_series"  # synth kind; real the trends lane uses a term fallback
    for key in ("sasuke_uchiha", "itachi_uchiha", "kakashi_hatake"):
        assert mom["flags"][key] == "topic_series"
    # Unit comes from the trends lane's outputs, not a hard-coded string.
    assert mom["unit"] == ("Google search index on one shared scale "
                             "(reference: search term 'Naruto' = 28.4)")
    assert "franchise" not in mom["unit"]

    reg = doc["regions"]
    assert reg["characters"] == TOP3 and len(reg["states"]) == 16
    assert reg["suppress_below"] == 10 and reg["full_edition_only"] is True
    sl = next(s for s in reg["states"] if s["code"] == "SL")
    assert "kakashi_hatake" not in sl["by_character"]  # suppressed cell (4 < 10)

    assert set(doc["merch"]["by_character"]) == {
        "sasuke_uchiha", "itachi_uchiha", "kakashi_hatake",
        "minato_namikaze", "madara_uchiha", "hinata_hyuga"}
    assert len(doc["events"]) == 1

    bench_cmp = doc["benchmark_comparison"]
    assert bench_cmp["benchmark"] == "naruto_uzumaki"
    assert {s["id"] for s in bench_cmp["sources"]} == {
        "amazon", "ebay", "kleinanzeigen", "youtube_comments", "youtube_videos",
        "google_trends", "anime2you_comments", "anime2you_articles", "narutop99"}
    assert "naruto_uzumaki" not in bench_cmp["by_character"]
    sasuke_ratio = bench_cmp["by_character"]["sasuke_uchiha"]["ratios"]
    assert sasuke_ratio == {"kleinanzeigen": 1.24, "narutop99": 1.4}  # rounded to 2 dp at build
    assert bench_cmp["sources"][0]["benchmark_value"] == 999.46  # 999.456 → 2 dp


def test_missing_benchmark_json_is_a_clear_error(aux_dir):
    (aux_dir / "benchmark.json").unlink()
    with pytest.raises(FileNotFoundError, match="benchmark"):
        build(make_result(), aux_dir, **FIXED)


def test_benchmark_malformed_is_rejected(aux_dir):
    import json as _json
    (aux_dir / "benchmark.json").write_text(_json.dumps({"benchmark": "sasuke_uchiha"}))
    with pytest.raises(ValueError, match="benchmark_comparison"):
        build(make_result(), aux_dir, **FIXED)


def test_missing_aux_file_names_it(aux_dir, tmp_path):
    (aux_dir / "prices.parquet").unlink()
    with pytest.raises(FileNotFoundError, match="prices.parquet"):
        build(make_result(), aux_dir, **FIXED)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="empty"):
        build(make_result(), empty, **FIXED)


def test_privacy_catches_url_and_long_snippet(aux_dir):
    doc = build(make_result(), aux_dir, **FIXED)
    doc["meta"]["notes"] = ["see https://evil.example/listing/123 for details"]
    with pytest.raises(ValueError, match="URL"):
        check_privacy(doc)
    doc = build(make_result(), aux_dir, **FIXED)
    doc["events"][0]["note_en"] = "x" * 121
    with pytest.raises(ValueError, match=">120"):
        check_privacy(doc)
    with pytest.raises(ValueError):
        write_release(doc, aux_dir / "out")


def test_same_inputs_identical_bytes(aux_dir, tmp_path):
    doc1 = build(make_result(), aux_dir, **FIXED)
    doc2 = build(make_result(), aux_dir, **FIXED)
    assert dump_bytes(doc1) == dump_bytes(doc2)
    write_release(doc1, tmp_path / "r1")
    write_release(doc2, tmp_path / "r2")
    assert (tmp_path / "r1/dashboard.json").read_bytes() == (tmp_path / "r2/dashboard.json").read_bytes()
    assert (tmp_path / "r1/dashboard.sha256").read_text() == (tmp_path / "r2/dashboard.sha256").read_text()
    import hashlib
    payload = (tmp_path / "r1/dashboard.json").read_bytes()
    assert (tmp_path / "r1/dashboard.sha256").read_text().strip() == hashlib.sha256(payload).hexdigest()
    assert b"\xc3\xa4" not in payload  # synthetic ASCII-only, but encoding must be UTF-8
    assert json.loads(payload) == doc1  # round-trips; sorted keys + 1-space indent
    assert payload.startswith(b'{\n "benchmark_comparison":')


def test_cli_writes_release_files(public_aux_dir, tmp_path, monkeypatch):
    from nga.release import provenance
    from nga.release.__main__ import main

    # No private archive in the demo: pin provenance to constants.
    monkeypatch.setattr(provenance, "archive_commit", lambda: "a" * 40)
    monkeypatch.setattr(provenance, "input_sha256", lambda *a, **k: "b" * 64)
    result_file = tmp_path / "result.json"
    result_file.write_text(json.dumps(make_result()))
    out = main(["--result", str(result_file), "--aux-dir", str(public_aux_dir),
                "--release-dir", str(tmp_path / "release")])
    assert out.name == "dashboard.json" and out.exists()
    assert (tmp_path / "release/dashboard.sha256").exists()
    schema_validate(json.loads(out.read_text()), SCHEMA)
    public = json.loads((tmp_path / "release/dashboard.public.json").read_text())
    assert (tmp_path / "release/dashboard.public.sha256").exists()
    assert public["meta"]["edition"] == "public"
    schema_validate(public, SCHEMA)


def test_metrics_key_only_feeds_counts(aux_dir):
    # the pipeline regression: the real CLI passes the long metrics table under the
    # "metrics" key with no "metrics_df". A stale loop variable meant the
    # concat read None instead of the table and crashed the real pipeline,
    # while synthetic tests (no metrics keys at all) stayed green.
    import pandas as pd

    from nga.release import build as build_fn

    result = make_result()
    result.pop("counts", None)
    result.pop("metrics_df", None)
    result["metrics"] = pd.DataFrame([
        {"character_key": "sasuke_uchiha", "source": "amazon",
         "metric": "asins", "period": "snapshot", "value": 129.0},
        {"character_key": "sasuke_uchiha", "source": "ebay",
         "metric": "items", "period": "snapshot", "value": 623.0},
        {"character_key": "itachi_uchiha", "source": "amazon",
         "metric": "asins", "period": "snapshot", "value": 95.0},
    ])
    doc = build_fn(result, aux_dir, **FIXED)
    by_key = {c["key"]: c for c in doc["characters"]}
    assert by_key["sasuke_uchiha"]["counts"]["amazon_products"] == 129
    assert by_key["sasuke_uchiha"]["counts"]["ebay_items"] == 623
    assert by_key["itachi_uchiha"]["counts"]["amazon_products"] == 95


def test_records_counted_derived_from_sources_when_missing(aux_dir):
    # the pipeline regression: no lane writes records_counted to kpis_*.json, so the
    # builder must derive it (plan §8: sum of all in-score source records).
    # An explicitly provided value still passes through untouched.
    import json

    from nga.release import build as build_fn

    kpis_shops = aux_dir / "kpis_shops.json"
    part = json.loads(kpis_shops.read_text())
    assert part.pop("records_counted") == 9000
    kpis_shops.write_text(json.dumps(part))
    doc = build_fn(make_result(), aux_dir, **FIXED)
    assert doc["kpis"]["records_counted"] == 3000  # 1000 + 2000 in score


def test_sub_source_ids_merge_to_contract_id(aux_dir):
    # the pipeline regression: the trends lane reports google_trends:timeseries (in score) and
    # google_trends:geo (context); the contract allows one google_trends id.
    import json

    from nga.release import build as build_fn

    (aux_dir / "sources_extra.json").write_text(json.dumps([
        {"id": "google_trends:timeseries", "records": 3132, "in_score": True},
        {"id": "google_trends:geo", "records": 528, "in_score": False},
    ]))
    doc = build_fn(make_result(), aux_dir, **FIXED)
    gt = [s for s in doc["sources"] if s["id"] == "google_trends"]
    assert len(gt) == 1
    assert gt[0] == {"id": "google_trends", "records": 3132, "in_score": True}
    assert doc["kpis"]["records_counted"] == 9000  # explicit value kept


def test_precision_flags_follow_applied_treatment(aux_dir):
    # the pipeline regression: _all fallback rows must flag only characters without an
    # exact cell (mirrors scoring lookup), exact "use" clears the flag, and
    # the benchmark (never scored) carries no treatment flags.
    import pandas as pd

    from nga.release import build as build_fn

    result = make_result()
    for ch in result["characters"]:
        ch["flags"] = []
    result["precision"] = pd.DataFrame([
        {"source": "amazon", "character_key": "_all", "n": 40,
         "correct": 32, "precision": 0.8, "treatment": "adjust"},
        {"source": "amazon", "character_key": "sasuke_uchiha", "n": 10,
         "correct": 10, "precision": 1.0, "treatment": "use"},
        {"source": "ebay", "character_key": "naruto_uzumaki", "n": 29,
         "correct": 19, "precision": 0.66, "treatment": "exclude"},
    ])
    doc = build_fn(result, aux_dir, **FIXED)
    by_key = {c["key"]: c for c in doc["characters"]}
    assert "low_precision" not in by_key["sasuke_uchiha"]["flags"]
    assert "low_precision" in by_key["gaara"]["flags"]
    assert "excluded_source" not in by_key["naruto_uzumaki"]["flags"]
    assert "low_precision" not in by_key["naruto_uzumaki"]["flags"]
    assert by_key["sasuke_uchiha"]["accuracy"]["amazon"] == 1.0
    assert by_key["gaara"]["accuracy"]["amazon"] == 0.8


def test_merch_excludes_benchmark(aux_dir):
    # the pipeline regression: plan §8 merch covers candidates with ≥100 items; the
    # benchmark is never ranked and must not appear even with ≥100 items.
    import pandas as pd

    from nga.release import build as build_fn

    merch = pd.read_parquet(aux_dir / "merch.parquet")
    extra = pd.DataFrame([
        {"character_key": "naruto_uzumaki", "category": c, "items": 50}
        for c in ["figures", "clothing", "cards", "manga_media",
                  "accessories", "other"]
    ])
    pd.concat([merch, extra], ignore_index=True).to_parquet(
        aux_dir / "merch.parquet", index=False)
    doc = build_fn(make_result(), aux_dir, **FIXED)
    assert "naruto_uzumaki" not in doc["merch"]["by_character"]


def test_momentum_unit_derived_from_inputs(aux_dir):
    # The unit names the actual reference (Naruto's matched term series and
    # its interest_52w value from the inputs), never "franchise term".
    import pandas as pd

    from nga.release import build as build_fn

    result = make_result()
    result["counts"]["naruto_uzumaki"]["google_interest"] = 37.73
    doc = build_fn(result, aux_dir, **FIXED)
    assert doc["momentum"]["unit"] == (
        "Google search index on one shared scale "
        "(reference: search term 'Naruto' = 37.73)")
    assert "franchise" not in doc["momentum"]["unit"]
    assert "term" in doc["momentum"]["unit"] and "Naruto" in doc["momentum"]["unit"]


def test_momentum_unit_fallback_without_reference(aux_dir):
    # No Naruto value anywhere → generic scale label, still valid.
    import pandas as pd

    from nga.release import build as build_fn

    result = make_result()
    result.pop("counts", None)
    result["metrics"] = pd.DataFrame([
        {"character_key": "sasuke_uchiha", "source": "amazon",
         "metric": "asins", "period": "snapshot", "value": 129.0},
    ])
    doc = build_fn(result, aux_dir, **FIXED)
    assert doc["momentum"]["unit"] == "index (rescaled German search interest)"


def test_default_generated_utc_is_deterministic(aux_dir):
    # the pipeline regression: byte-for-byte rerun determinism requires no wall-clock
    # in the default release; repeated builds must produce identical bytes.
    from nga.release import build as build_fn
    from nga.release.build import dump_bytes

    result = make_result()
    doc1 = build_fn(result, aux_dir, snapshot_date="2026-10-22",
                    archive_commit="a" * 40, input_sha256="b" * 64)
    doc2 = build_fn(result, aux_dir, snapshot_date="2026-10-22",
                    archive_commit="a" * 40, input_sha256="b" * 64)
    assert dump_bytes(doc1) == dump_bytes(doc2)
    assert doc1["meta"]["generated_utc"] == "2026-10-22T00:00:00Z"


def _decimals(x) -> int:
    from decimal import Decimal
    d = Decimal(str(x)).normalize() if "." in str(x) else Decimal(str(x))
    return max(0, -d.as_tuple().exponent)


def test_rounding_applies_at_build_time(aux_dir):
    # Every field in the §4 rounding table is rounded in build(); exact values.
    import pandas as pd

    from nga.release import build as build_fn

    result = make_result()
    for ch in result["characters"]:
        if ch["character_key"] == "sasuke_uchiha":
            ch["lens_ranks"] = {"shoppers": 8 / 3, "watching": 2.6666666666666665,
                                "votes": 5.555}
            ch["index"] = 92.6
    result["counts"]["sasuke_uchiha"]["google_interest"] = 4.0576923076923075
    result["precision"] = [
        {"source": "amazon", "character_key": "_all", "n": 40,
         "correct": 38, "precision": 0.9545454545454546, "treatment": "use"},
    ]
    result["robustness"]["kendall_w"] = 0.7077281197
    prices = pd.read_parquet(aux_dir / "prices.parquet")
    mask = ((prices["character_key"] == "sasuke_uchiha")
            & (prices["platform"] == "amazon"))
    prices.loc[mask, "median_eur"] = 19.999
    prices.to_parquet(aux_dir / "prices.parquet", index=False)
    doc = build_fn(result, aux_dir, **FIXED)
    by_key = {c["key"]: c for c in doc["characters"]}
    sasuke = by_key["sasuke_uchiha"]
    assert sasuke["lens_ranks"] == {"shoppers": 2.67, "watching": 2.67, "votes": 5.55}
    assert sasuke["index"] == 93 and isinstance(sasuke["index"], int)
    assert sasuke["counts"]["google_interest"] == 4.06
    assert sasuke["prices_eur"]["amazon"] == 20.0
    assert sasuke["accuracy"]["amazon"] == 0.955
    assert doc["robustness"]["kendall_w"] == 0.708


def test_no_float_exceeds_allowed_decimals(aux_dir):
    # Walk the whole release: each float must fit its field's allowance.
    from nga.release import build as build_fn

    doc = build_fn(make_result(), aux_dir, **FIXED)
    problems: list[str] = []
    for c in doc["characters"]:
        key = c["key"]
        for lens, v in (c["lens_ranks"] or {}).items():
            if v is not None and _decimals(v) > 2:
                problems.append(f"{key}.lens_ranks.{lens}={v}")
        if c["index"] is not None and not isinstance(c["index"], int):
            problems.append(f"{key}.index={c['index']!r} not int")
        for field, v in c["counts"].items():
            if v is None:
                continue
            if field == "google_interest":
                if _decimals(v) > 2:
                    problems.append(f"{key}.counts.{field}={v}")
            elif not isinstance(v, int):
                problems.append(f"{key}.counts.{field}={v!r} not int")
        for plat, v in c["prices_eur"].items():
            if v is not None and _decimals(v) > 2:
                problems.append(f"{key}.prices_eur.{plat}={v}")
        for src, v in (c.get("accuracy") or {}).items():
            if v is not None and _decimals(v) > 3:
                problems.append(f"{key}.accuracy.{src}={v}")
    if _decimals(doc["robustness"]["kendall_w"]) > 3:
        problems.append(f"robustness.kendall_w={doc['robustness']['kendall_w']}")
    for key, vals in doc["momentum"]["series"].items():
        for v in vals:
            if v is not None and _decimals(v) > 2:
                problems.append(f"momentum.series.{key}={v}")
    for key, v in doc["momentum"]["change_12m"].items():
        if _decimals(v) > 1:
            problems.append(f"momentum.change_12m.{key}={v}")
    for src in doc["benchmark_comparison"]["sources"]:
        if src["benchmark_value"] is not None and _decimals(src["benchmark_value"]) > 2:
            problems.append(f"benchmark.sources.{src['id']}={src['benchmark_value']}")
    for key, entry in doc["benchmark_comparison"]["by_character"].items():
        for src_id, v in entry["ratios"].items():
            if v is not None and _decimals(v) > 2:
                problems.append(f"benchmark.ratios.{key}.{src_id}={v}")
        for f in ("comparable_sources", "ahead_in"):
            if not isinstance(entry[f], int):
                problems.append(f"benchmark.{key}.{f}={entry[f]!r} not int")
    assert problems == []


def test_momentum_flag_precedence_with_censored(aux_dir):
    # Flag precedence: ambiguous_name > censored > term_series > topic_series.
    import pandas as pd

    from nga.release import build as build_fn

    mom = pd.read_parquet(aux_dir / "momentum.parquet")
    for key in ("madara_uchiha", "sasuke_uchiha", "hinata_hyuga"):
        mom.loc[mom["character_key"] == key, "flag"] = "censored"
    mom.to_parquet(aux_dir / "momentum.parquet", index=False)
    doc = build_fn(make_result(), aux_dir, **FIXED)
    assert doc["momentum"]["flags"]["madara_uchiha"] == "censored"
    assert doc["momentum"]["flags"]["sasuke_uchiha"] == "censored"
    # Hinata's ambiguous_name takes precedence even when censored too.
    assert doc["momentum"]["flags"]["hinata_hyuga"] == "ambiguous_name"
    assert doc["momentum"]["flags"]["minato_namikaze"] == "topic_series"


def test_release_id_deterministic_and_sensitive(aux_dir):
    from nga.release import build as build_fn

    doc1 = build_fn(make_result(), aux_dir, **FIXED)
    doc2 = build_fn(make_result(), aux_dir, **FIXED)
    assert doc1["meta"]["release_id"] == doc2["meta"]["release_id"]
    changed = make_result()
    changed["characters"][0]["index"] = 94.0
    doc3 = build_fn(changed, aux_dir, **FIXED)
    assert doc3["meta"]["release_id"] != doc1["meta"]["release_id"]


def test_all7_kendall_note_appended_when_detail_present(aux_dir):
    # §12 amendment 2026-10-23 §7.7(b): secondary all-7 W rides in meta.notes.
    from nga.release import build as build_fn

    result = make_result()
    result["detail"] = {"kendall_w_all7": 0.85, "n_complete_all7": 2}
    doc = build_fn(result, aux_dir, **FIXED)
    assert doc["meta"]["notes"][-1] == (
        "Kendall W (all 7 sources, n=2 complete cases) = 0.850"
    )


def test_no_all7_kendall_note_without_detail(aux_dir):
    from nga.release import build as build_fn

    doc = build_fn(make_result(), aux_dir, **FIXED)
    assert not [n for n in doc["meta"]["notes"] if "Kendall W (all 7" in n]


def test_google_trends_records_exclude_censored_series(aux_dir):
    # N5: google_trends records count only rows of series that feed the
    # score. the trends lane requests len(SERIES) series on one shared grid, so the
    # in-score rows divide evenly; censored series (flagged in the trends lane's own
    # momentum output) contribute no scored row and are subtracted.
    import json as _json
    import pandas as pd

    from nga.release import build as build_fn

    (aux_dir / "sources_extra.json").write_text(_json.dumps([
        {"id": "google_trends:timeseries", "records": 120, "in_score": True},
        {"id": "google_trends:geo", "records": 528, "in_score": False},
    ]))
    kpis = _json.loads((aux_dir / "kpis_shops.json").read_text())
    kpis.pop("records_counted", None)  # derive, as in the real pipeline
    (aux_dir / "kpis_shops.json").write_text(_json.dumps(kpis))
    mom = pd.read_parquet(aux_dir / "momentum.parquet")
    mom.loc[mom["character_key"].isin(["gaara", "madara_uchiha"]), "flag"] = "censored"
    mom.to_parquet(aux_dir / "momentum.parquet", index=False)
    doc = build_fn(make_result(), aux_dir, **FIXED)
    gt = next(s for s in doc["sources"] if s["id"] == "google_trends")
    # 12 requested series share 120 rows evenly (10 each); 2 censored → 100.
    assert gt == {"id": "google_trends", "records": 100, "in_score": True}
    # records_counted follows the corrected sources, uncensored totals kept.
    assert doc["kpis"]["records_counted"] == 1000 + 2000 + 100
    assert [s["records"] for s in doc["sources"]
            if s["id"] in ("amazon", "ebay")] == [1000, 2000]


def test_google_trends_records_unchanged_without_censored_flags(aux_dir):
    # No censored flags (older aux) → totals pass through untouched.
    import json as _json

    from nga.release import build as build_fn

    (aux_dir / "sources_extra.json").write_text(_json.dumps([
        {"id": "google_trends:timeseries", "records": 120, "in_score": True},
        {"id": "google_trends:geo", "records": 528, "in_score": False},
    ]))
    kpis = _json.loads((aux_dir / "kpis_shops.json").read_text())
    kpis.pop("records_counted", None)
    (aux_dir / "kpis_shops.json").write_text(_json.dumps(kpis))
    doc = build_fn(make_result(), aux_dir, **FIXED)
    gt = next(s for s in doc["sources"] if s["id"] == "google_trends")
    assert gt == {"id": "google_trends", "records": 120, "in_score": True}
    assert doc["kpis"]["records_counted"] == 1000 + 2000 + 120


def test_google_trends_records_uneven_series_rows_raise(aux_dir):
    # Rows must divide evenly over the requested SERIES table; otherwise the
    # per-series subtraction is undefined — fail loudly instead of guessing.
    import json as _json
    import pandas as pd

    from nga.release import build as build_fn

    (aux_dir / "sources_extra.json").write_text(_json.dumps([
        {"id": "google_trends:timeseries", "records": 125, "in_score": True},
    ]))
    mom = pd.read_parquet(aux_dir / "momentum.parquet")
    mom.loc[mom["character_key"] == "gaara", "flag"] = "censored"
    mom.to_parquet(aux_dir / "momentum.parquet", index=False)
    with pytest.raises(ValueError, match="do not divide evenly"):
        build_fn(make_result(), aux_dir, **FIXED)


def test_meta_notes_state_records_rule_and_null_meaning(aux_dir):
    # N5/N6: the release says what records counts cover and what null means.
    from nga.release import build as build_fn

    doc = build_fn(make_result(), aux_dir, **FIXED)
    notes = doc["meta"]["notes"]
    assert ("records counts only rows of series that feed the score "
            "(censored Trends series excluded).") in notes
    assert ("counts.google_interest is null where the series is censored "
            "in the request view used (missing, never zero).") in notes
    assert all(len(n) <= 120 for n in notes)  # privacy guard: ≤120 chars


# --- contract 1.2.0: regions_trends and the public edition ------------------


def test_regions_trends_block(aux_dir):
    rt = build(make_result(), aux_dir, **FIXED)["regions_trends"]
    assert rt["source"] == "google_trends_de" and rt["flat_spread"] == 2
    assert len(rt["states"]) == 16
    assert rt["states"][0]["naruto_index"] == 100
    assert rt["missing"] == ["nagato_pain"]
    assert rt["readings"]["sasuke_uchiha"] == "flat"
    assert rt["readings"]["itachi_uchiha"] == "hint"
    assert rt["readings"]["hinata_hyuga"] == "ambiguous"
    by = next(s for s in rt["states"] if s["code"] == "BY")
    assert by["shares"]["gaara"] is None  # Google's 0 is missing, not zero
    assert "nagato_pain" not in by["shares"]


def test_full_edition_is_marked(aux_dir):
    doc = build(make_result(), aux_dir, **FIXED)
    assert doc["meta"]["edition"] == "full"
    assert "regions" in doc


def test_public_edition_drops_kleinanzeigen_and_regions(public_aux_dir):
    aux_dir = public_aux_dir
    from nga.release.public import public_edition

    doc = build(make_result(), aux_dir, **FIXED)
    pub = public_edition(doc)
    schema_validate(pub, SCHEMA)
    check_privacy(pub)
    assert pub["meta"]["edition"] == "public"
    assert pub["meta"]["release_id"] != doc["meta"]["release_id"]
    assert "regions" not in pub
    for c in pub["characters"]:
        assert c["counts"]["kleinanzeigen_ads"] is None
        assert c["prices_eur"]["kleinanzeigen"] is None
        assert "kleinanzeigen" not in (c.get("accuracy") or {})
    ka = next(s for s in pub["sources"] if s["id"] == "kleinanzeigen")
    ka_full = next(s for s in doc["sources"] if s["id"] == "kleinanzeigen")
    assert ka["records"] is None and ka["in_score"] is True
    assert (pub["kpis"]["shop_listings_checked"]
            == doc["kpis"]["shop_listings_checked"] - ka_full["records"])
    assert pub["kpis"]["records_counted"] == doc["kpis"]["records_counted"] - ka_full["records"]
    bc = next(s for s in pub["benchmark_comparison"]["sources"] if s["id"] == "kleinanzeigen")
    assert bc["benchmark_value"] is None
    # Scores are kept: same ranks and index.
    assert ([(c["key"], c["rank"], c["index"]) for c in pub["characters"]]
            == [(c["key"], c["rank"], c["index"]) for c in doc["characters"]])
    # The full document is not modified.
    assert "regions" in doc and doc["meta"]["edition"] == "full"


def test_public_schema_rejects_full_edition_only_blocks(public_aux_dir):
    aux_dir = public_aux_dir
    import copy
    from jsonschema import ValidationError
    from nga.release.public import public_edition

    pub = public_edition(build(make_result(), aux_dir, **FIXED))
    bad = copy.deepcopy(pub)
    bad["regions"] = build(make_result(), aux_dir, **FIXED)["regions"]
    with pytest.raises(ValidationError):
        schema_validate(bad, SCHEMA)


def test_public_edition_refuses_a_comparable_kleinanzeigen(aux_dir):
    from nga.release.public import public_edition

    (aux_dir / "sources_ka.json").write_text(json.dumps([
        {"id": "kleinanzeigen", "records": 1500, "in_score": True}]))
    with pytest.raises(ValueError, match="must not be comparable"):
        public_edition(build(make_result(), aux_dir, **FIXED))
