#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from condition_ouvriere.util import dump_yaml, load_yaml
from condition_ouvriere.wikisource import build_manifest_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Ricostruisce il manifest da snapshot e file canonici")
    parser.add_argument("--check", action="store_true", help="verifica senza modificare il manifest")
    parser.add_argument("--root", type=Path, help="radice alternativa del corpus")
    args = parser.parse_args()
    root = args.root.resolve() if args.root else Path(__file__).resolve().parents[1]
    path = root / "corpus" / "manifest.yml"
    data = build_manifest_data(root)
    rendered = dump_yaml(data)
    if args.check:
        if not path.exists() or load_yaml(path) != data:
            print("Manifest non aggiornato")
            return 1
        print("Manifest aggiornato")
        return 0
    path.write_bytes(rendered)
    print(f"Scritto {path.relative_to(root)} con {len(data['units'])} unità")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
