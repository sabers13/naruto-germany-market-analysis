"""Dashboard event timeline (ANALYSIS_PLAN.md §4, event-calendar row).

Selection, in this order (``select_events`` is pure and unit-tested):

1. ``confirmed`` German-relevant events (``region_scope`` de/dach) inside the
   archive's core window (2021-10 -> 2026-10), newest first, filling all
   slots but one;
2. the newest ``confirmed`` franchise announcement.

Only franchise event types (``EVENT_TYPES``, an allowlist) are used; any
other row of the event calendar is never selected.

``EVENT_TEXTS`` holds the lane-written EN/DE titles and notes (facts only, no
copied article text), keyed by event_id. Unknown ids raise KeyError instead
of silently copying archive copy.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from nga.paths import dataset

MAX_EVENTS = 6
EVENT_TYPES = (
    "anime_release", "anime_episode_arc", "german_dub_release",
    "streaming_availability_de", "tv_broadcast_de", "manga_release",
    "manga_release_de", "movie_release", "game_release", "anniversary",
    "official_poll", "convention_de", "merch_drop", "other",
)
CORE_START = "2021-10-01"
CORE_END = "2026-10-22"  # snapshot date

EVENT_TEXTS = {
    "ev_20260612_disney_adds_naruto_first_52_episodes_in_germany": {
        "title_en": "Naruto arrives on Disney+ Germany",
        "title_de": "Naruto startet bei Disney+ Deutschland",
        "note_en": "First 52 episodes, German dub and Japanese with German subtitles.",
        "note_de": "Erste 52 Folgen, deutsche Synchronfassung und Japanisch mit deutschen Untertiteln.",
    },
    "ev_20260212_magentatv_adds_the_free_24_7_naruto_fast_channel": {
        "title_en": "MagentaTV starts free Naruto channel",
        "title_de": "MagentaTV startet kostenlosen Naruto-Sender",
        "note_en": "Free 24/7 channel with Naruto, Shippuden and Boruto in German.",
        "note_de": "Kostenloser 24/7-Sender mit Naruto, Shippuden und Boruto auf Deutsch.",
    },
    "ev_20251218_naruto_collector_s_edition_blu_ray_boxes_1_and_2": {
        "title_en": "Naruto Collector's Edition boxes 1 and 2 released",
        "title_de": "Naruto Collector's Edition Box 1 und 2 erschienen",
        "note_en": "KSM Anime Blu-ray boxes, both released 18 December 2025.",
        "note_de": "KSM-Anime-Blu-ray-Boxen, beide erschienen am 18. Dezember 2025.",
    },
    "ev_20251028_flow_world_tour_2025_naruto_the_rock_hamburg_geo": {
        "title_en": "FLOW 'Naruto the Rock' concert in Hamburg",
        "title_de": "FLOW-Konzert 'Naruto the Rock' in Hamburg",
        "note_en": "Third of three German tour dates, Georg Elser Halle.",
        "note_de": "Dritter von drei Deutschland-Terminen, Georg Elser Halle.",
    },
    "ev_20251024_flow_world_tour_2025_naruto_the_rock_berlin_colu": {
        "title_en": "FLOW 'Naruto the Rock' concert in Berlin",
        "title_de": "FLOW-Konzert 'Naruto the Rock' in Berlin",
        "note_en": "Second of three German tour dates, Columbiahalle.",
        "note_de": "Zweiter von drei Deutschland-Terminen, Columbiahalle.",
    },
    "ev_20261011_project_rasengan_announced_new_manga_naruto_shad": {
        "title_en": "New Naruto manga announced",
        "title_de": "Neuer Naruto-Manga angekündigt",
        "note_en": "'Project Rasengan': new manga 'Naruto: Shadow Rising' by Masashi Kishimoto.",
        "note_de": "'Project Rasengan': neuer Manga 'Naruto: Shadow Rising' von Masashi Kishimoto.",
    },
}


def _date(row: dict) -> str:
    return str(row["date_start"])[:10]


def select_events(rows: list[dict]) -> list[dict]:
    """Apply the two-step rule; return the chosen rows, oldest first."""
    rows = [r for r in rows if r["event_type"] in EVENT_TYPES]
    pool = [r for r in rows
            if r["confidence"] == "confirmed"
            and r.get("region_scope") in ("de", "dach")
            and CORE_START <= _date(r) <= CORE_END]
    pool.sort(key=_date, reverse=True)

    slots = MAX_EVENTS - 1  # step 2 always reserves one slot
    chosen = pool[:slots]

    announcements = [r for r in rows
                     if r["event_id"] not in {c["event_id"] for c in chosen}
                     and r["confidence"] == "confirmed"
                     and _is_announcement(r)]
    announcements.sort(key=_date, reverse=True)
    if announcements:
        chosen.append(announcements[0])
    chosen = chosen[:MAX_EVENTS]
    chosen.sort(key=_date)
    return chosen


def _is_announcement(row: dict) -> bool:
    """A confirmed event whose substance is a franchise reveal/announcement.

    Operationalised as: global- or DE-scoped, confirmed, and either an
    anime/manga/movie/game release-type row whose title or notes place the
    actual release in the future (announcement-vs-release decision rule), or
    an explicit reveal/announcement row. Rows about availability that already
    holds (streaming catalogue adds, TV broadcasts, dub discs, concerts) are
    not announcements.
    """
    if row["event_type"] in ("streaming_availability_de", "tv_broadcast_de",
                             "german_dub_release", "convention_de"):
        return False
    if row.get("region_scope") not in ("global", "de", "dach", "eu"):
        return False
    text = f"{row.get('title_en', '')} {row.get('notes', '')}".lower()
    return any(k in text for k in (
        "announc", "reveal", "confirms", "casting call", "teaser",
        "what's next", "whats next"))


def load_events() -> pd.DataFrame:
    """Read the event calendar in place."""
    con = duckdb.connect()
    marks = ", ".join("?" for _ in EVENT_TYPES)
    df = con.execute(
        "SELECT event_id, date_start, event_type, region_scope, confidence,"
        " franchise_scope, title_en, notes, source_url"
        f" FROM read_parquet(?) WHERE event_type IN ({marks})",
        [str(dataset("event_calendar", "data", "events.parquet")), *EVENT_TYPES],
    ).fetch_df()
    con.close()
    return df


def build_events(df: pd.DataFrame | None = None) -> list[dict]:
    """Select events and render the contract ``events`` array."""
    if df is None:
        df = load_events()
    rows = df.to_dict("records")
    entries = []
    for row in select_events(rows):
        texts = EVENT_TEXTS[row["event_id"]]  # KeyError: write texts first
        entries.append({
            "id": row["event_id"],
            "date": str(row["date_start"])[:10],
            "owner": "franchise",
            "confidence": row["confidence"],
            "title_en": texts["title_en"],
            "title_de": texts["title_de"],
            "note_en": texts["note_en"],
            "note_de": texts["note_de"],
            "source_url": row["source_url"],
        })
    for e in entries:
        if not e["source_url"]:
            raise ValueError(f"event {e['id']} has no source_url")
    return entries
