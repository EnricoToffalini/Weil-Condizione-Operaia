from pathlib import Path

from condition_ouvriere.wikisource import _local_integrity_errors


ROOT = Path(__file__).resolve().parents[1]


def test_committed_corpus_has_no_unregistered_local_edits() -> None:
    assert _local_integrity_errors(ROOT) == []

