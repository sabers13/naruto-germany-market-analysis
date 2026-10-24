"""The locked character dictionary (config/characters.yaml)."""
from __future__ import annotations

from functools import lru_cache

import yaml

from .paths import REPO


@lru_cache
def load() -> dict:
    return yaml.safe_load((REPO / "config/characters.yaml").read_text())


def keys(role: str | None = None) -> list[str]:
    """All 14 keys, or only 'candidate' (13) / 'benchmark' (1)."""
    d = load()
    if role is None:
        return d["roles"]["benchmark"] + d["roles"]["candidate"]
    return list(d["roles"][role])


def name(key: str) -> str:
    return load()["characters"][key]["name"]


def flags(key: str) -> list[str]:
    return list(load()["characters"][key].get("flags", []))


def source_map(source: str) -> dict[str, str]:
    """Map a source's own spelling → canonical key, e.g. source_map("ebay")["pain_nagato"] == "nagato_pain"."""
    out: dict[str, str] = {}
    for key, c in load()["characters"].items():
        v = c["source_keys"].get(source)
        for spelling in (v if isinstance(v, list) else [v]):
            if spelling is not None:
                out[spelling] = key
    return out


def text_aliases(key: str) -> list[str]:
    return list(load()["characters"][key]["text_aliases"])


def context_words() -> list[str]:
    return list(load()["naruto_context_words"])
