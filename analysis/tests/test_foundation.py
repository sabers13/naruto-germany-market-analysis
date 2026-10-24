"""Baseline tests: config, character dictionary, metrics table and contract.

Tests marked `archive` read the data archive and are skipped when it isn't on disk.
Archive tests assert only on sets of keys / aggregate counts, never on row content.
"""
import copy
import json
import tempfile
from pathlib import Path

import duckdb
import pandas as pd
import pytest
import yaml
from jsonschema import validate as schema_validate
from jsonschema.exceptions import ValidationError

from nga import characters, metrics, paths

archive_present = pytest.mark.skipif(not paths.archive().exists(), reason="data archive not on disk")


def test_fourteen_locked_characters():
    assert len(characters.keys()) == 14
    assert characters.keys("benchmark") == ["naruto_uzumaki"]
    assert len(characters.keys("candidate")) == 13
    assert "sakura_haruno" not in characters.keys()
    assert "boruto_uzumaki" not in characters.keys()


def test_source_maps_cover_every_character():
    for source in ["amazon", "ebay", "kleinanzeigen", "youtube", "wikimedia", "anime2you", "narutop99", "trends_term"]:
        assert set(characters.source_map(source).values()) == set(characters.keys()), source


def test_metrics_validator_accepts_a_good_row_and_rejects_a_bad_one():
    row = dict(character_key="sasuke_uchiha", source="ebay", metric="items", period="snapshot", region="DE",
               value=623.0, n=623, unit="count", evidence_class="D", lens="shoppers", primary=True, lane="shops")
    metrics.validate(pd.DataFrame([row]))
    with pytest.raises(ValueError):
        metrics.validate(pd.DataFrame([row | {"character_key": "sakura_haruno"}]))
    with pytest.raises(ValueError):
        metrics.validate(pd.DataFrame([row, row]))  # duplicate


def test_synthetic_release_matches_contract():
    schema = json.loads((paths.REPO / "contract/dashboard.schema.json").read_text())
    schema_validate(_load_fixture_doc(), schema)


def _load_schema():
    return json.loads((paths.REPO / "contract/dashboard.schema.json").read_text())


def _load_fixture_doc():
    """A full release built from the synthetic test inputs (no archive needed)."""
    from release.synth import make_aux, make_result
    from nga.release import build

    with tempfile.TemporaryDirectory() as tmp:
        aux = Path(tmp) / "aux"
        make_aux(aux, paths.REPO / "config/states.yaml")
        return build(make_result(), aux, generated_utc="2026-10-23T00:00:00Z",
                     snapshot_date="2026-10-22", archive_commit="a" * 40,
                     input_sha256="b" * 64)


def _synthetic_110_doc():
    """Synthetic doc: fixture with one comparable source and one ratio entry."""
    doc = copy.deepcopy(_load_fixture_doc())
    doc["benchmark_comparison"] = {
        "benchmark": "naruto_uzumaki",
        "sources": [
            {"id": "amazon", "metric": "asins", "comparable": False, "reason": "precision_low",
             "detail": "Naruto precision 0.60", "benchmark_value": 120},
            {"id": "ebay", "metric": "items", "comparable": False, "reason": "precision_low",
             "benchmark_value": 340},
            {"id": "kleinanzeigen", "metric": "offer_ads", "comparable": True, "reason": "explicit_tags",
             "benchmark_value": 60},
            {"id": "youtube_comments", "metric": "comments_de", "comparable": False,
             "reason": "not_measured", "benchmark_value": None},
            {"id": "youtube_videos", "metric": "videos_de", "comparable": False,
             "reason": "not_measured", "benchmark_value": None},
            {"id": "google_trends", "metric": "interest_52w", "comparable": False,
             "reason": "franchise_dominated", "detail": "r = 0.94 with franchise topic",
             "benchmark_value": 28.4},
            {"id": "anime2you_comments", "metric": "comment_mentions", "comparable": False,
             "reason": "alias_restricted", "benchmark_value": 3},
            {"id": "anime2you_articles", "metric": "articles", "comparable": False,
             "reason": "not_measured", "benchmark_value": None},
            {"id": "narutop99", "metric": "votes_eu", "comparable": True, "reason": "vote",
             "benchmark_value": 5000},
        ],
        "by_character": {
            "sasuke_uchiha": {"ratios": {"kleinanzeigen": 1.24, "narutop99": 1.0},
                              "comparable_sources": 2, "ahead_in": 2},
        },
    }
    return doc


def test_contract_110_fixture_and_synthetic_validate():
    schema = _load_schema()
    schema_validate(_load_fixture_doc(), schema)
    schema_validate(_synthetic_110_doc(), schema)


def test_contract_110_missing_benchmark_comparison_fails():
    schema = _load_schema()
    doc = copy.deepcopy(_load_fixture_doc())
    del doc["benchmark_comparison"]
    with pytest.raises(ValidationError):
        schema_validate(doc, schema)


def test_contract_110_extra_lens_rank_key_fails():
    schema = _load_schema()
    doc = copy.deepcopy(_load_fixture_doc())
    doc["characters"][0]["lens_ranks"]["extra_lens"] = 1
    with pytest.raises(ValidationError):
        schema_validate(doc, schema)


@pytest.mark.archive
@archive_present
def test_archive_is_at_pinned_commit():
    assert paths.check_archive() == paths.config()["archive"]["commit"]


