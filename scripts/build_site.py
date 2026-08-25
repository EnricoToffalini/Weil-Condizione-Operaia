#!/usr/bin/env python
"""Genera i sorgenti Quarto del sito italiano a partire da `corpus/it/`.

Il corpus resta la sola fonte autorevole: questo script non lo modifica mai.
Per ogni testo italiano produce un capitolo `site/testi/NN-slug.qmd` in cui:

* il titolo passa dal front matter (`title_it`) all'intestazione YAML del
  capitolo, così il titolo in maiuscolo del corpus non viene ripetuto;
* la nota che nell'edizione del 1951 è agganciata al titolo diventa un
  cappello introduttivo, perché una nota a piè di pagina appesa al titolo non
  è rappresentabile nell'intestazione YAML;
* i titoletti già presenti nel corpus vengono portati al livello richiesto da
  `site/sezioni.yml`;
* nei testi lunghi e privi di articolazione vengono inseriti i titoli
  editoriali descritti in `site/sezioni.yml`, marcati dalla classe `.sez-ed`.

Uso:

    python scripts/build_site.py            # rigenera site/testi/
    python scripts/build_site.py --check    # verifica soltanto, senza scrivere
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parent.parent
CORPUS = RADICE / "corpus" / "it"
MANIFEST = RADICE / "corpus" / "manifest.yml"
SITO = RADICE / "site"
USCITA = SITO / "testi"
CONFIG = SITO / "sezioni.yml"

RIGA_TITOLO = re.compile(r"^#\s+(?P<testo>.+?)\s*$")
TITOLETTO = re.compile(r"^(?P<cancelletti>#{2,6})\s+(?P<testo>.+?)\s*$")
RIFERIMENTO_NOTA = re.compile(r"\[\^([^\]]+)\]")
DEFINIZIONE_NOTA = re.compile(r"^\[\^([^\]]+)\]:\s*(?P<testo>.*)$")
SEPARATORE = re.compile(r"^(?:---|⁂)\s*$")
URL_SENZA_SCHEMA = re.compile(r"\]\(//")
ANCORA = re.compile(r'<a id="p(\d+)"></a>')
ANCORA_ISOLATA = re.compile(r'^(?:<a id="p\d+"></a>|<!--.*?-->|\s)+$')


class ErroreDiStruttura(RuntimeError):
    """Il corpus e la configurazione editoriale non coincidono più."""


# ---------------------------------------------------------------------------
# lettura


def carica_configurazione() -> dict:
    if not CONFIG.exists():
        return {}
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def carica_manifest() -> dict:
    dati = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    return {unita["id"]: unita for unita in dati.get("units", [])}


def dividi_front_matter(testo: str) -> tuple[dict, list[str]]:
    righe = testo.split("\n")
    if righe and righe[0].strip() == "---":
        for indice in range(1, len(righe)):
            if righe[indice].strip() == "---":
                intestazione = yaml.safe_load("\n".join(righe[1:indice])) or {}
                return intestazione, righe[indice + 1:]
    return {}, righe


# ---------------------------------------------------------------------------
# trasformazioni


def estrai_titolo(righe: list[str]) -> tuple[str | None, list[str]]:
    """Toglie dal corpo il titolo di primo livello e lo restituisce."""
    for indice, riga in enumerate(righe):
        trovato = RIGA_TITOLO.match(riga)
        if trovato:
            return trovato.group("testo"), righe[:indice] + righe[indice + 1:]
    return None, righe


def stacca_note(righe: list[str], etichette: list[str]) -> tuple[list[str], list[str]]:
    """Rimuove le definizioni delle note indicate e ne restituisce il testo."""
    testi: list[str] = []
    risultato: list[str] = []
    indice = 0
    while indice < len(righe):
        trovato = DEFINIZIONE_NOTA.match(righe[indice])
        if trovato and trovato.group(1) in etichette:
            pezzi = [trovato.group("testo").strip()]
            indice += 1
            while indice < len(righe) and righe[indice].strip():
                pezzi.append(righe[indice].strip())
                indice += 1
            testi.append(" ".join(pezzi).strip())
            while indice < len(righe) and not righe[indice].strip():
                indice += 1
            continue
        risultato.append(righe[indice])
        indice += 1
    return testi, risultato


def indice_del_prefisso(righe: list[str], prefisso: str, occorrenza: int | None) -> int:
    trovati = [i for i, riga in enumerate(righe) if riga.startswith(prefisso)]
    if not trovati:
        raise ErroreDiStruttura(f"nessun paragrafo comincia con {prefisso!r}")
    if occorrenza is None:
        if len(trovati) > 1:
            raise ErroreDiStruttura(
                f"il prefisso {prefisso!r} compare {len(trovati)} volte: "
                "indicare `occorrenza` in site/sezioni.yml"
            )
        return trovati[0]
    if occorrenza > len(trovati):
        raise ErroreDiStruttura(
            f"il prefisso {prefisso!r} compare solo {len(trovati)} volte"
        )
    return trovati[occorrenza - 1]


def inserisci_titolo(righe: list[str], posizione: int, titolo: str) -> None:
    """Inserisce un titolo editoriale assorbendo lo stacco che lo precede.

    Quando il punto di inserimento è preceduto da una riga di stacco (`---`
    oppure l'asterismo), la riga viene tolta: è il titolo, ora, a segnare la
    divisione.
    """
    inizio = posizione
    indietro = posizione - 1
    while indietro >= 0 and not righe[indietro].strip():
        indietro -= 1
    if indietro >= 0 and SEPARATORE.match(righe[indietro]):
        del righe[indietro:posizione]
        inizio = indietro
    righe[inizio:inizio] = [f"## {titolo} {{.sez-ed}}", ""]


def primo_contenuto(righe: list[str], da: int, a: int) -> int:
    for indice in range(da, a):
        if righe[indice].strip():
            return indice
    return da


def e_coda_di_note(righe: list[str], intervallo: tuple[int, int]) -> bool:
    """Vero se il blocco contiene soltanto definizioni di note a piè di pagina."""
    inizio, fine = intervallo
    contenuto = [r for r in righe[inizio:fine] if r.strip()]
    if not contenuto:
        return False
    return DEFINIZIONE_NOTA.match(contenuto[0]) is not None


def applica_blocchi(righe: list[str], titoli: list) -> list[str]:
    """Titola i blocchi separati da `---`: le lettere raccolte in un solo testo."""
    stacchi = [i for i, riga in enumerate(righe) if riga.strip() == "---"]
    limiti = [-1, *stacchi, len(righe)]
    blocchi = [(limiti[i] + 1, limiti[i + 1]) for i in range(len(limiti) - 1)]
    corpo = [b for b in blocchi if not e_coda_di_note(righe, b)]
    if len(corpo) != len(titoli):
        raise ErroreDiStruttura(
            f"il testo ha {len(corpo)} blocchi separati da `---`, "
            f"ma site/sezioni.yml ne titola {len(titoli)}"
        )
    for (inizio, fine), titolo in reversed(list(zip(corpo, titoli))):
        if titolo is None:
            continue
        inserisci_titolo(righe, primo_contenuto(righe, inizio, fine), titolo)
    return righe


def applica_sezioni(righe: list[str], sezioni: list[dict]) -> list[str]:
    posizioni = [
        (
            indice_del_prefisso(righe, sezione["prima_di"], sezione.get("occorrenza")),
            sezione["titolo"],
        )
        for sezione in sezioni
    ]
    for posizione, titolo in sorted(posizioni, reverse=True):
        inserisci_titolo(righe, posizione, titolo)
    return righe


def livella_titoletti(righe: list[str], impostazioni: dict) -> list[str]:
    """Porta i titoletti del corpus al livello voluto, senza toccarne il testo."""
    predefinito = int(impostazioni.get("livello_titoli_originali", 2))
    promuovi = impostazioni.get("promuovi") or []
    subordina = impostazioni.get("subordina") or []
    risultato = []
    for riga in righe:
        trovato = TITOLETTO.match(riga)
        if not trovato:
            risultato.append(riga)
            continue
        testo = trovato.group("testo")
        if testo.endswith("{.sez-ed}"):  # titolo editoriale appena inserito
            risultato.append(riga)
            continue
        nudo = re.sub(r"[*_]", "", testo).strip()
        livello = predefinito
        if any(nudo.startswith(p) for p in promuovi):
            livello = 2
        elif any(nudo.startswith(p) for p in subordina):
            livello = 3
        risultato.append("#" * livello + " " + testo)
    return risultato


def normalizza(righe: list[str]) -> list[str]:
    """Ritocchi minimi di resa, senza toccare il testo.

    Completa gli URL relativi al protocollo lasciati da Wikisource e converte
    in blocco le ancore di pagina che stanno da sole su una riga: come
    elementi in linea diventerebbero un paragrafo vuoto, che aprirebbe uno
    stacco bianco nel testo.
    """
    risultato = []
    for riga in righe:
        riga = URL_SENZA_SCHEMA.sub("](https://", riga)
        if riga.strip() and ANCORA_ISOLATA.match(riga):
            riga = ANCORA.sub(r'<div id="p\1" class="ancora-pagina"></div>', riga)
        risultato.append(riga)
    return risultato


def distingui_note(righe: list[str], prefisso: str) -> list[str]:
    """Antepone il numero del testo alle etichette delle note a piè di pagina.

    Nel PDF i capitoli confluiscono in un solo documento Pandoc: le note
    numerate da 1 in ogni testo si sovrapporrebbero, e delle etichette ripetute
    Pandoc tiene solo la prima definizione (segnalando «duplicate note
    reference»). Le etichette non compaiono nel testo reso — la numerazione
    delle note la rifà Pandoc, capitolo per capitolo — quindi il prefisso resta
    invisibile al lettore, nel sito come nel libro.
    """
    return [
        RIFERIMENTO_NOTA.sub(lambda t: f"[^{prefisso}-{t.group(1)}]", riga)
        for riga in righe
    ]


def ripulisci_righe_vuote(righe: list[str]) -> list[str]:
    risultato: list[str] = []
    for riga in righe:
        if not riga.strip() and risultato and not risultato[-1].strip():
            continue
        risultato.append(riga)
    while risultato and not risultato[0].strip():
        risultato.pop(0)
    while risultato and not risultato[-1].strip():
        risultato.pop()
    return risultato


# ---------------------------------------------------------------------------
# scrittura


def cita_yaml(valore: str) -> str:
    return '"' + valore.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sigla(titolo: str, lunghezza_massima: int = 60) -> str:
    """Ricava dal titolo italiano una parte di URL leggibile."""
    piano = re.sub(r"\([^)]*\)", " ", titolo)
    piano = piano.replace("’", "-").replace("'", "-")
    piano = piano.replace("œ", "oe").replace("Œ", "Oe")
    piano = piano.replace("æ", "ae").replace("Æ", "Ae")
    piano = unicodedata.normalize("NFKD", piano)
    piano = piano.encode("ascii", "ignore").decode("ascii").lower()
    piano = re.sub(r"[^a-z0-9]+", "-", piano).strip("-")
    if len(piano) > lunghezza_massima:
        tagliato = piano[:lunghezza_massima]
        piano = tagliato.rpartition("-")[0] or tagliato
    return piano


def numero_del_testo(sorgente: Path) -> str:
    return sorgente.stem.partition("_")[0]


def nome_di_uscita(sorgente: Path, titolo: str, impostazioni: dict) -> str:
    parte = impostazioni.get("sigla") or sigla(titolo)
    return f"{numero_del_testo(sorgente)}-{parte}.qmd"


def componi(sorgente: Path, impostazioni: dict, manifest: dict) -> tuple[str, str]:
    intestazione, righe = dividi_front_matter(sorgente.read_text(encoding="utf-8-sig"))
    titolo_originale, righe = estrai_titolo(righe)
    titolo = intestazione.get("title_it") or titolo_originale or sorgente.stem

    cappello: list[str] = []
    if titolo_originale:
        etichette = RIFERIMENTO_NOTA.findall(titolo_originale)
        if etichette:
            cappello, righe = stacca_note(righe, etichette)

    if impostazioni.get("blocchi"):
        righe = applica_blocchi(righe, impostazioni["blocchi"])
    if impostazioni.get("sezioni"):
        righe = applica_sezioni(righe, impostazioni["sezioni"])
    righe = livella_titoletti(righe, impostazioni)
    righe = normalizza(righe)
    righe = ripulisci_righe_vuote(righe)

    # Per ultimo, a struttura ormai fissata: i confronti fatti sopra (blocchi,
    # sezioni, code di note) guardano il testo come sta nel corpus.
    numero = numero_del_testo(sorgente)
    righe = distingui_note(righe, numero)
    cappello = distingui_note(cappello, numero)

    unita = manifest.get(intestazione.get("id"), {})
    riferimento = ""
    if unita.get("page_start"):
        pagine = f"pp. {unita['page_start']}-{unita['page_end']}"
        riferimento = (
            f"[*La Condizione Operaia*, Gallimard, Parigi 1951, {pagine}."
            "]{.riferimento}\n\n"
        )

    cappello_reso = ""
    if cappello:
        cappello_reso = "::: {.cappello}\n" + "\n\n".join(cappello) + "\n:::\n\n"

    testa = (
        "---\n"
        f"title: {cita_yaml(titolo)}\n"
        "---\n\n"
        "<!-- Generato da scripts/build_site.py a partire da "
        f"corpus/it/{sorgente.name}. Non modificare a mano. -->\n\n"
    )
    return titolo, testa + riferimento + cappello_reso + "\n".join(righe) + "\n"


def main() -> int:
    analizzatore = argparse.ArgumentParser(
        description="Genera site/testi/*.qmd da corpus/it/*.md"
    )
    analizzatore.add_argument(
        "--check",
        action="store_true",
        help="verifica che site/testi/ sia allineato al corpus, senza scrivere",
    )
    argomenti = analizzatore.parse_args()

    configurazione = carica_configurazione()
    manifest = carica_manifest()
    sorgenti = sorted(CORPUS.glob("*.md"))
    if not sorgenti:
        print("nessun testo italiano in corpus/it/", file=sys.stderr)
        return 1

    USCITA.mkdir(parents=True, exist_ok=True)
    attesi: set[str] = set()
    disallineati: list[str] = []

    for sorgente in sorgenti:
        impostazioni = configurazione.get(sorgente.stem) or {}
        try:
            titolo, contenuto = componi(sorgente, impostazioni, manifest)
        except ErroreDiStruttura as errore:
            print(f"{sorgente.name}: {errore}", file=sys.stderr)
            return 1
        destinazione = USCITA / nome_di_uscita(sorgente, titolo, impostazioni)
        attesi.add(destinazione.name)
        vecchio = None
        if destinazione.exists():
            vecchio = destinazione.read_text(encoding="utf-8")
        if vecchio == contenuto:
            continue
        if argomenti.check:
            disallineati.append(destinazione.name)
        else:
            destinazione.write_text(contenuto, encoding="utf-8", newline="\n")
            print(f"scritto site/testi/{destinazione.name}")

    for superfluo in sorted(p for p in USCITA.glob("*.qmd") if p.name not in attesi):
        if argomenti.check:
            disallineati.append(superfluo.name)
        else:
            superfluo.unlink()
            print(f"rimosso site/testi/{superfluo.name}")

    if argomenti.check:
        if disallineati:
            print(
                "site/testi/ non è allineato al corpus: "
                + ", ".join(sorted(disallineati)),
                file=sys.stderr,
            )
            return 1
        print(f"site/testi/: {len(attesi)} capitoli allineati al corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
