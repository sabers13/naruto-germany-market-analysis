"""CLI: uv run python -m nga.accuracy sample|packet|score."""
from __future__ import annotations

import argparse

from .packet import run as run_packet
from .precision import run as run_score
from .sample import run as run_sample


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m nga.accuracy")
    parser.add_argument("command", choices=("sample", "packet", "score"))
    args = parser.parse_args(argv)
    if args.command == "sample":
        sample = run_sample()
        print(f"sampled {len(sample)} rows")
    elif args.command == "packet":
        sample = run_packet()
        print(f"packet for {len(sample)} items")
    else:
        precision = run_score()
        print(precision.to_string(index=False))


if __name__ == "__main__":
    main()
