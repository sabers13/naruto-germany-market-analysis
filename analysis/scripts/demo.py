"""Build a full and a public release from the synthetic test inputs.

No data archive, credentials or network needed. Every number comes from
tests/release/synth.py, so the output demonstrates the pipeline, not the study.

    uv run python scripts/demo.py [output-dir]
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from release.synth import add_kleinanzeigen, make_aux, make_result  # noqa: E402

from nga.release import build, write_release  # noqa: E402
from nga.release.public import public_edition  # noqa: E402


def main(out_dir: str | None = None) -> None:
    out = Path(out_dir or tempfile.mkdtemp(prefix="nga-demo-"))
    with tempfile.TemporaryDirectory() as tmp:
        aux = Path(tmp) / "aux"
        make_aux(aux, ROOT / "config" / "states.yaml")
        add_kleinanzeigen(aux)
        doc = build(make_result(), aux, generated_utc="2026-10-23T00:00:00Z",
                    snapshot_date="2026-10-22", archive_commit="0" * 40,
                    input_sha256="0" * 64)
    full = write_release(doc, out)
    pub = write_release(public_edition(doc), out, name="dashboard.public")
    ranked = sorted((c for c in doc["characters"] if c["rank"] is not None),
                    key=lambda c: c["rank"])[:3]
    print("top 3 (synthetic):", ", ".join(f"{c['key']} ({c['index']})" for c in ranked))
    print("full:  ", full)
    print("public:", pub)


if __name__ == "__main__":
    main(*sys.argv[1:2])
