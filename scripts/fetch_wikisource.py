#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from condition_ouvriere.wikisource import AcquisitionError, fetch_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquisisce La Condition ouvrière tramite MediaWiki API")
    parser.add_argument(
        "--update",
        action="store_true",
        help="applica esplicitamente una differenza upstream, solo se il corpus locale coincide con i checksum",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="ricostruisce in una directory vuota senza modificare il corpus canonico",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        print(fetch_corpus(root, update=args.update, output_dir=args.output_dir))
    except AcquisitionError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
