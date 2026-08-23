"""MediaWiki API acquisition and conservative HTML-to-Markdown conversion."""

from __future__ import annotations

import copy
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from markdownify import markdownify
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .catalog import EXPECTED_INDEX_UNIT_COUNT, EXPECTED_UNIT_COUNT, SOURCE_INDEX_ORDERS, UNITS, UnitSpec
from .util import dump_json, dump_yaml, load_json, load_yaml, sha256_bytes, sha256_file

API_ENDPOINT = "https://fr.wikisource.org/w/api.php"
INDEX_PAGE = "La Condition ouvrière"
INDEX_URL = "https://fr.wikisource.org/wiki/La_Condition_ouvri%C3%A8re"
USER_AGENT = "condition-ouvriere-corpus/0.1 (reproducible scholarly corpus; MediaWiki API)"


class AcquisitionError(RuntimeError):
    pass


def canonical_url(page: str) -> str:
    return "https://fr.wikisource.org/wiki/" + quote(page.replace(" ", "_"), safe="/_()")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class WikisourceClient:
    def __init__(self, timeout: int = 60) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
        retry = Retry(
            total=6,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get(self, params: dict[str, str]) -> dict[str, Any]:
        params = {**params, "maxlag": "5"}
        try:
            response = self.session.get(API_ENDPOINT, params=params, timeout=self.timeout)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AcquisitionError(f"richiesta MediaWiki fallita: {exc}") from exc
        if "error" in payload:
            raise AcquisitionError(str(payload["error"]))
        return payload

    def parse(self, page: str, revision_id: int | None = None) -> dict[str, Any]:
        target = {"oldid": str(revision_id)} if revision_id else {"page": page}
        return self._get(
            {
                "action": "parse",
                "format": "json",
                "formatversion": "2",
                **target,
                "prop": "text|wikitext|revid|displaytitle|sections|links",
                "disablelimitreport": "1",
            }
        )["parse"]

    def revisions(self, pages: list[str]) -> dict[str, dict[str, Any]]:
        payload = self._get(
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "prop": "revisions",
                "rvprop": "ids|timestamp",
                "titles": "|".join(pages),
            }
        )
        result: dict[str, dict[str, Any]] = {}
        for item in payload["query"]["pages"]:
            if "missing" in item:
                raise AcquisitionError(f"Pagina MediaWiki non trovata: {item['title']}")
            revision = item["revisions"][0]
            result[item["title"]] = {
                "pageid": item["pageid"],
                "title": item["title"],
                "revid": revision["revid"],
                "parentid": revision.get("parentid"),
                "timestamp": revision["timestamp"],
            }
        if len(result) != len(pages):
            raise AcquisitionError(f"Metadati revisioni incompleti: attesi {len(pages)}, ricevuti {len(result)}")
        return result

    def snapshot(self, page: str, revision: dict[str, Any]) -> dict[str, Any]:
        parsed = self.parse(page, revision_id=revision["revid"])
        if parsed["revid"] != revision["revid"]:
            raise AcquisitionError(f"Revisione inattesa durante il parse di {page}")
        return {"page": page, "revision": revision, "parse": parsed}


def validate_index_snapshot(snapshot: dict[str, Any]) -> None:
    prefix = INDEX_PAGE + "/"
    linked = {
        link["title"]
        for link in snapshot["parse"].get("links", [])
        if link.get("ns") == 0 and link.get("title", "").startswith(prefix)
    }
    numbered = sorted(x for x in linked if re.fullmatch(re.escape(prefix) + r"\d{2}", x))
    expected = [f"{INDEX_PAGE}/{number:02d}" for number in SOURCE_INDEX_ORDERS]
    if numbered != expected:
        raise AcquisitionError(
            f"Indice inatteso: attese {EXPECTED_INDEX_UNIT_COUNT} sottopagine {expected}, trovate {numbered}"
        )


def extract_page_range(snapshot: dict[str, Any]) -> tuple[int, int]:
    soup = BeautifulSoup(snapshot["parse"]["text"], "html.parser")
    start = soup.select_one("#headertemplate [itemprop='pageStart']")
    end = soup.select_one("#headertemplate [itemprop='pageEnd']")
    if start is None or end is None:
        raise AcquisitionError(f"Intervallo di pagine assente in {snapshot['page']}")
    try:
        return int(start.get_text(strip=True)), int(end.get_text(strip=True))
    except ValueError:
        # At least one current header (unit 04) contains a malformed end value.
        # ProofreadPage's in-text markers still identify the printed pages exactly.
        printed_pages = [
            int(marker["id"])
            for marker in soup.select(".pagenum.ws-pagenum[id]")
            if marker.get("id", "").isdigit()
        ]
        if not printed_pages:
            raise AcquisitionError(f"Intervallo di pagine non interpretabile in {snapshot['page']}")
        return min(printed_pages), max(printed_pages)


