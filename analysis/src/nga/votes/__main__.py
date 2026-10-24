"""Run the votes lane end to end: metrics, events, kpis, sources."""
from __future__ import annotations

import json

import pandas as pd

from nga import metrics
from nga.paths import check_archive, work

from . import context, events, narutop99


def main() -> None:
    check_archive()
    votes = narutop99.run()
    wiki, wiki_rows = context.wikimedia_run()
    all_metrics = pd.concat([votes, wiki], ignore_index=True)
    metrics.write(all_metrics, "votes")

    events_doc = events.build_events()
    work("aux", "events.json").write_text(
        json.dumps(events_doc, indent=2, ensure_ascii=False) + "\n")

    n_europe = narutop99.europe_row_count()
    work("aux", "sources_votes.json").write_text(json.dumps([
        {"id": "narutop99", "records": n_europe, "in_score": True},
        {"id": "wikimedia", "records": wiki_rows, "in_score": False},
    ], indent=2) + "\n")
    work("aux", "kpis_votes.json").write_text(json.dumps({}, indent=2) + "\n")

    prim = all_metrics[all_metrics["primary"]]
    print(prim.pivot_table(index="character_key", columns="source",
                           values="value", aggfunc="first").to_string())
    print(f"wikimedia_rows_12m={wiki_rows} narutop99_europe={n_europe}")
    print(f"events={len(events_doc)}")


if __name__ == "__main__":
    main()
