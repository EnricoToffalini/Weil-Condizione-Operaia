"""Curated structural metadata transcribed from the 1951 Wikisource index."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UnitSpec:
    source_order: int
    title_fr: str
    slug: str
    author: str
    date: str | None
    content_type: str
    is_simone_weil: bool
    editorial_notes: str | None = None

    @property
    def id(self) -> str:
        return f"co-1951-{self.source_order:02d}"

    @property
    def wikisource_page(self) -> str:
        return f"La Condition ouvrière/{self.source_order:02d}"

    @property
    def filename(self) -> str:
        return f"{self.source_order:02d}_{self.slug}.md"

    @property
    def local_file(self) -> str:
        return f"corpus/fr/{self.filename}"


UNITS: tuple[UnitSpec, ...] = (
    UnitSpec(2, "Trois lettres à Mme Albertine Thévenon (1934-1935)", "trois_lettres_a_albertine_thevenon", "Simone Weil", "1934-1935", "correspondence", True),
    UnitSpec(3, "Lettre à une élève (1934)", "lettre_a_une_eleve", "Simone Weil", "1934", "correspondence", True),
    UnitSpec(
        4,
        "Lettre à Boris Souvarine (1935)",
        "lettre_a_boris_souvarine",
        "Simone Weil",
        "1935",
        "correspondence",
        True,
        "L’header Wikisource rende l’intervallo come « p. 29-- »; page_end=31 è ricavato dai marcatori di pagina stampata 29-31 presenti nel contenuto.",
    ),
    UnitSpec(5, "Fragment de lettre à X. (1933-1934 ?)", "fragment_de_lettre_a_x", "Simone Weil", "1933-1934 ?", "correspondence-fragment", True),
    UnitSpec(6, "Journal d’Usine (1934-1935)", "journal_d_usine", "Simone Weil", "1934-1935", "journal", True),
    UnitSpec(7, "Fragments", "fragments", "Simone Weil", None, "fragments", True),
    UnitSpec(8, "Lettres à un ingénieur directeur d’usine (Bourges, janvier-juin 1936)", "lettres_a_un_ingenieur_directeur_d_usine", "Simone Weil", "janvier-juin 1936", "correspondence", True),
    UnitSpec(9, "La vie et la grève des ouvrières métallos (Sur le tas) (10 juin 1936)", "la_vie_et_la_greve_des_ouvrieres_metallos", "Simone Weil", "10 juin 1936", "article", True),
    UnitSpec(10, "Lettre ouverte à un Syndiqué (après juin 1936)", "lettre_ouverte_a_un_syndique", "Simone Weil", "après juin 1936", "open-letter", True),
    UnitSpec(11, "Lettres à Auguste Detœuf (1936-1937)", "lettres_a_auguste_detoeuf", "Simone Weil", "1936-1937", "correspondence", True),
    UnitSpec(12, "Remarques sur les enseignements à tirer des conflits du Nord (1936-1937 ?)", "remarques_sur_les_conflits_du_nord", "Simone Weil", "1936-1937 ?", "article", True),
    UnitSpec(13, "Principes d’un projet pour un régime intérieur nouveau dans les entreprises industrielles (1936-1937 ?)", "principes_d_un_projet_de_regime_interieur", "Simone Weil", "1936-1937 ?", "proposal", True),
    UnitSpec(14, "La rationalisation (23 février 1937)", "la_rationalisation", "Simone Weil", "23 février 1937", "lecture", True),
    UnitSpec(15, "La condition ouvrière (30 septembre 1937)", "la_condition_ouvriere", "Simone Weil", "30 septembre 1937", "article", True),
    UnitSpec(16, "Expérience de la vie d’usine (Marseille, 1941-1942)", "experience_de_la_vie_d_usine", "Simone Weil", "1941-1942", "essay", True),
    UnitSpec(17, "Condition première d’un travail non servile (Marseille, 1941-1942)", "condition_premiere_d_un_travail_non_servile", "Simone Weil", "1941-1942", "essay", True),
)

EXPECTED_UNIT_COUNT = len(UNITS)
SOURCE_INDEX_ORDERS = tuple(range(1, 18))
EXPECTED_INDEX_UNIT_COUNT = len(SOURCE_INDEX_ORDERS)
