from __future__ import annotations

import json
import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import quote
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from ..models import DiscoveredDocument

EXTRA_GAZETTES_URL = "https://documents.gov.lk/web/extra_gazettes"
EXTRA_GAZETTE_ARCHIVE_URL = "https://www.documents.gov.lk/view/egz/egz.html"
EXTRA_GAZETTE_ARCHIVE_YEAR_URL = "https://www.documents.gov.lk/view/egz/egz_{year}.html"
USER_AGENT = "LegalAI-ingestion/0.1 (+https://github.com/abdrhxyii/darzey-ingestion)"

_NUMBER_RE = re.compile(r"\b(\d{3,5})\s*/\s*(\d{1,3})\b")
_DATE_RE = re.compile(r"\b((?:19|20)\d{2}-\d{2}-\d{2})\b")
_YEAR_LINK_RE = re.compile(r"egz_(20\d{2})\.html", re.I)
_LANGUAGE_SUFFIXES = {"e": "en", "s": "si", "t": "ta"}


def _normalise_language(value: str) -> str:
    language = value.strip().lower()
    return {"english": "en", "sinhala": "si", "sinhalese": "si", "tamil": "ta"}.get(
        language, language
    )


class _ArchiveTableParser(HTMLParser):
    """Extract rows and PDF links from the Government Printer's HTML archive."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict[str, list[str]]]] = []
        self._row: list[dict[str, list[str]]] | None = None
        self._cell: dict[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = {"text": [], "links": []}
            self._row.append(self._cell)
        elif tag == "a" and self._cell is not None:
            href = dict(attrs).get("href")
            if href:
                self._cell["links"].append(href)

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"}:
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _archive_language(pdf_url: str, link_text: str) -> str:
    filename = urlparse(pdf_url).path.rsplit("/", 1)[-1]
    match = re.search(r"_([EST])\.pdf$", filename, re.I)
    if match:
        return _LANGUAGE_SUFFIXES[match.group(1).lower()]
    return _normalise_language(link_text) or "und"


def _archive_documents(page_html: str, *, year: int, page_url: str) -> list[DiscoveredDocument]:
    parser = _ArchiveTableParser()
    parser.feed(page_html)
    discovered: list[DiscoveredDocument] = []

    for cells in parser.rows:
        text = " ".join(" ".join(cell["text"]) for cell in cells)
        number_match = _NUMBER_RE.search(text)
        if not number_match:
            continue
        document_number = f"{number_match.group(1)}/{number_match.group(2)}"
        source_id = document_number.replace("/", "-")
        date_match = _DATE_RE.search(text)
        published_date = date_match.group(1) if date_match else None
        title = " ".join(cells[2]["text"]).strip() if len(cells) > 2 else document_number
        title = re.sub(r"\s+", " ", title) or document_number

        for cell in cells:
            link_text = " ".join(cell["text"])
            for href in cell["links"]:
                if not href.lower().split("?", 1)[0].endswith(".pdf"):
                    continue
                pdf_url = urljoin(page_url, href)
                discovered.append(
                    DiscoveredDocument(
                        source="documents.gov.lk",
                        document_type="extra-gazette",
                        source_id=source_id,
                        title=title,
                        official_page_url=page_url,
                        source_pdf_url=pdf_url,
                        published_date=published_date,
                        archive_year=str(year),
                        language=_archive_language(pdf_url, link_text),
                        document_number=document_number,
                    )
                )
    return discovered


def _get(url: str, *, timeout: int = 60) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _initial_items(page_html: str) -> list[dict[str, object]]:
    """Read the server-rendered initialData used by the official Next.js page."""

    marker = r'\\"initialData\\":'
    match = re.search(
        marker + r'\{\\"items\\"\s*:\s*(\[.*?\])\s*,\s*\\"total\\"\s*:\s*\d+\}',
        page_html,
        re.S,
    )
    if not match:
        raise ValueError("Could not find Extra Gazette initialData in official page")

    # The Next.js RSC payload is a JSON string containing another JSON value.
    # Decode the enclosing string first so embedded quotes, newlines, and other
    # JSON escapes in descriptions are preserved correctly.
    try:
        decoded_items = json.loads(f'"{match.group(1)}"')
        return json.loads(decoded_items)
    except json.JSONDecodeError as error:
        raise ValueError("Could not decode Extra Gazette initialData") from error


def discover_extra_gazettes(*, page_url: str = EXTRA_GAZETTES_URL) -> list[DiscoveredDocument]:
    items = _initial_items(_get(page_url).decode("utf-8"))
    discovered: list[DiscoveredDocument] = []

    for item in items:
        item_id = str(item.get("id") or "").strip()
        number = str(item.get("gazetteNoText") or "").strip()
        if not item_id or not number:
            continue

        title = str(item.get("descriptionEnglish") or item.get("descriptionSinhala") or number)
        published = item.get("date")
        published_date = None
        if isinstance(published, str) and published:
            published_date = datetime.fromisoformat(published.replace("Z", "+00:00")).date().isoformat()

        contents = item.get("contents")
        if not isinstance(contents, list):
            continue
        for content in contents:
            if not isinstance(content, dict):
                continue
            uploaded_file = content.get("uploadedFile")
            language = _normalise_language(str(content.get("language") or ""))
            if not isinstance(uploaded_file, str) or not uploaded_file or not language:
                continue

            # This is the public proxy used by the official site's own buttons.
            pdf_url = "https://documents.gov.lk/api/content-file-proxy?file=" + quote(
                "/" + uploaded_file, safe="/"
            )
            discovered.append(
                DiscoveredDocument(
                    source="documents.gov.lk",
                    document_type="extra-gazette",
                    source_id=f"{item_id}-{language}",
                    title=title,
                    official_page_url=page_url,
                    source_pdf_url=pdf_url,
                    published_date=published_date,
                    language=language,
                    document_number=number,
                )
            )

    return discovered


def discover_extra_gazette_archive_years() -> list[int]:
    """Return every year advertised by the official Extra Gazette archive."""

    html = _get(EXTRA_GAZETTE_ARCHIVE_URL).decode("utf-8", "replace")
    return sorted({int(match.group(1)) for match in _YEAR_LINK_RE.finditer(html)})


def discover_extra_gazettes_for_year(year: int) -> list[DiscoveredDocument]:
    """Discover every PDF listed for one official archive year."""

    page_url = EXTRA_GAZETTE_ARCHIVE_YEAR_URL.format(year=year)
    html = _get(page_url).decode("utf-8", "replace")
    return _archive_documents(html, year=year, page_url=page_url)


def download_pdf(url: str) -> bytes:
    body = _get(url)
    if not body.startswith(b"%PDF"):
        raise ValueError(f"Official download was not a PDF: {url}")
    return body
