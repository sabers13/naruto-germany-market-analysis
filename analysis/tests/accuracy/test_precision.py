"""Tests for precision scoring. Synthetic samples and labels only."""
import pandas as pd
import pytest

from nga.accuracy.precision import (
    STOP_THRESHOLD,
    compute_precision,
    run,
    sources_below_stop,
    treatment_for,
    wilson,
)
from nga.accuracy.sample import draw_sample

from conftest import SOURCES, make_labels, make_matches, write_matches


def test_wilson_against_known_values():
    p, lo, hi = wilson(80, 100)
    assert (p, lo, hi) == pytest.approx((0.8, 0.711169, 0.866634), abs=1e-6)
    p, lo, hi = wilson(9, 10)
    assert (p, lo, hi) == pytest.approx((0.9, 0.595844, 0.982124), abs=1e-6)
    assert wilson(0, 10) == pytest.approx((0.0, 0.0, 0.277540), abs=1e-6)
    assert wilson(10, 10) == pytest.approx((1.0, 0.722460, 1.0), abs=1e-6)
    with pytest.raises(ValueError):
        wilson(0, 0)


def test_treatment_thresholds_exact_boundaries():
    assert treatment_for(1.0) == "use"
    assert treatment_for(0.90) == "use"      # exact 0.90 -> use
    assert treatment_for(0.8999) == "adjust"
    assert treatment_for(0.70) == "adjust"   # exact 0.70 -> adjust
    assert treatment_for(0.6999) == "exclude"
    assert treatment_for(0.0) == "exclude"


