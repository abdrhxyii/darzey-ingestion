"""Historical Gazette discovery through the official public date-list page."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime

from ..models import DiscoveredDocument
from .documents_gov_lk_archive import DiscoveredDocumentPage
from .documents_gov_lk_gazettes import GAZETTES_URL, discover_gazette_issue


def _visible_dates(page: object) -> list[str]:
    """Read official date buttons from one visible Gazette date-list page."""

    values = page.get_by_role("button").all_text_contents()
    dates: list[str] = []
    for value in values:
        try:
            dates.append(datetime.strptime(value.strip(), "%b %d, %Y").date().isoformat())
        except ValueError:
            continue
    return dates


def discover_gazettes_for_year_range(
    from_year: int, to_year: int, *, max_pages: int | None = None
) -> Iterator[DiscoveredDocument]:
    """Yield Gazette PDFs in a publication-year range using the public date UI."""

    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when provided")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover
        raise RuntimeError('Historical Gazette backfill requires: pip install -e ".[browser]"') from error

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(GAZETTES_URL, wait_until="domcontentloaded", timeout=60_000)
            current_page = 1
            while True:
                page.wait_for_timeout(500)
                issue_dates = _visible_dates(page)
                if not issue_dates:
                    raise ValueError("Official Gazette date page returned no visible issue dates")
                for issue_date in issue_dates:
                    year = int(issue_date[:4])
                    if from_year <= year <= to_year:
                        for document in discover_gazette_issue(issue_date):
                            yield replace(document, archive_year=str(year))
                if max_pages is not None and current_page >= max_pages:
                    return
                if max(int(issue_date[:4]) for issue_date in issue_dates) < from_year:
                    return
                next_page = page.get_by_role("button", name="next page button", exact=True).first
                if not next_page.is_enabled():
                    return
                previous_dates = issue_dates
                next_page.click()
                for _ in range(120):
                    page.wait_for_timeout(500)
                    updated_dates = _visible_dates(page)
                    if updated_dates and updated_dates != previous_dates:
                        break
                else:
                    raise TimeoutError("Official Gazette date page did not advance")
                current_page += 1
        finally:
            browser.close()


def discover_gazette_pages_for_year_range(from_year: int, to_year: int, *, start_page: int = 1, max_pages: int | None = None) -> Iterator[DiscoveredDocumentPage]:
    """Yield bounded Gazette date-list pages without downloading earlier pages again."""
    if start_page < 1:
        raise ValueError("start_page must be positive")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover
        raise RuntimeError('Historical Gazette backfill requires: pip install -e ".[browser]"') from error
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(GAZETTES_URL, wait_until="domcontentloaded", timeout=60_000)
            current_page = 1
            while True:
                page.wait_for_timeout(500)
                dates = _visible_dates(page)
                if not dates:
                    raise ValueError("Official Gazette date page returned no visible issue dates")
                if current_page >= start_page:
                    documents: list[DiscoveredDocument] = []
                    for issue_date in dates:
                        if from_year <= int(issue_date[:4]) <= to_year:
                            documents.extend(replace(item, archive_year=issue_date[:4]) for item in discover_gazette_issue(issue_date))
                    yield DiscoveredDocumentPage(current_page, documents)
                    if max_pages is not None:
                        max_pages -= 1
                        if max_pages == 0:
                            return
                if max(int(value[:4]) for value in dates) < from_year:
                    return
                next_button = page.get_by_role("button", name="next page button", exact=True).first
                if not next_button.is_enabled():
                    return
                previous_dates = dates
                next_button.click()
                for _ in range(120):
                    page.wait_for_timeout(500)
                    updated_dates = _visible_dates(page)
                    if updated_dates and updated_dates != previous_dates:
                        break
                else:
                    raise TimeoutError("Official Gazette date page did not advance")
                current_page += 1
        finally:
            browser.close()
