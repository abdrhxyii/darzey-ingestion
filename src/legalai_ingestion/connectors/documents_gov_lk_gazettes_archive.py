"""Historical Gazette discovery through the official Gazette date API."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

from ..models import DiscoveredDocument
from .documents_gov_lk_archive import DiscoveredDocumentPage
from .documents_gov_lk_gazettes import fetch_gazette_date_page, discover_gazette_issue

DATE_PAGE_SIZE = 100


def discover_gazettes_for_year_range(from_year: int, to_year: int, *, max_pages: int | None = None) -> Iterator[DiscoveredDocument]:
    """Yield Gazette PDFs in a publication-year range."""
    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when provided")
    current_page = 1
    while True:
        issue_dates, total = fetch_gazette_date_page(current_page, limit=DATE_PAGE_SIZE)
        if not issue_dates:
            return
        for issue_date in issue_dates:
            year = int(issue_date[:4])
            if from_year <= year <= to_year:
                for document in discover_gazette_issue(issue_date):
                    yield replace(document, archive_year=str(year))
        if max_pages is not None and current_page >= max_pages:
            return
        if min(int(issue_date[:4]) for issue_date in issue_dates) < from_year:
            return
        if current_page * DATE_PAGE_SIZE >= total:
            return
        current_page += 1


def discover_gazette_pages_for_year_range(from_year: int, to_year: int, *, start_page: int = 1, max_pages: int | None = None) -> Iterator[DiscoveredDocumentPage]:
    """Yield bounded Gazette date pages without downloading earlier pages again."""
    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    if start_page < 1:
        raise ValueError("start_page must be positive")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when provided")
    current_page = 1
    emitted_pages = 0
    while True:
        dates, total = fetch_gazette_date_page(current_page, limit=DATE_PAGE_SIZE)
        if not dates:
            return
        if current_page >= start_page:
            documents: list[DiscoveredDocument] = []
            for issue_date in dates:
                if from_year <= int(issue_date[:4]) <= to_year:
                    documents.extend(replace(item, archive_year=issue_date[:4]) for item in discover_gazette_issue(issue_date))
            yield DiscoveredDocumentPage(current_page, documents)
            emitted_pages += 1
            if max_pages is not None and emitted_pages >= max_pages:
                return
        if min(int(value[:4]) for value in dates) < from_year:
            return
        if current_page * DATE_PAGE_SIZE >= total:
            return
        current_page += 1
