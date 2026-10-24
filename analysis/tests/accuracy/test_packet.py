"""Tests for the labelling packet. Synthetic samples only."""
import pandas as pd
import pytest

from nga.accuracy.packet import run, write_packet
from nga.accuracy.sample import draw_sample

from conftest import make_matches


@pytest.fixture
def small_sample() -> pd.DataFrame:
    df = make_matches({("amazon", "sasuke_uchiha"): 50, ("amazon", "hinata_hyuga"): 20,
                       ("ebay", "sasuke_uchiha"): 50, ("ebay", "nagato_pain"): 20})
    return draw_sample(df, seed=20261023)


def test_packet_lists_every_item_with_snippet(tmp_path, small_sample):
    packet, template = tmp_path / "packet.md", tmp_path / "labels_template.csv"
    write_packet(small_sample, packet, template)
    text = packet.read_text()
    for label in ("correct", "wrong_character", "not_naruto", "unclear"):
        assert label in text  # instructions define every label
    for _, row in small_sample.iterrows():
        assert row["sample_id"] in text
        assert row["snippet"] in text  # snippets belong in work/, and this is work/


def test_template_is_an_empty_form(tmp_path, small_sample):
    packet, template = tmp_path / "packet.md", tmp_path / "labels_template.csv"
    write_packet(small_sample, packet, template)
    form = pd.read_csv(template)
    assert form.columns.tolist() == ["sample_id", "label", "note"]
    assert len(form) == 0


def test_run_needs_a_sample_first(tmp_path):
    with pytest.raises(FileNotFoundError):
        run(sample_path=tmp_path / "missing.parquet",
            packet_path=tmp_path / "packet.md",
            template_path=tmp_path / "labels_template.csv")
