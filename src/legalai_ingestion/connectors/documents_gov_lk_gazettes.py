"""Official Gazette issue PDFs listed by documents.gov.lk."""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterable
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..models import DiscoveredDocument
from .documents_gov_lk import _get, normalise_language


GAZETTES_URL = "https://documents.gov.lk/web/gazettes"
GAZETTE_ISSUE_URL = "https://documents.gov.lk/web/Gazette?date={issue_date}"
GAZETTE_API_BASE_URL = os.environ.get(
    "GAZETTE_API_BASE_URL",
    "http://203.143.21.148:4500/website-data",
).rstrip("/")


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


def _gazette_dates_api_url(*, page: int, limit: int) -> str:
    return f"{GAZETTE_API_BASE_URL}/gazette/get-all-gazette-dates?{urlencode({'limit': limit, 'page': page})}"


def _decode_gazette_dates_response(payload: bytes) -> tuple[list[str], int]:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError("Gazette date API returned invalid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("Gazette date API returned an unexpected payload")
    raw_dates = value.get("dates")
    if not isinstance(raw_dates, list):
        raise ValueError("Gazette date API returned no dates")
    dates = [
        datetime.fromisoformat(item.replace("Z", "+00:00")).date().isoformat()
        for item in raw_dates
        if isinstance(item, str)
    ]
    total = value.get("total")
    if not isinstance(total, int):
        total = len(dates)
    return dates, total


def fetch_gazette_date_page(
    page: int, *, limit: int = 100, attempts: int = 6, retry_delay_seconds: float = 5
) -> tuple[list[str], int]:
    """Fetch one date page from the official Gazette API with transient retries."""

    if page < 1 or limit < 1 or attempts < 1:
        raise ValueError("page, limit, and attempts must be positive")
    url = _gazette_dates_api_url(page=page, limit=limit)
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": "LegalAI-ingestion/0.1", "Accept": "application/json"})
            with urlopen(request, timeout=60) as response:
                return _decode_gazette_dates_response(response.read())
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt + 1 < attempts:
                time.sleep(retry_delay_seconds * (attempt + 1))
    raise RuntimeError(f"Gazette date API unavailable after {attempts} attempts: {url}") from last_error


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
