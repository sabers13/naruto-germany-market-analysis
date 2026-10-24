"""Labelling packet for the accuracy check (ANALYSIS_PLAN.md §6.3).

Writes work/accuracy/packet.md (instructions + one block per sampled item)
for a labeller model from a different family than the lane author, plus an
empty work/accuracy/labels_template.csv (sample_id,label,note).

Snippets stay in work/ (gitignored) and never reach reports/ or git.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from nga.paths import work

from . import LABELS

TEMPLATE_COLUMNS = ("sample_id", "label", "note")

INSTRUCTIONS = """# Accuracy labelling packet

You are checking keyword matches that link shop / fan-text records to Naruto
characters. For each item you see `sample_id`, the keyword `source`, the
`claimed character`, and a short text `snippet` (<= 200 chars) around the match.

Reply with one CSV row per item: `sample_id,label,note`.

## Labels (exactly one of)

- `correct` — the snippet really refers to the claimed Naruto character.
  Example: claimed `sasuke_uchiha`, snippet mentions a Sasuke Uchiha figure.
- `wrong_character` — the snippet refers to Naruto content, but a different
  character than claimed.
  Example: claimed `nagato_pain`, snippet is about a painful injury ("pain")
  with no Naruto character in it — actually this is `not_naruto`; a
  `wrong_character` example is claimed `minato_namikaze`, snippet about
  Minato's student Kakashi with no Minato reference.
- `not_naruto` — the snippet has nothing to do with Naruto.
  Example: claimed `hinata_hyuga`, snippet about volleyball player Shoyo Hinata.
- `unclear` — cannot tell from the snippet (counts as wrong, so use it only
  when truly undecidable).
  Example: snippet is a truncated fragment with no identifiable subject.

## Rules

- Judge only what the snippet shows; never use outside knowledge about the record.
- `note` must describe the error type WITHOUT quoting or paraphrasing the
  snippet text (notes are committed; snippets never leave work/).
"""


def render_packet(sample_df: pd.DataFrame) -> str:
    """Render the full packet markdown for the sampled items (ordered by sample_id)."""
    lines = [INSTRUCTIONS.rstrip(), "", f"## Items ({len(sample_df)} in total)", ""]
    for _, row in sample_df.sort_values("sample_id").iterrows():
        lines += [
            f"### {row['sample_id']}",
            f"- source: {row['source']}",
            f"- claimed character: {row['character_key']}",
            f"- matched on: {row['matched_on']}",
            f"- snippet: {row['snippet']}",
            "",
        ]
    return "\n".join(lines)


def write_packet(sample_df: pd.DataFrame, packet_path: Path,
                 template_path: Path) -> None:
    """Write packet.md and the empty labels template CSV."""
    required = {"sample_id", "source", "character_key", "matched_on", "snippet"}
    missing = required - set(sample_df.columns)
    if missing:
        raise ValueError(f"sample is missing columns: {sorted(missing)}")
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(render_packet(sample_df))
    template = pd.DataFrame(columns=list(TEMPLATE_COLUMNS))
    template.to_csv(template_path, index=False)


def run(sample_path: Path | None = None, packet_path: Path | None = None,
        template_path: Path | None = None) -> pd.DataFrame:
    """Read sample.parquet, write packet.md + labels_template.csv, return sample."""
    sample_file = Path(sample_path) if sample_path is not None else work("accuracy", "sample.parquet")
    if not sample_file.exists():
        raise FileNotFoundError(f"no sample at {sample_file}; run the sample step first")
    sample_df = pd.read_parquet(sample_file)
    packet = Path(packet_path) if packet_path is not None else work("accuracy", "packet.md")
    template = Path(template_path) if template_path is not None else work("accuracy", "labels_template.csv")
    write_packet(sample_df, packet, template)
    return sample_df


assert set(LABELS) == {"correct", "wrong_character", "not_naruto", "unclear"}
