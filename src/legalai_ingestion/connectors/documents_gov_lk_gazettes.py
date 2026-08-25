"""Official Gazette issue PDFs listed by documents.gov.lk."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import date, datetime
from urllib.parse import quote

from ..models import DiscoveredDocument
from .documents_gov_lk import _get, normalise_language


GAZETTES_URL = "https://documents.gov.lk/web/gazettes"
GAZETTE_ISSUE_URL = "https://documents.gov.lk/web/Gazette?date={issue_date}"


def _rsc_strings(page_html: str) -> Iterable[str]:
    """Yield decoded React Server Component payload strings from an official page."""

    for match in re.finditer(r"self\.__next_f\.push\((\[1,.*?\])\)</script>", page_html, re.S):
        try:
            record = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(record, list) and len(record) == 2 and isinstance(record[1], str):
            yield record[1]


def _object_after(payload: str, marker: str) -> object | None:
    position = payload.find(marker)
    if position < 0:
        return None
    start = payload.find("{", position + len(marker))
    if start < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(payload, start)[0]
    except json.JSONDecodeError:
        return None


def listed_gazette_dates(page_html: str) -> list[str]:
    """Read the issue dates embedded in one official date-list page."""

    for payload in _rsc_strings(page_html):
        match = re.search(r'"dates":(\[[^\]]*\])', payload)
        if not match:
            continue
        try:
            values = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        return [
            datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
            for value in values
            if isinstance(value, str)
        ]
    raise ValueError("Official Gazette date page returned no issue dates")


def _pdf_entries(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _pdf_entries(child)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, dict) and child.get("uploadedFileFormat") == "PDF":
                yield child
            else:
                yield from _pdf_entries(child)


def documents_from_gazette_issue_html(
    page_html: str, *, issue_date: str, page_url: str
) -> list[DiscoveredDocument]:
    """Normalize all official PDF parts in one Gazette issue page."""

    content_tree = next(
        (
            value
            for payload in _rsc_strings(page_html)
            if (value := _object_after(payload, '"partContentArray":')) is not None
        ),
        None,
    )
    if content_tree is None:
        raise ValueError(f"Official Gazette issue {issue_date} returned no part data")

    discovered: list[DiscoveredDocument] = []
    for entry in _pdf_entries(content_tree):
        uploaded_file = entry.get("uploadedFile")
        if not isinstance(uploaded_file, str) or not uploaded_file:
            continue
        part = str(entry.get("partNo") or "unknown")
        section = str(entry.get("sectionId") or "unknown")
        language = normalise_language(str(entry.get("language") or "")) or "und"
        source_id = f"{issue_date}-part-{part}-section-{section}"
        section_title = str(entry.get("section") or f"Part {part}, section {section}")
        discovered.append(
            DiscoveredDocument(
                source="documents.gov.lk",
                document_type="gazette",
                source_id=source_id,
                title=f"Gazette {issue_date} — {section_title}",
                official_page_url=page_url,
                source_pdf_url="https://documents.gov.lk/api/content-file-proxy?file="
                + quote("/" + uploaded_file, safe="/"),
                published_date=issue_date,
                language=language,
                document_number=f"Gazette {issue_date}, Part {part}, Section {section}",
            )
        )
    return discovered


def discover_gazette_issue(issue_date: str) -> list[DiscoveredDocument]:
    """Discover every original PDF published under one official Gazette date."""

    page_url = GAZETTE_ISSUE_URL.format(issue_date=issue_date)
    return documents_from_gazette_issue_html(
        _get(page_url).decode("utf-8"), issue_date=issue_date, page_url=page_url
    )


def discover_gazettes() -> list[DiscoveredDocument]:
    """Discover all Gazette PDFs in the latest official issue-date page."""

    documents: list[DiscoveredDocument] = []
    for issue_date in listed_gazette_dates(_get(GAZETTES_URL).decode("utf-8")):
        documents.extend(discover_gazette_issue(issue_date))
    return documents