@pytest.fixture
def scored() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One source, three characters: big/use, big/adjust, small/pooled."""
    matches = make_matches({("amazon", "sasuke_uchiha"): 60,
                            ("amazon", "hinata_hyuga"): 60,
                            ("amazon", "obito_uchiha"): 6})
    sample = draw_sample(matches, seed=20261023)
    sasuke = sample[sample.character_key == "sasuke_uchiha"].sample_id.tolist()
    hinata = sample[sample.character_key == "hinata_hyuga"].sample_id.tolist()
    # sasuke 9/10-ish correct -> use; hinata ~7/10 correct -> adjust; obito pooled
    wrong = sasuke[::10][:1] + hinata[::3][:4]
    labels = make_labels(sample, wrong_ids=wrong)
    return sample, labels, compute_precision(sample, labels)


def test_per_character_rows_and_small_char_pooling(scored):
    _, _, precision = scored
    assert set(precision.columns) == {"source", "character_key", "n", "correct",
                                      "precision", "ci_low", "ci_high", "treatment"}
    assert "obito_uchiha" not in set(precision.character_key)  # n < 10: pooled
    assert "_all" in set(precision.character_key)


def test_unclear_counts_as_wrong():
    matches = make_matches({("ebay", "sasuke_uchiha"): 60})
    sample = draw_sample(matches, seed=20261023)
    ids = sample.sample_id.tolist()
    labels = make_labels(sample, unclear_ids=set(ids[:3]))
    precision = compute_precision(sample, labels)
    row = precision[(precision.source == "ebay") & (precision.character_key == "sasuke_uchiha")]
    assert row.iloc[0]["correct"] == len(sample) - 3
    assert row.iloc[0]["precision"] == pytest.approx((len(sample) - 3) / len(sample))


def test_treatment_boundaries_through_labels():
    matches = make_matches({("ebay", "sasuke_uchiha"): 30, ("ebay", "gaara"): 30,
                            ("ebay", "madara_uchiha"): 30})
    sample = draw_sample(matches, seed=20261023)
    # Build exact-rate labels directly: 10 labelled rows per char.
    tiny = sample.groupby("character_key").head(10).copy()
    plan = {"sasuke_uchiha": 9, "gaara": 7, "madara_uchiha": 6}  # -> use/adjust/exclude
    rows = []
    for char, k in plan.items():
        ids = tiny[tiny.character_key == char].sample_id.tolist()
        for j, sid in enumerate(ids):
            lab = "correct" if j < k else "wrong_character"
            base = tiny[tiny.sample_id == sid].iloc[0]
            rows.append({"sample_id": sid, "source": base["source"],
                         "character_key": char, "record_hash": base["record_hash"],
                         "label": lab, "labeller_model": "t", "note": ""})
    labels = pd.DataFrame(rows)
    precision = compute_precision(tiny, labels)
    got = {r.character_key: r.treatment for r in precision.itertuples()
           if r.character_key != "_all"}
    assert got == {"sasuke_uchiha": "use", "gaara": "adjust", "madara_uchiha": "exclude"}


def test_join_refuses_any_mismatch():
    matches = make_matches({("amazon", "sasuke_uchiha"): 60})
    sample = draw_sample(matches, seed=20261023)
    good = make_labels(sample)
    with pytest.raises(ValueError):  # unknown sample_id
        compute_precision(sample, pd.concat(
            [good, good.iloc[[0]].assign(sample_id="S9999")], ignore_index=True))
    with pytest.raises(ValueError):  # record_hash does not match the sample
        compute_precision(sample, good.assign(record_hash="0" * 40))
    with pytest.raises(ValueError):  # a sampled row has no label
        compute_precision(sample, good.iloc[1:])
    with pytest.raises(ValueError):  # unknown label value
        compute_precision(sample, good.assign(label="maybe"))
    with pytest.raises(ValueError):  # duplicate sample_id
        compute_precision(sample, pd.concat([good, good.iloc[[0]]], ignore_index=True))


def test_stop_rule_below_half(tmp_path):
    matches = make_matches({("amazon", "sasuke_uchiha"): 60, ("ebay", "gaara"): 60})
    sample = draw_sample(matches, seed=20261023)
    ebay_ids = sample[sample.source == "ebay"].sample_id.tolist()
    labels = make_labels(sample, wrong_ids=set(ebay_ids[: len(ebay_ids) // 2 + 1]))
    precision = compute_precision(sample, labels)
    assert sources_below_stop(precision) == ["ebay"]
    assert STOP_THRESHOLD == 0.50
    matches_dir = tmp_path / "matches"
    matches_dir.mkdir()
    write_matches(make_matches({("amazon", "sasuke_uchiha"): 60, ("ebay", "gaara"): 60}), matches_dir)
    # Rebuild the identical sample on disk so the run path accepts it.
    sample.to_parquet(tmp_path / "sample.parquet", index=False)
    labels.to_csv(tmp_path / "labels.csv", index=False)
    with pytest.raises(RuntimeError):  # STOP §10.3
        run(matches_dir=matches_dir, sample_path=tmp_path / "sample.parquet",
            labels_path=tmp_path / "labels.csv",
            precision_parquet=tmp_path / "precision.parquet",
            precision_csv=tmp_path / "precision.csv",
            sample_csv=tmp_path / "sample.csv",
            stop_path=tmp_path / "STOP.md")
    assert (tmp_path / "STOP.md").exists()
    assert "ebay" in (tmp_path / "STOP.md").read_text()


def test_run_writes_committed_csvs_without_snippets(tmp_path):
    matches = make_matches({("amazon", "sasuke_uchiha"): 80, ("amazon", "gaara"): 80,
                            ("ebay", "sasuke_uchiha"): 80, ("ebay", "gaara"): 80})
    matches_dir = tmp_path / "matches"
    matches_dir.mkdir()
    write_matches(matches, matches_dir)
    sample = draw_sample(matches, seed=20261023)
    sample.to_parquet(tmp_path / "sample.parquet", index=False)
    make_labels(sample).to_csv(tmp_path / "labels.csv", index=False)
    precision = run(matches_dir=matches_dir, sample_path=tmp_path / "sample.parquet",
                    labels_path=tmp_path / "labels.csv",
                    precision_parquet=tmp_path / "precision.parquet",
                    precision_csv=tmp_path / "precision.csv",
                    sample_csv=tmp_path / "sample.csv",
                    stop_path=tmp_path / "STOP.md")
    assert not (tmp_path / "STOP.md").exists()  # high precision: no stop
    assert (tmp_path / "precision.parquet").exists()
    committed = pd.read_csv(tmp_path / "sample.csv")
    assert committed.columns.tolist() == ["sample_id", "source", "character", "label"]
    assert "snippet" not in committed.columns
    assert len(committed) == len(sample)
    assert set(pd.read_csv(tmp_path / "precision.csv").columns) == set(precision.columns)
