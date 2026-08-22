"""Official HTML archive discovery for historical Extra Gazettes."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from ..models import DiscoveredDocument
from .documents_gov_lk import USER_AGENT, normalise_language


EXTRA_GAZETTE_ARCHIVE_URL = "https://www.documents.gov.lk/view/egz/egz.html"
EXTRA_GAZETTE_ARCHIVE_YEAR_URL = "https://www.documents.gov.lk/view/egz/egz_{year}.html"

_NUMBER_RE = re.compile(r"\b(\d{3,5})\s*/\s*(\d{1,3})\b")
_DATE_RE = re.compile(r"\b((?:19|20)\d{2}-\d{2}-\d{2})\b")
_YEAR_LINK_RE = re.compile(r"egz_((?:19|20)\d{2})\.html", re.I)
_LANGUAGE_SUFFIXES = {"e": "en", "s": "si", "t": "ta"}


class _ArchiveTableParser(HTMLParser):
    """Collect text and links from the Government Printer's archive tables."""

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


def _get_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def _language(pdf_url: str, link_text: str) -> str:
    filename = urlparse(pdf_url).path.rsplit("/", 1)[-1]
    match = re.search(r"_([EST])\.pdf$", filename, re.I)
    if match:
        return _LANGUAGE_SUFFIXES[match.group(1).lower()]
    return normalise_language(link_text) or "und"


def discover_extra_gazette_archive_years() -> list[int]:
    """Return every year advertised by the official archive index."""

    return sorted({int(match.group(1)) for match in _YEAR_LINK_RE.finditer(_get_html(EXTRA_GAZETTE_ARCHIVE_URL))})


def discover_extra_gazettes_for_year(year: int) -> list[DiscoveredDocument]:
    """Return every Extra Gazette PDF listed for one official archive year."""

    page_url = EXTRA_GAZETTE_ARCHIVE_YEAR_URL.format(year=year)
    parser = _ArchiveTableParser()
    parser.feed(_get_html(page_url))
    documents: list[DiscoveredDocument] = []

    for cells in parser.rows:
        row_text = " ".join(" ".join(cell["text"]) for cell in cells)
        number_match = _NUMBER_RE.search(row_text)
        if not number_match:
            continue
        document_number = f"{number_match.group(1)}/{number_match.group(2)}"
        date_match = _DATE_RE.search(row_text)
        title = " ".join(cells[2]["text"]).strip() if len(cells) > 2 else document_number
        title = re.sub(r"\s+", " ", title) or document_number

        for cell in cells:
            link_text = " ".join(cell["text"])
            for href in cell["links"]:
                if not href.lower().split("?", 1)[0].endswith(".pdf"):
                    continue
                pdf_url = urljoin(page_url, href)
                documents.append(
                    DiscoveredDocument(
                        source="documents.gov.lk",
                        document_type="extra-gazette",
                        source_id=document_number.replace("/", "-"),
                        title=title,
                        official_page_url=page_url,
                        source_pdf_url=pdf_url,
                        published_date=date_match.group(1) if date_match else None,
                        archive_year=str(year),
                        language=_language(pdf_url, link_text),
                        document_number=document_number,
                    )
                )
    return documents
