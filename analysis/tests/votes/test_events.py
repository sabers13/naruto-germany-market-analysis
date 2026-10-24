"""Event-selection unit tests (synthetic) + archive tests."""
import json

import duckdb
import jsonschema
import pandas as pd
import pytest

from nga.paths import REPO, dataset
from nga.votes import events

archive_present = pytest.mark.skipif(
    not dataset("event_calendar", "data", "events.parquet").exists(),
    reason="data archive not on disk")


def _row(eid, date, etype="other", region="de", conf="confirmed",
         scope="naruto", title="T", notes="announced", url="https://x.test/"):
    return {"event_id": eid, "date_start": pd.Timestamp(date),
            "event_type": etype, "region_scope": region, "confidence": conf,
            "franchise_scope": scope, "title_en": title, "notes": notes,
            "source_url": url}


def test_selection_rule_synthetic():
    rows = [
        _row("brand", "2025-03-01", "brand_specific", title="X announced"),
        _row("rep", "2025-05-01", "other", conf="reported", notes="announced"),
        _row("jp", "2025-06-01", "merch_drop", region="jp"),
        _row("unconf", "2025-07-01", "other", conf="announced_unconfirmed"),
        _row("a_old", "2025-08-01", "anime_release", region="global"),
        _row("a_new", "2025-09-01", "manga_release", region="global"),
    ]
    # eight confirmed DE rows: only the newest may fill the step-1 slots
    for i in range(8):
        rows.append(_row(f"d{i}", f"2024-0{i + 1}-15", "other"))
    chosen = events.select_events(rows)
    ids = [r["event_id"] for r in chosen]
    assert len(ids) <= events.MAX_EVENTS
    dates = [str(r["date_start"])[:10] for r in chosen]
    assert dates == sorted(dates)  # oldest first
    assert "brand" not in ids  # only franchise event types are selected
    assert "rep" not in ids and "jp" not in ids and "unconf" not in ids
    assert "a_new" in ids and "a_old" not in ids  # newest announcement only
    assert "d0" not in ids and "d7" in ids  # newest-first fill


def test_announcement_predicate():
    assert events._is_announcement(
        _row("a", "2025-01-01", "anime_release", region="global"))
    assert not events._is_announcement(
        _row("s", "2025-01-01", "streaming_availability_de"))
    assert not events._is_announcement(
        _row("j", "2025-01-01", "other", region="jp"))


def _schema(name):
    schema = json.loads((REPO / "contract/dashboard.schema.json").read_text())
    return schema["properties"][name]


@pytest.mark.archive
@archive_present
def test_builtin_selection_matches_plan():
    df = events.load_events()
    assert set(df["event_type"]) <= set(events.EVENT_TYPES)
    chosen = events.select_events(df.to_dict("records"))
    assert len(chosen) == events.MAX_EVENTS
    assert all(r["event_type"] in events.EVENT_TYPES for r in chosen)
    assert all(r["confidence"] == "confirmed" for r in chosen)
    de = [r for r in chosen
          if r["event_id"] !=
          "ev_20261011_project_rasengan_announced_new_manga_naruto_shad"]
    assert all(r["region_scope"] == "de" for r in de)
    dates = [str(r["date_start"])[:10] for r in chosen]
    assert dates == sorted(dates)
    assert all("2021-10-01" <= d <= "2026-10-22" for d in dates)


@pytest.mark.archive
@archive_present
def test_built_events_validate_against_contract():
    doc = events.build_events()
    jsonschema.validate(doc, _schema("events"),
                        format_checker=jsonschema.FormatChecker())
    assert len(doc) == events.MAX_EVENTS
    assert {e["owner"] for e in doc} == {"franchise"}
    # lane-written, facts-only: no archive curator copy beyond named entities
    assert all(e["source_url"].startswith("https://") for e in doc)