def _collapse_text_whitespace(root: Tag) -> None:
    for node in list(root.descendants):
        if not isinstance(node, NavigableString) or isinstance(node, Comment):
            continue
        if node.parent and node.parent.name in {"pre", "code"}:
            continue
        collapsed = re.sub(r"[ \t\r\n]+", " ", str(node))
        node.replace_with(collapsed)


def _tokenize_inline_html(root: Tag) -> dict[str, str]:
    replacements: dict[str, str] = {}
    counter = 0
    # Process outer abbreviations first; their nested superscripts stay inside the token.
    for tag in list(root.select("abbr")) + [x for x in root.find_all(["sup", "sub"]) if not x.find_parent("abbr")]:
        if not tag.parent or (tag.name == "sup" and "reference" in tag.get("class", [])):
            continue
        counter += 1
        token = f"@@INLINEHTML{counter}@@"
        replacements[token] = str(tag)
        tag.replace_with(NavigableString(token))
    return replacements


def _extract_footnotes(root: Tag) -> list[str]:
    notes: list[str] = []
    id_to_number: dict[str, int] = {}
    for item in root.select("li[id^='cite_note']"):
        note_id = item.get("id", "")
        text = item.select_one(".reference-text")
        if text is None:
            continue
        number = len(notes) + 1
        id_to_number[note_id] = number
        fragment = copy.copy(text)
        for anchor in fragment.find_all("a", href=True):
            if anchor["href"].startswith("/"):
                anchor["href"] = "https://fr.wikisource.org" + anchor["href"]
        _collapse_text_whitespace(fragment)
        rendered = markdownify(str(fragment), heading_style="ATX", bullets="-").strip()
        notes.append(rendered)

    for ref in root.select("sup.reference"):
        anchor = ref.find("a", href=True)
        target = anchor["href"].lstrip("#") if anchor else ""
        number = id_to_number.get(target)
        if number is None:
            raise AcquisitionError(f"Nota senza definizione: {target}")
        ref.replace_with(NavigableString(f"[^{number}]"))

    for references in root.select("ol.references"):
        references.decompose()
    return notes


