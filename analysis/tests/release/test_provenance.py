"""Unit tests for nga.release.provenance (synthetic files only)."""
import json

from nga.release import provenance


def test_hash_files_is_order_independent(tmp_path):
    a = tmp_path / "a.parquet"
    b = tmp_path / "b.parquet"
    a.write_bytes(b"aaa")
    b.write_bytes(b"bbb")
    h1 = provenance.hash_files([("x/a", a), ("x/b", b)])
    h2 = provenance.hash_files([("x/b", b), ("x/a", a)])
    assert h1 == h2 and len(h1) == 64


def test_collect_prefers_sources_files_lists(tmp_path):
    archive = tmp_path / "archive"
    (archive / "datasets").mkdir(parents=True)
    f1 = archive / "datasets" / "one.parquet"
    f1.write_bytes(b"1")
    aux = tmp_path / "aux"
    aux.mkdir()
    (aux / "sources_t01.json").write_text(json.dumps(
        [{"id": "amazon", "records": 3, "in_score": True,
          "files": ["datasets/one.parquet"]}]))
    got = provenance.collect_input_files(aux, archive_root=archive)
    assert got == [("datasets/one.parquet", f1)]
    assert provenance.input_sha256(aux, archive_root=archive) == provenance.hash_files(got)


def test_collect_missing_file_names_it(tmp_path):
    aux = tmp_path / "aux"
    aux.mkdir()
    (aux / "sources_t01.json").write_text(json.dumps(
        [{"id": "amazon", "records": 3, "in_score": True,
          "files": ["datasets/nope.parquet"]}]))
    try:
        provenance.collect_input_files(aux, archive_root=tmp_path / "archive")
    except FileNotFoundError as e:
        assert "datasets/nope.parquet" in str(e)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_release_id_and_meta_shape():
    content = "ab" * 32
    rid = provenance.release_id_for("1.1.0", "2026-10-22", content)
    assert rid == "v1.1.0-20261022-abababab"
    meta = provenance.make_meta(generated_utc="2026-10-23T00:00:00Z",
                                snapshot="2026-10-22", commit="c" * 40, digest="d" * 64,
                                release_id=rid)
    assert meta["status"] == "validated"
    assert meta["contract_version"] == "1.2.0"
    assert meta["release_id"] == "v1.1.0-20261022-abababab"
    assert meta["youtube_snapshot"] == "2026-10-22"
    assert all(len(n) <= 120 for n in meta["notes"])  # privacy-guard safe


def test_release_id_defaults_to_blank_until_build_fills_it():
    meta = provenance.make_meta(generated_utc="2026-10-23T00:00:00Z",
                                snapshot="2026-10-22", commit="c" * 40, digest="d" * 64)
    assert meta["release_id"] == ""
