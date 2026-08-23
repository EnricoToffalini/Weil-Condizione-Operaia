#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from condition_ouvriere.validation import validate_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida corpus, manifest e snapshot")
    parser.add_argument("--root", type=Path, help="radice alternativa del corpus")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else Path(__file__).resolve().parents[1]
    errors = validate_corpus(root)
    if errors:
        print("Validazione fallita:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Validazione riuscita: 16 unità, tutte di Simone Weil.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
