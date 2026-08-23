from pathlib import Path

import yaml

from condition_ouvriere.catalog import UNITS
from condition_ouvriere.util import load_json, load_yaml
from condition_ouvriere.validation import validate_corpus
from condition_ouvriere.wikisource import extract_page_range, render_markdown


ROOT = Path(__file__).resolve().parents[1]


def test_corpus_passes_full_validation() -> None:
    assert validate_corpus(ROOT) == []


def test_manifest_counts_and_classification() -> None:
    manifest = load_yaml(ROOT / "corpus" / "manifest.yml")
    assert manifest["expected_unit_count"] == 16
    assert manifest["weil_unit_count"] == 16
    assert manifest["editorial_unit_count"] == 0
    assert sum(item["is_simone_weil"] for item in manifest["units"]) == 16


def test_each_markdown_file_has_matching_frontmatter() -> None:
    for unit in UNITS:
        text = (ROOT / unit.local_file).read_text(encoding="utf-8")
        _, raw_frontmatter, body = text.split("---", 2)
        frontmatter = yaml.safe_load(raw_frontmatter)
        assert frontmatter["id"] == unit.id
        assert frontmatter["title_fr"] == unit.title_fr
        assert frontmatter["author"] == unit.author
        assert frontmatter["wikisource_page"] == unit.wikisource_page
        assert body.lstrip().startswith(("<a id=", "#"))


def test_rendering_is_reproducible_from_snapshots() -> None:
    for unit in UNITS:
        snapshot = load_json(ROOT / "source" / "snapshots" / f"{unit.source_order:02d}.json")
        expected = (ROOT / unit.local_file).read_text(encoding="utf-8")
        assert render_markdown(snapshot, unit) == expected


def test_malformed_wikisource_page_end_has_traceable_fallback() -> None:
    snapshot = load_json(ROOT / "source" / "snapshots" / "04.json")
    assert extract_page_range(snapshot) == (29, 31)
    manifest = load_yaml(ROOT / "corpus" / "manifest.yml")
    unit = next(item for item in manifest["units"] if item["order"] == 4)
    assert unit["page_end"] == 31
    assert "29--" in unit["editorial_notes"]