@pytest.mark.archive
@archive_present
def test_core_tables_exist():
    for parts in [("amazon", "out", "amazon_search_cards.parquet"),
                  ("ebay", "data", "ebay_de_observations.parquet"),
                  ("kleinanzeigen", "raw", "final", "listings.parquet"),
                  ("youtube", "raw", "parquet", "naruto-de-youtube-v1__comments.parquet"),
                  ("google_trends", "raw", "20261022T1000Z__full", "out", "parquet", "timeseries_bridged.parquet"),
                  ("anime2you", "data", "full", "comments.parquet"),
                  ("event_calendar", "data", "events.parquet")]:
        assert paths.dataset(*parts).exists(), parts


def _archive_key_set(sql, params):
    """Distinct non-null key set from one DuckDB query over the archive."""
    con = duckdb.connect()
    return {r[0] for r in con.execute(sql, params).fetchall() if r[0] is not None}


def _json_list_key_set(parquet, column, where=""):
    """Distinct set of keys stored as JSON lists in one parquet column."""
    con = duckdb.connect()
    values = con.execute(
        f"SELECT {column} FROM read_parquet(?) {where}", [str(parquet)]
    ).fetchall()
    out = set()
    for (raw,) in values:
        if raw:
            items = json.loads(raw)
            out.update(items if isinstance(items, list) else [items])
    return out


def _entity_key_set(column, *parts, wrapped=True):
    """Distinct set of entity keys in a JSON mentions column.

    YouTube stores {"entities": {key: ...}} (wrapped=True);
    a flat {key: ...} mapping is read with wrapped=False.
    """
    con = duckdb.connect()
    values = con.execute(
        f"SELECT {column} FROM read_parquet(?)", [str(paths.dataset(*parts))]
    ).fetchall()
    out = set()
    for (raw,) in values:
        if raw:
            doc = json.loads(raw)
            out.update(doc.get("entities", {}).keys() if wrapped else doc.keys())
    return out


@pytest.mark.archive
@archive_present
def test_spellings_exist_in_archive():
    """Every per-source spelling in config/characters.yaml occurs in the archive.

    Asserts only on sets of keys (expected subset of observed), never on row content.
    YouTube unions videos + comments; both spellings of kakashi are covered.
    """
    observed = {
        "amazon": _archive_key_set(
            "SELECT DISTINCT trim(unnest(string_split(character_matches, ?))) "
            "FROM read_parquet(?)", [";", str(paths.dataset("amazon", "out", "amazon_search_cards.parquet"))]),
        "ebay": _json_list_key_set(
            paths.dataset("ebay", "data", "ebay_de_observations.parquet"), "character_matches"),
        "kleinanzeigen": _json_list_key_set(
            paths.dataset("kleinanzeigen", "raw", "final", "listings.parquet"), "character_tags"),
        "youtube": _entity_key_set(
            "d_mentions",
            "youtube", "raw", "parquet", "naruto-de-youtube-v1__videos.parquet")
        | _entity_key_set(
            "d_mentions",
            "youtube", "raw", "parquet", "naruto-de-youtube-v1__comments.parquet"),
        "wikimedia": _archive_key_set(
            "SELECT DISTINCT character_key FROM read_parquet(?)",
            [str(paths.dataset("wikimedia", "collector", "exports",
                               "full_2026-10-22", "entities.parquet"))]),
        "anime2you": _json_list_key_set(
            paths.dataset("anime2you", "data", "full", "posts.parquet"), "characters_mentioned"),
        "narutop99": _archive_key_set(
            "SELECT DISTINCT name_en FROM read_parquet(?) WHERE region = 'europe'",
            [str(paths.dataset("anime2you", "data", "external", "narutop99",
                               "narutop99_rankings.parquet"))]),
        "trends_term": _archive_key_set(
            "SELECT DISTINCT term_raw FROM read_parquet(?)",
            [str(paths.dataset("google_trends", "raw", "20261022T1000Z__full",
                               "out", "parquet", "timeseries_bridged.parquet"))]),
    }
    for source, archive_keys in observed.items():
        expected = set(characters.source_map(source).keys())
        assert expected <= archive_keys, (source, sorted(expected - archive_keys))


@pytest.mark.archive
@archive_present
def test_states_map_archive():
    """Every Kleinanzeigen `state` value maps to one code in config/states.yaml (16 total)."""
    states = yaml.safe_load((paths.REPO / "config/states.yaml").read_text())
    archive_states = _archive_key_set(
        "SELECT DISTINCT state FROM read_parquet(?)",
        [str(paths.dataset("kleinanzeigen", "raw", "final", "listings.parquet"))])
    assert archive_states == set(states.keys()), sorted(archive_states ^ set(states.keys()))
    assert len(states) == 16
    assert len({v["code"] for v in states.values()}) == 16  # one code per state


@pytest.mark.archive
@archive_present
def test_trends_topics_exist_in_archive():
    """Each non-null trends_topic exists in timeseries_bridged.parquet with weekly rows."""
    topics = {k: v["source_keys"].get("trends_topic")
              for k, v in characters.load()["characters"].items()}
    topics = {k: t for k, t in topics.items() if t is not None}
    assert len(topics) == 12  # plan section 4: 12 of 14 have a topic series
    archive_terms = _archive_key_set(
        "SELECT DISTINCT term_raw FROM read_parquet(?)",
        [str(paths.dataset("google_trends", "raw", "20261022T1000Z__full",
                           "out", "parquet", "timeseries_bridged.parquet"))])
    con = duckdb.connect()
    parquet = str(paths.dataset("google_trends", "raw", "20261022T1000Z__full",
                                "out", "parquet", "timeseries_bridged.parquet"))
    for key, topic in sorted(topics.items()):
        assert topic in archive_terms, (key, topic)
        weekly = con.execute(
            "SELECT COUNT(*) FROM read_parquet(?) WHERE term_raw = ? AND resolution = 'WEEK'",
            [parquet, topic]).fetchone()[0]
        assert weekly > 0, (key, topic)
