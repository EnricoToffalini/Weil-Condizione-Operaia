from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from .catalog import EXPECTED_UNIT_COUNT, UNITS
from .util import load_json, load_yaml, sha256_file
from .wikisource import validate_index_snapshot


def validate_corpus(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "corpus" / "manifest.yml"
    if not manifest_path.exists():
        return ["corpus/manifest.yml mancante"]
    try:
        manifest = load_yaml(manifest_path)
    except (UnicodeDecodeError, ValueError) as exc:
        return [f"manifest non leggibile come UTF-8/YAML: {exc}"]

    units = manifest.get("units", [])
    if manifest.get("expected_unit_count") != EXPECTED_UNIT_COUNT or len(units) != EXPECTED_UNIT_COUNT:
        errors.append(f"numero unità: attese {EXPECTED_UNIT_COUNT}, trovate {len(units)}")

    ids = [item.get("id") for item in units]
    if len(ids) != len(set(ids)):
        errors.append("ID duplicati nel manifest")
    orders = [item.get("order") for item in units]
    if orders != [unit.source_order for unit in UNITS]:
        errors.append(f"ordine non coerente: {orders}")

    expected_paths = {unit.local_file for unit in UNITS}
    manifest_paths = {item.get("local_file") for item in units}
    if manifest_paths != expected_paths:
        errors.append("i percorsi del manifest non coincidono con il catalogo dell’edizione")

    for item in units:
        relative = item.get("local_file")
        if not relative:
            errors.append(f"local_file assente per {item.get('id')}")
            continue
        path = root / relative
        if not path.exists():
            errors.append(f"file mancante: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"encoding non UTF-8: {relative}: {exc}")
            continue
        if not text.strip():
            errors.append(f"file vuoto: {relative}")
        if not re.search(r"^#{1,6}\s+\S", text, re.MULTILINE):
            errors.append(f"titolo Markdown principale assente: {relative}")
        if not text.startswith("---\n") or f"title_fr: {item.get('title_fr')}" not in text.split("---", 2)[1]:
            errors.append(f"titolo/provenienza front matter incoerente: {relative}")
        if sha256_file(path) != item.get("sha256"):
            errors.append(f"checksum non valido: {relative}")
        url = item.get("source_url", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.netloc != "fr.wikisource.org":
            errors.append(f"URL sorgente assente o non canonico: {item.get('id')}")
        if not item.get("revision_id") or not item.get("revision_timestamp"):
            errors.append(f"provenienza di revisione incompleta: {item.get('id')}")
        snapshot_path = root / "source" / "snapshots" / f"{item.get('order', 0):02d}.json"
        if not snapshot_path.exists():
            errors.append(f"snapshot unità mancante: {item.get('id')}")
        elif sha256_file(snapshot_path) != item.get("snapshot_sha256"):
            errors.append(f"checksum snapshot non valido: {item.get('id')}")

    found_md = {
        path.relative_to(root).as_posix()
        for directory in (root / "corpus" / "fr",)
        if directory.exists()
        for path in directory.glob("*.md")
    }
    extras = found_md - expected_paths
    if extras:
        errors.append(f"file Markdown non dichiarati nel manifest: {sorted(extras)}")

    index_path = root / "source" / "snapshots" / "index.json"
    if not index_path.exists():
        errors.append("snapshot dell’indice mancante")
    else:
        try:
            validate_index_snapshot(load_json(index_path))
        except Exception as exc:  # report a validation failure, not a traceback
            errors.append(f"indice Wikisource incoerente: {exc}")
        if sha256_file(index_path) != manifest.get("canonical_source", {}).get("snapshot_sha256"):
            errors.append("checksum dello snapshot indice non valido")

    return errors
