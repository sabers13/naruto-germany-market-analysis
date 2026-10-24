"""Locations of the read-only archive and the local work/release folders.

Every module gets paths from here; nothing else hard-codes a path.
"""
from __future__ import annotations

import os
import subprocess
import tomllib
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@lru_cache
def config() -> dict:
    return tomllib.loads((REPO / "config/paths.toml").read_text())


def archive() -> Path:
    return Path(os.environ.get("NGA_ARCHIVE", config()["archive"]["root"]))


def dataset(*parts: str) -> Path:
    """Path inside the archive's datasets/ folder, e.g. dataset("ebay", "data", "ebay_de_observations.parquet")."""
    return archive().joinpath("datasets", *parts)


def work(*parts: str) -> Path:
    p = REPO.joinpath(config()["local"]["work"], *parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def release(*parts: str) -> Path:
    return REPO.joinpath(config()["local"]["release"], *parts)


def reports(*parts: str) -> Path:
    return REPO.joinpath(config()["local"]["reports"], *parts)


def archive_commit() -> str:
    return subprocess.run(["git", "-C", str(archive()), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def check_archive() -> str:
    """Refuse to run on an archive commit other than the pinned one (ANALYSIS_PLAN.md §3)."""
    pinned, actual = config()["archive"]["commit"], archive_commit()
    if actual != pinned and os.environ.get("NGA_ALLOW_ARCHIVE_DRIFT") != "1":
        raise RuntimeError(f"archive is at {actual}, analysis is pinned to {pinned}; "
                           "check out the pinned commit or set NGA_ALLOW_ARCHIVE_DRIFT=1 and log why")
    return actual