def render_markdown(snapshot: dict[str, Any], unit: UnitSpec) -> str:
    soup = BeautifulSoup(snapshot["parse"]["text"], "html.parser")
    root = soup.select_one(".prp-pages-output")
    if root is None:
        raise AcquisitionError(f"Contenitore ProofreadPage assente in {unit.wikisource_page}")

    # MediaWiki places the rendered note list immediately after prp-pages-output,
    # while the reference calls remain inside it; process their common parent.
    parser_output = soup.select_one(".mw-parser-output")
    if parser_output is None:
        raise AcquisitionError(f"Contenitore MediaWiki assente in {unit.wikisource_page}")
    notes = _extract_footnotes(parser_output)

    for unwanted in root.select(".ws-noexport, style, script, link, meta, .mw-editsection, .Z3988"):
        unwanted.decompose()

    # Preserve printed-page boundaries as unobtrusive Markdown comments.
    page_tokens: dict[str, str] = {}
    for index, marker in enumerate(root.select(".pagenum.ws-pagenum"), start=1):
        printed = marker.get("id", "?")
        scan = marker.get("title", "")
        token = f"@@PAGEMARKER{index}@@"
        page_tokens[token] = f'<a id="p{printed}"></a><!-- page: {printed}; scan: {scan} -->'
        marker.replace_with(NavigableString(token))

    for corrected in root.select(".coquille"):
        original = corrected.get("title")
        if original:
            corrected.append(NavigableString(f'@@COQUILLE:{original}@@'))

    for anchor in root.find_all("a", href=True):
        if anchor["href"].startswith("/"):
            anchor["href"] = "https://fr.wikisource.org" + anchor["href"]

    first_heading = root.find(re.compile(r"^h[1-6]$"))
    if first_heading:
        first_heading.name = "h1"

    _collapse_text_whitespace(root)
    inline_tokens = _tokenize_inline_html(root)
    body = markdownify(str(root), heading_style="ATX", bullets="-", strip=["style", "script"])

    for token, replacement in {**page_tokens, **inline_tokens}.items():
        body = body.replace(token, replacement)
    body = re.sub(r"@@COQUILLE:([^@]+)@@", r'<!-- Wikisource: coquille, lezione del facsimile "\1" -->', body)
    body = re.sub(r"[ \t]+\n", "\n", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    if notes:
        body += "\n\n" + "\n\n".join(f"[^{i}]: {note}" for i, note in enumerate(notes, start=1))

    frontmatter = {
        "id": unit.id,
        "title_fr": unit.title_fr,
        "author": unit.author,
        "source_url": canonical_url(unit.wikisource_page),
        "wikisource_page": unit.wikisource_page,
        "revision_id": snapshot["revision"]["revid"],
        "revision_timestamp": snapshot["revision"]["timestamp"],
    }
    yaml_text = dump_yaml(frontmatter).decode("utf-8").rstrip()
    return f"---\n{yaml_text}\n---\n\n{body}\n"


def build_manifest_data(root: Path, acquired_at: str | None = None) -> dict[str, Any]:
    existing_path = root / "corpus" / "manifest.yml"
    existing = load_yaml(existing_path) if existing_path.exists() else None
    if acquired_at is None:
        acquired_at = existing.get("acquired_at") if existing else utc_now()

    index_path = root / "source" / "snapshots" / "index.json"
    index_snapshot = load_json(index_path)
    validate_index_snapshot(index_snapshot)

    units: list[dict[str, Any]] = []
    for unit in UNITS:
        snapshot_path = root / "source" / "snapshots" / f"{unit.source_order:02d}.json"
        local_path = root / unit.local_file
        snapshot = load_json(snapshot_path)
        page_start, page_end = extract_page_range(snapshot)
        entry: dict[str, Any] = {
            "id": unit.id,
            "order": unit.source_order,
            "title_fr": unit.title_fr,
            "author": unit.author,
            "date": unit.date,
            "page_start": page_start,
            "page_end": page_end,
            "source_url": canonical_url(unit.wikisource_page),
            "wikisource_page": unit.wikisource_page,
            "revision_id": snapshot["revision"]["revid"],
            "revision_timestamp": snapshot["revision"]["timestamp"],
            "local_file": unit.local_file,
            "content_type": unit.content_type,
            "is_simone_weil": unit.is_simone_weil,
            "sha256": sha256_file(local_path),
            "snapshot_sha256": sha256_file(snapshot_path),
        }
        if unit.editorial_notes:
            entry["editorial_notes"] = unit.editorial_notes
        units.append(entry)

    return {
        "schema_version": 1,
        "edition": {
            "title": "La Condition ouvrière",
            "author": "Simone Weil",
            "editor": "Albert Camus",
            "publisher": "Gallimard",
            "publication_place": "Paris",
            "publication_year": 1951,
        },
        "canonical_source": {
            "name": "Wikisource francese",
            "index_url": INDEX_URL,
            "wikisource_page": INDEX_PAGE,
            "revision_id": index_snapshot["revision"]["revid"],
            "revision_timestamp": index_snapshot["revision"]["timestamp"],
            "snapshot_sha256": sha256_file(index_path),
        },
        "acquired_at": acquired_at,
        "acquisition": {
            "method": "MediaWiki Action API (action=parse), contenuto ProofreadPage espanso",
            "api_endpoint": API_ENDPOINT,
            "snapshot_directory": "source/snapshots",
            "converter": "condition_ouvriere.wikisource.render_markdown",
        },
        "expected_unit_count": EXPECTED_UNIT_COUNT,
        "weil_unit_count": sum(unit.is_simone_weil for unit in UNITS),
        "editorial_unit_count": 0,
        "units": units,
    }


def _write_candidate(root: Path, client: WikisourceClient, destination: Path | None = None) -> Path:
    staging = destination.resolve() if destination else root / "source" / "staging" / "current"
    if staging.exists():
        if destination and any(staging.iterdir()):
            raise AcquisitionError(f"La directory di output non è vuota: {staging}")
        import shutil

        shutil.rmtree(staging)
    (staging / "source" / "snapshots").mkdir(parents=True)
    (staging / "corpus" / "fr").mkdir(parents=True)

    page_names = [INDEX_PAGE, *(unit.wikisource_page for unit in UNITS)]
    revisions = client.revisions(page_names)

    index_snapshot = client.snapshot(INDEX_PAGE, revisions[INDEX_PAGE])
    validate_index_snapshot(index_snapshot)
    (staging / "source" / "snapshots" / "index.json").write_bytes(dump_json(index_snapshot))

    for unit in UNITS:
        # A small client-side interval avoids burdening the public API and
        # complements the explicit 429/Retry-After handling above.
        time.sleep(0.25)
        snapshot = client.snapshot(unit.wikisource_page, revisions[unit.wikisource_page])
        snapshot_path = staging / "source" / "snapshots" / f"{unit.source_order:02d}.json"
        snapshot_path.write_bytes(dump_json(snapshot))
        output_path = staging / unit.local_file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_markdown(snapshot, unit), encoding="utf-8", newline="\n")

    manifest = build_manifest_data(staging, acquired_at=utc_now())
    (staging / "corpus" / "manifest.yml").write_bytes(dump_yaml(manifest))
    return staging


