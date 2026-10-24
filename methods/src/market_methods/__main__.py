"""Run the offline methods demo using local JSON files."""

import argparse
import json
from pathlib import Path

from .engine import build_report, canonical_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--quality", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_report(json.loads(args.metrics.read_text()), json.loads(args.config.read_text()),
                              json.loads(args.quality.read_text()) if args.quality else [])
    except (ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical_bytes(report))
    print(f"{args.out}: {report['data_kind']}, release {report['release_id']}")


if __name__ == "__main__":
    main()
