"""CLI: uv run python -m nga.fans — runs the full the fans lane fans-text lane."""
from __future__ import annotations

import json

import pandas as pd

from nga import characters, metrics, paths
from nga.fans import anime2you, youtube

LANE = "fans"


def _rows(counts: dict[str, int], source: str, metric: str, primary: bool) -> list[dict]:
    return [{
        "character_key": key,
        "source": source,
        "metric": metric,
        "period": "snapshot",
        "region": "DE",
        "value": float(counts.get(key, 0)),
        "n": int(counts.get(key, 0)),
        "unit": "count",
        "evidence_class": "B",
        "lens": "watching",
        "primary": primary,
        "lane": LANE,
    } for key in characters.keys()]


def main() -> None:
    paths.check_archive()
    yt = youtube.run()
    a2y = anime2you.run()

    df = pd.DataFrame(
        _rows(yt["comment_counts"], "youtube", "comments_de", True)
        + _rows(yt["solo_counts"], "youtube", "comments_de_solo", False)
        + _rows(yt["video_counts"], "youtube", "videos_de", False)
        + _rows(a2y["comment_counts"], "anime2you", "comment_mentions", True)
        + _rows(a2y["solo_counts"], "anime2you", "comment_mentions_solo", False)
        + _rows(a2y["article_counts"], "anime2you", "articles", False)
    )
    metrics.write(df, LANE)

    kpis = {
        "youtube_comments_de": yt["comments_de"],
        "youtube_comments_total": yt["total_comments"],
        "anime2you_articles": a2y["total_posts"],
    }
    paths.work("aux", "kpis_fans.json").write_text(json.dumps(kpis, indent=2) + "\n")
    sources = [
        {"id": "youtube", "records": yt["total_comments"] + yt["total_videos"], "in_score": True},
        {"id": "anime2you", "records": a2y["total_comments"] + a2y["total_posts"],
         "in_score": True},
    ]
    paths.work("aux", "sources_fans.json").write_text(json.dumps(sources, indent=2) + "\n")

    print(f"the fans lane done: youtube comments_de={yt['comments_de']} "
          f"videos_de={yt['videos_de']} match_rows={yt['match_rows']}; "
          f"anime2you comments={a2y['total_comments']} "
          f"posts={a2y['total_posts']} match_rows={a2y['match_rows']}")


if __name__ == "__main__":
    main()
