"""Provenance for the validated release (ANALYSIS_PLAN.md §9).

Computes meta fields that trace release/dashboard.json back to the pinned
archive: the archive commit and a sha256 over every archive file the lanes
read. Pure helpers take explicit paths so tests can run on synthetic files;
only archive_commit() / input_sha256() touch the real archive.
"""
from __future__ import annotations

import glob
import hashlib
from pathlib import Path

from nga.paths import REPO, archive, check_archive, config

# Archive-relative dataset files named in ANALYSIS_PLAN.md §4. Used when no
# sources_*.json entry lists its input files (the interface table only
# requires {id, records, in_score}; the "files" key is an optional extra).
# Globs are allowed.
# Archive-relative dataset files named in ANALYSIS_PLAN.md §4 (relative to
# paths.archive(), i.e. under datasets/, mirroring nga.paths.dataset()).
FALLBACK_INPUTS = [
    "datasets/amazon/out/amazon_search_cards.parquet",
    "datasets/ebay/data/ebay_de_observations.parquet",
    "datasets/kleinanzeigen/raw/final/listings.parquet",
    "datasets/youtube/raw/parquet/naruto-de-youtube-v1__videos.parquet",
    "datasets/youtube/raw/parquet/naruto-de-youtube-v1__comments.parquet",
    "datasets/google_trends/raw/20261022T1000Z__full/out/parquet/timeseries_bridged.parquet",
    "datasets/google_trends/raw/20261022T1000Z__full/out/parquet/geo.parquet",
    "datasets/anime2you/data/full/posts.parquet",
    "datasets/anime2you/data/full/comments.parquet",
    "datasets/anime2you/data/external/narutop99/narutop99_rankings.parquet",
    "datasets/wikimedia/collector/exports/full_2026-10-22/pageviews.parquet",
    "datasets/event_calendar/data/events.parquet",
]


def contract_version() -> str:
    """Release contract version, read from contract/CONTRACT_VERSION."""
    return (REPO / "contract" / "CONTRACT_VERSION").read_text().strip()


def archive_commit() -> str:
    """Pinned archive commit; refuses to run on drift (plan §3)."""
    return check_archive()


def snapshot_date() -> str:
    return config()["snapshot"]["date"]


def hash_files(entries: list[tuple[str, Path]]) -> str:
    """sha256 over the sorted list of (relpath, file-sha256) lines."""
    lines = []
    for rel, path in sorted(entries, key=lambda e: e[0]):
        lines.append(f"{rel} {hashlib.sha256(path.read_bytes()).hexdigest()}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def collect_input_files(aux_dir: str | Path, archive_root: Path | None = None) -> list[tuple[str, Path]]:
    """Every archive file the lanes read, as (archive-relative, absolute) pairs.

    Prefers the optional "files" lists in work/aux/sources_*.json; falls back
    to the ANALYSIS_PLAN.md §4 table when no entry lists files.
    """
    aux_dir = Path(aux_dir)
    root = archive_root or archive()
    rels: list[str] = []
    for src_file in sorted(aux_dir.glob("sources_*.json")):
        import json

        for entry in json.loads(src_file.read_text()):
            rels.extend(entry.get("files", []))
    if not rels:
        rels = list(FALLBACK_INPUTS)
    out: list[tuple[str, Path]] = []
    for rel in rels:
        matches = sorted(glob.glob(rel, root_dir=str(root), recursive=True))
        if not matches:
            raise FileNotFoundError(f"release input missing from archive: {rel}")
        out.extend((m, root / m) for m in matches)
    # dedupe, keep sorted order
    return sorted(set(out), key=lambda e: e[0])


def input_sha256(aux_dir: str | Path, archive_root: Path | None = None) -> str:
    return hash_files(collect_input_files(aux_dir, archive_root))


def release_id_for(contract_version: str, snapshot: str, content_sha256: str) -> str:
    """Content-derived release id.

    ``v<contract_version>-<snapshot YYYYMMDD>-<first 8 hex of sha256 over
    the release JSON with release_id set to "">``: identical content gives
    an identical id, any value change gives a different one.
    """
    return f"v{contract_version}-{snapshot.replace('-', '')}-{content_sha256[:8]}"


def make_meta(
    *,
    generated_utc: str,
    snapshot: str,
    commit: str,
    digest: str,
    youtube_snapshot: str | None = None,
    notes: list[str] | None = None,
    release_id: str = "",
) -> dict:
    return {
        "contract_version": contract_version(),
        "release_id": release_id,
        "status": "validated",
        "generated_utc": generated_utc,
        "snapshot_date": snapshot,
        "archive_commit": commit,
        "youtube_snapshot": youtube_snapshot or snapshot,
        "input_sha256": digest,
        "notes": notes
        if notes is not None
        else [
            "Validated release: deduped entity counts, accuracy-checked.",
            "generated_utc is pinned to the snapshot date (midnight UTC) for reproducible hashes.",
            "change_12m is rounded to 1 dp; momentum series values to 2 dp.",
            "records counts only rows of series that feed the score (censored Trends series excluded).",
            "counts.google_interest is null where the series is censored in the request view used (missing, never zero).",
        ],
    }


def default_notes() -> list[str]:
    return make_meta(generated_utc="", snapshot="", commit="", digest="")["notes"]
