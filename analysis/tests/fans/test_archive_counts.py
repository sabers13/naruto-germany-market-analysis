"""Archive count checks for the fans lane (aggregate counts only, no row content)."""
import duckdb
import pytest

from nga import paths

archive_present = pytest.mark.skipif(not paths.archive().exists(),
                                     reason="data archive not on disk")


@pytest.mark.archive
@archive_present
def test_deduped_comment_total_within_one_percent():
    con = duckdb.connect()
    n = con.execute(
        "SELECT COUNT(DISTINCT comment_id) FROM read_parquet(?)",
        [str(paths.dataset("youtube", "raw", "parquet",
                            "naruto-de-youtube-v1__comments.parquet"))],
    ).fetchone()[0]
    assert abs(n - 142203) / 142203 <= 0.01, n
