from condition_ouvriere.catalog import EXPECTED_INDEX_UNIT_COUNT, EXPECTED_UNIT_COUNT, UNITS


def test_catalog_matches_numbered_wikisource_subpages() -> None:
    assert EXPECTED_UNIT_COUNT == 16
    assert EXPECTED_INDEX_UNIT_COUNT == 17
    assert [unit.source_order for unit in UNITS] == list(range(2, 18))
    assert [unit.wikisource_page for unit in UNITS] == [
        f"La Condition ouvrière/{number:02d}" for number in range(2, 18)
    ]
    assert len({unit.id for unit in UNITS}) == 16
    assert len({unit.local_file for unit in UNITS}) == 16


def test_only_simone_weil_material_is_included() -> None:
    assert all(unit.is_simone_weil for unit in UNITS)
    assert all(unit.author == "Simone Weil" for unit in UNITS)
    assert all(unit.local_file.startswith("corpus/fr/") for unit in UNITS)