def _local_integrity_errors(root: Path) -> list[str]:
    manifest_path = root / "corpus" / "manifest.yml"
    if not manifest_path.exists():
        return []
    manifest = load_yaml(manifest_path)
    errors = []
    for item in manifest.get("units", []):
        path = root / item["local_file"]
        if not path.exists():
            errors.append(f"file locale mancante: {item['local_file']}")
        elif sha256_file(path) != item.get("sha256"):
            errors.append(f"modifica locale non registrata: {item['local_file']}")
    return errors


def _candidate_differs(root: Path, staging: Path) -> bool:
    candidate_manifest = load_yaml(staging / "corpus" / "manifest.yml")
    current_manifest_path = root / "corpus" / "manifest.yml"
    if not current_manifest_path.exists():
        return True
    current = load_yaml(current_manifest_path)
    if current["canonical_source"]["revision_id"] != candidate_manifest["canonical_source"]["revision_id"]:
        return True
    for old, new in zip(current.get("units", []), candidate_manifest["units"], strict=False):
        if old.get("revision_id") != new["revision_id"] or old.get("sha256") != new["sha256"]:
            return True
    return len(current.get("units", [])) != len(candidate_manifest["units"])


def _promote(root: Path, staging: Path, preserve_acquired_at: bool) -> None:
    import shutil

    candidate_manifest_path = staging / "corpus" / "manifest.yml"
    candidate_manifest = load_yaml(candidate_manifest_path)
    current_manifest_path = root / "corpus" / "manifest.yml"
    if preserve_acquired_at and current_manifest_path.exists():
        current = load_yaml(current_manifest_path)
        candidate_manifest["acquired_at"] = current["acquired_at"]
        candidate_manifest_path.write_bytes(dump_yaml(candidate_manifest))

    for source in sorted(staging.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(staging)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def fetch_corpus(root: Path, update: bool = False, output_dir: Path | None = None) -> str:
    root = root.resolve()
    if update and output_dir:
        raise AcquisitionError("--update e --output-dir non possono essere usati insieme")
    staging = _write_candidate(root, WikisourceClient(), destination=output_dir)
    if output_dir:
        return f"Ricostruzione indipendente completata in {staging}: {EXPECTED_UNIT_COUNT} unità."
    integrity_errors = _local_integrity_errors(root)
    if integrity_errors:
        details = "\n".join(f"- {error}" for error in integrity_errors)
        raise AcquisitionError(
            "Il corpus canonico contiene modifiche locali. Nessun file è stato sovrascritto; "
            f"la proposta resta in {staging}.\n{details}"
        )

    manifest_exists = (root / "corpus" / "manifest.yml").exists()
    if not manifest_exists:
        _promote(root, staging, preserve_acquired_at=False)
        return f"Corpus iniziale importato: {EXPECTED_UNIT_COUNT} unità."

    if not _candidate_differs(root, staging):
        return "La fonte coincide con il corpus canonico; nessun file modificato."

    if not update:
        raise AcquisitionError(
            "Wikisource differisce dal corpus canonico. Nessun file è stato sovrascritto; "
            f"esaminare {staging} e rieseguire con --update per applicare."
        )

    _promote(root, staging, preserve_acquired_at=False)
    return f"Aggiornamento esplicito applicato: {EXPECTED_UNIT_COUNT} unità."
