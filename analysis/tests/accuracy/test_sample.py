"""Tests for the stratified sampler. Synthetic matches only."""
import pandas as pd

from nga.accuracy import SEED
from nga.accuracy.sample import draw_sample, load_matches, run, top5_candidates

from conftest import SOURCES, make_matches, write_matches

EXPECTED_TOP5 = ["sasuke_uchiha", "itachi_uchiha", "kakashi_hatake", "gaara", "madara_uchiha"]


def test_top5_excludes_benchmark_and_is_deterministic(ample_matches):
    assert top5_candidates(ample_matches) == EXPECTED_TOP5


def test_stratum_sizes_per_source(ample_matches):
    sample = draw_sample(ample_matches, seed=SEED)
    assert len(sample) == 5 * (40 + 15 + 15 + 5 * 10)  # 600 gross, pools ample
    for source in SOURCES:
        sub = sample[sample.source == source]
        assert len(sub) == 120, source
        assert (sub.stratum == "random").sum() == 40, source
        assert (sub.stratum == "hinata_hyuga").sum() == 15, source
        assert (sub.stratum == "nagato_pain").sum() == 15, source
        for char in EXPECTED_TOP5:
            assert ((sub.stratum == f"top5:{char}") & (sub.character_key == char)).sum() == 10, (source, char)


def test_no_duplicates_and_stable_ids(ample_matches):
    sample = draw_sample(ample_matches, seed=SEED)
    assert not sample.duplicated(["record_hash", "character_key"]).any()
    assert sample.sample_id.is_unique
    assert sample.sample_id.tolist() == [f"S{n:04d}" for n in range(1, len(sample) + 1)]


def test_seed_determinism(ample_matches):
    first = draw_sample(ample_matches, seed=SEED)
    second = draw_sample(ample_matches, seed=SEED)
    pd.testing.assert_frame_equal(first, second)


def test_small_stratum_takes_everything_available():
    counts = {("amazon", "hinata_hyuga"): 3, ("amazon", "sasuke_uchiha"): 100,
              ("ebay", "sasuke_uchiha"): 100}
    sample = draw_sample(make_matches(counts), seed=SEED)
    amazon = sample[sample.source == "amazon"]
    assert (amazon.stratum == "random").sum() == 40
    # Quota is 15 but only 3 hinata rows exist: every one of them is sampled,
    # split across the random and hinata strata.
    assert (amazon.character_key == "hinata_hyuga").sum() == 3


def test_load_matches_reads_only_keyword_sources(tmp_path):
    df = make_matches({("amazon", "sasuke_uchiha"): 5, ("wikimedia", "sasuke_uchiha"): 5})
    write_matches(df, tmp_path)
    loaded = load_matches(tmp_path)
    assert set(loaded.source.unique()) == {"amazon"}  # wikimedia is not keyword-matched


def test_run_writes_sample_parquet(tmp_path, ample_matches):
    matches_dir = tmp_path / "matches"
    matches_dir.mkdir()
    write_matches(ample_matches, matches_dir)
    out = tmp_path / "accuracy" / "sample.parquet"
    sample = run(matches_dir=matches_dir, out_path=out)
    assert out.exists()
    back = pd.read_parquet(out)
    pd.testing.assert_frame_equal(back, sample)
    assert {"sample_id", "stratum", "record_hash", "source",
            "character_key", "matched_on", "snippet"} <= set(back.columns)
