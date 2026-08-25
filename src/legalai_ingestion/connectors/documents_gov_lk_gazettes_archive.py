"""Historical Gazette discovery through the official public web page."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime

from ..models import DiscoveredDocument
from .documents_gov_lk_archive import (
    DiscoveredDocumentPage,
    PAGE_LOAD_TIMEOUT_MS,
    _raise_if_source_unavailable,
)
from .documents_gov_lk_gazettes import GAZETTES_URL, discover_gazette_issue, listed_gazette_dates


def _dates_from_value(value: object) -> list[str] | None:
    if isinstance(value, dict):
        dates = value.get("dates")
        if isinstance(dates, list) and all(isinstance(item, str) for item in dates):
            return [item.replace("T00:00:00.000Z", "") for item in dates]
        for child in value.values():
            found = _dates_from_value(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _dates_from_value(child)
            if found is not None:
                return found
    return None


def _dates_from_server_action(response_body: str) -> list[str] | None:
    """Extract Gazette dates from the official page's server-action response."""
    decoder = json.JSONDecoder()
    for line in response_body.splitlines():
        _, separator, value = line.partition(":")
        if separator:
            try:
                found = _dates_from_value(json.loads(value))
            except json.JSONDecodeError:
                found = None
            if found is not None:
                return found
    for match in re.finditer(r'\{"dates":', response_body):
        try:
            payload, _ = decoder.raw_decode(response_body, match.start())
        except json.JSONDecodeError:
            continue
        found = _dates_from_value(payload)
        if found is not None:
            return found
    return None


def _initial_dates_from_page_html(page_html: str) -> list[str]:
    return listed_gazette_dates(page_html)


def _visible_dates(page: object) -> list[str]:
    dates: list[str] = []
    for value in page.get_by_role("button").all_text_contents():
        try:
            dates.append(datetime.strptime(value.strip(), "%b %d, %Y").date().isoformat())
        except ValueError:
            continue
    return dates


def _next_date_page(
    page: object,
    previous_dates: list[str],
) -> list[str]:
    next_button = page.get_by_role("button", name="next page button", exact=True).first
    if not next_button.is_enabled():
        return []
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("Gazette pagination requires Playwright") from error

    try:
        # The Gazette control is a React-Aria <li role="button">. Wait for the
        # streamed Next server-action response produced by the real control;
        # reading it from a response event is too early for streamed bodies.
        with page.expect_response(
            lambda response: (
                response.request.method == "POST"
                and response.url.rstrip("/") == GAZETTES_URL.rstrip("/")
                and response.headers.get("content-type", "").startswith("text/x-component")
            ),
            timeout=PAGE_LOAD_TIMEOUT_MS,
        ) as response_info:
            next_button.click(timeout=PAGE_LOAD_TIMEOUT_MS)
        response = response_info.value
        response.finished()
        response_body = response.text()
        _raise_if_source_unavailable(response_body)
        dates = _dates_from_server_action(response_body)
        if dates and dates != previous_dates:
            return dates
        raise RuntimeError("Official Gazette pagination response contained no new dates")
    except PlaywrightTimeoutError as error:
        raise TimeoutError("Official Gazette date page did not return its server response") from error


def _browser_pages(start_page: int = 1) -> Iterator[tuple[int, list[str]]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover
        raise RuntimeError('Historical Gazette backfill requires: pip install -e ".[browser]"') from error
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(GAZETTES_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            dates = _initial_dates_from_page_html(page.content())
            current_page = 1
            while current_page < start_page:
                dates = _next_date_page(page, dates)
                if not dates:
                    return
                current_page += 1
            while dates:
                yield current_page, dates
                dates = _next_date_page(page, dates)
                if not dates:
                    return
                current_page += 1
        finally:
            browser.close()


def discover_gazettes_for_year_range(from_year: int, to_year: int, *, max_pages: int | None = None) -> Iterator[DiscoveredDocument]:
    """Yield Gazette PDFs in a publication-year range."""
    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when provided")
    for page_number, dates in _browser_pages():
        for issue_date in dates:
            if from_year <= int(issue_date[:4]) <= to_year:
                for document in discover_gazette_issue(issue_date):
                    yield replace(document, archive_year=issue_date[:4])
        if max_pages is not None and page_number >= max_pages:
            return
        if min(int(value[:4]) for value in dates) < from_year:
            return


def discover_gazette_pages_for_year_range(from_year: int, to_year: int, *, start_page: int = 1, max_pages: int | None = None) -> Iterator[DiscoveredDocumentPage]:
    """Yield bounded Gazette date pages for a resumable run."""
    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    if start_page < 1:
        raise ValueError("start_page must be positive")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when provided")
    yielded = 0
    for page_number, dates in _browser_pages(start_page):
        documents: list[DiscoveredDocument] = []
        for issue_date in dates:
            if from_year <= int(issue_date[:4]) <= to_year:
                documents.extend(replace(item, archive_year=issue_date[:4]) for item in discover_gazette_issue(issue_date))
        yield DiscoveredDocumentPage(page_number, documents)
        yielded += 1
        if max_pages is not None and yielded >= max_pages:
            return
        if min(int(value[:4]) for value in dates) < from_year:
            return
