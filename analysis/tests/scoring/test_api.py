"""API surface tests: INTERFACES.md shape, dtypes, CLI writers."""

import inspect
import json

import pandas as pd
import pytest

from nga.scoring import ScoreResult, score
from nga.scoring.__main__ import write_outputs

from .synth import FIXTURE_ENTRIES, metrics_frame


def test_api_signature_matches_interfaces():
    sig = inspect.signature(score)
    assert list(sig.parameters) == ["metrics_df", "precision_df", "weights"]
    assert sig.parameters["precision_df"].default is None
    assert sig.parameters["weights"].default is None


def test_characters_columns_and_dtypes():
    result = score(metrics_frame(FIXTURE_ENTRIES))
    assert list(result.characters.columns) == [
        "character_key",
        "rank",
        "index",
        "score",
        "shoppers",
        "watching",
        "votes",
        "top3_sources",
        "confidence",
        "flags",
    ]
    assert str(result.characters["rank"].dtype) == "Int64"
    assert str(result.characters["index"].dtype) == "Int64"
    assert all(isinstance(f, list) for f in result.characters["flags"])
    assert set(result.characters["confidence"]) <= {"robust", "mixed", "one_source", None}
    assert isinstance(result, ScoreResult)


def test_source_ranks_shape():
    result = score(metrics_frame(FIXTURE_ENTRIES))
    assert list(result.source_ranks.columns) == [
        "character_key",
        "amazon",
        "ebay",
        "kleinanzeigen",
        "youtube",
        "google_trends",
        "anime2you",
        "narutop99",
    ]
    assert len(result.source_ranks) == 4


def test_custom_weights_are_used():
    result = score(
        metrics_frame(FIXTURE_ENTRIES),
        weights={"shoppers": 1.0, "watching": 0.0, "votes": 0.0},
    )
    rows = result.characters.set_index("character_key")
    assert rows.loc["sasuke_uchiha", "score"] == pytest.approx(1.0)
    assert result.detail["weights"] == {
        "shoppers": 1.0,
        "watching": 0.0,
        "votes": 0.0,
    }


def test_write_outputs_roundtrip(tmp_path):
    result = score(metrics_frame(FIXTURE_ENTRIES))
    write_outputs(result, tmp_path)
    chars = pd.read_parquet(tmp_path / "characters.parquet")
    ranks = pd.read_parquet(tmp_path / "source_ranks.parquet")
    rob = json.loads((tmp_path / "robustness.json").read_text())
    assert list(chars["character_key"]) == list(result.characters["character_key"])
    assert list(ranks["character_key"]) == list(result.source_ranks["character_key"])
    assert rob == result.robustness
