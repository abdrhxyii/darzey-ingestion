"""Historical Extra Gazette discovery through the official public web page.

The Government Printing site exposes its records through a server action behind
``/web/extra_gazettes``. The upstream API host configured in the page is
private, so this connector uses the working public page and reads the records
returned when its pagination controls are used.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace

from ..models import DiscoveredDocument
from .documents_gov_lk import EXTRA_GAZETTES_URL, documents_from_extra_gazette_items


DEFAULT_PAGE_SIZE = 10
PAGE_LOAD_TIMEOUT_MS = 60_000

_CAPTURE_PAGE_RESPONSES_SCRIPT = """
(() => {
  const originalFetch = window.fetch;
  window.__legalaiExtraGazetteResponses = [];
  window.fetch = async function(input, init) {
    const response = await originalFetch.call(this, input, init);
    try {
      const url = typeof input === "string" ? input : input.url;
      const body = init && typeof init.body === "string" ? init.body : null;
      const text = await response.clone().text();
      window.__legalaiExtraGazetteResponses.push({ url, body, status: response.status, text });
    } catch (_) {
      // Non-text responses do not participate in record pagination.
    }
    return response;
  };

  const originalOpen = XMLHttpRequest.prototype.open;
  const originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__legalaiMethod = method;
    this.__legalaiUrl = url;
    return originalOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function(body) {
    this.addEventListener("loadend", () => {
      try {
        window.__legalaiExtraGazetteResponses.push({
          url: this.__legalaiUrl,
          body: typeof body === "string" ? body : null,
          status: this.status,
          text: this.responseText,
        });
      } catch (_) {
        // Binary responses do not participate in record pagination.
      }
    });
    return originalSend.call(this, body);
  };
})();
"""


def _items_from_server_action(response_body: str) -> list[dict[str, object]]:
    """Extract the records from the public page's Next.js server-action response."""

    for line in response_body.splitlines():
        _, separator, value = line.partition(":")
        if not separator:
            continue
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            continue
        items = _record_items_from_payload(payload)
        if items is not None:
            return items

    # Next.js normally separates its React Server Component records with
    # newlines. The official site sometimes compacts multiple records into one
    # response body instead (for example: ``0:{...} 1:{"data":[...]}``).
    # Decode the record beginning at each data object so both formats work.
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{"data":', response_body):
        try:
            payload, _ = decoder.raw_decode(response_body, match.start())
        except json.JSONDecodeError:
            continue
        items = _record_items_from_payload(payload)
        if items is not None:
            return items

    raise ValueError("Official Extra Gazette page returned no record data")


def _record_items_from_payload(payload: object) -> list[dict[str, object]] | None:
    """Return the table rows when a decoded RSC payload contains them."""

    if not isinstance(payload, dict):
        return None
    items = payload.get("data")
    if not isinstance(items, list):
        return None
    return [item for item in items if isinstance(item, dict)]


def _captured_page_responses(page: object, expected_page: int) -> list[dict[str, object]]:
    """Return every response body captured for one official pagination request."""

    return page.evaluate(
        """expectedPage => {
          const captures = window.__legalaiExtraGazetteResponses || [];
          return captures.filter(({ body }) =>
            body &&
            (() => {
              try { return JSON.parse(body)[0]?.page === expectedPage; }
              catch (_) { return false; }
            })()
          ).map(({ url, status, text }) => ({ url, status, text })).filter(({ text }) => Boolean(text));
        }""",
        expected_page,
    )


def _wait_for_captured_page_items(
    page: object, expected_page: int, *, document_label: str = "Extra Gazette"
) -> list[dict[str, object]]:
    """Wait for the actual record payload among responses for one page request."""

    examined: set[str] = set()
    for _ in range(PAGE_LOAD_TIMEOUT_MS // 500):
        for response in _captured_page_responses(page, expected_page):
            response_body = response.get("text")
            if not isinstance(response_body, str):
                continue
            if response_body in examined:
                continue
            examined.add(response_body)
            try:
                return _items_from_server_action(response_body)
            except ValueError:
                # The site emits ancillary server-action responses too. Only a
                # response that actually carries ``data`` is the table payload.
                preview = response_body.replace("\n", " ")[:300]
                print(
                    f"Ignoring non-record {document_label} response "
                    f"for page {expected_page}: status={response.get('status')} "
                    f"url={response.get('url')} body={preview!r}"
                )
                continue
        page.wait_for_timeout(500)
    raise TimeoutError(
        f"Official {document_label} page did not return record data for page {expected_page}"
    )


DocumentMapper = Callable[[list[dict[str, object]]], list[DiscoveredDocument]]


@dataclass(frozen=True)
class DiscoveredDocumentPage:
    """One official listing page after its documents have been year-filtered."""

    page_number: int
    documents: list[DiscoveredDocument]


def discover_documents_for_year_range(
    from_year: int,
    to_year: int,
    *,
    page_url: str,
    grid_name: str,
    document_label: str,
    documents_from_items: DocumentMapper,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int | None = None,
) -> Iterator[DiscoveredDocument]:
    """Yield one official documents.gov.lk table over a publication-year range."""

    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    if page_size != DEFAULT_PAGE_SIZE:
        raise ValueError(f"The official page currently uses {DEFAULT_PAGE_SIZE} records per page")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when provided")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover - exercised in GitHub workflow
        raise RuntimeError(
            f"Historical {document_label} backfill requires the browser dependency. "
            'Install it with: pip install -e ".[browser]"'
        ) from error

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.add_init_script(_CAPTURE_PAGE_RESPONSES_SCRIPT)
            page.goto(page_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            page.get_by_role("grid", name=grid_name).wait_for(timeout=PAGE_LOAD_TIMEOUT_MS)

            current_page = 1
            # The public page refreshes page one after hydration. Waiting for
            # that request prevents a pagination click from being ignored.
            items = _wait_for_captured_page_items(
                page, current_page, document_label=document_label
            )
            while True:
                documents = documents_from_items(items)
                years = [int(document.published_date[:4]) for document in documents if document.published_date]

                for document in documents:
                    if not document.published_date:
                        continue
                    year = int(document.published_date[:4])
                    if from_year <= year <= to_year:
                        yield replace(document, archive_year=str(year))

                if max_pages is not None and current_page >= max_pages:
                    return
                if years and max(years) < from_year:
                    return

                next_page = page.get_by_role("button", name="next page button", exact=True).first
                if not next_page.is_enabled():
                    return

                expected_page = current_page + 1
                next_page.click()
                items = _wait_for_captured_page_items(
                    page, expected_page, document_label=document_label
                )
                current_page = expected_page
        finally:
            browser.close()


def discover_extra_gazettes_for_year_range(
    from_year: int,
    to_year: int,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int | None = None,
) -> Iterator[DiscoveredDocument]:
    """Yield official records in the requested publication-year range.

    The public page is ordered newest first, so this stops once the next pages
    cannot contain a requested publication year.
    """

    yield from discover_documents_for_year_range(
        from_year,
        to_year,
        page_url=EXTRA_GAZETTES_URL,
        grid_name="Extra Gazettes",
        document_label="Extra Gazette",
        documents_from_items=lambda items: documents_from_extra_gazette_items(
            items, page_url=EXTRA_GAZETTES_URL
        ),
        page_size=page_size,
        max_pages=max_pages,
    )


def discover_extra_gazette_pages_for_year_range(
    from_year: int,
    to_year: int,
    *,
    start_page: int = 1,
    max_pages: int | None = None,
) -> Iterator[DiscoveredDocumentPage]:
    """Yield bounded official Extra Gazette listing pages for a resumable run.

    ``start_page`` is an official page number, not a document offset. Pages
    before it are only navigated through; their PDFs are never downloaded.
    """

    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    if start_page < 1:
        raise ValueError("start_page must be positive")
    if max_pages is not None and max_pages < 1:
        raise ValueError("max_pages must be positive when provided")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover - exercised in GitHub workflow
        raise RuntimeError(
            'Historical Extra Gazette backfill requires the browser dependency. Install it with: pip install -e ".[browser]"'
        ) from error

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.add_init_script(_CAPTURE_PAGE_RESPONSES_SCRIPT)
            page.goto(EXTRA_GAZETTES_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            page.get_by_role("grid", name="Extra Gazettes").wait_for(timeout=PAGE_LOAD_TIMEOUT_MS)

            current_page = 1
            items = _wait_for_captured_page_items(page, current_page)
            while current_page < start_page:
                next_page = page.get_by_role("button", name="next page button", exact=True).first
                if not next_page.is_enabled():
                    return
                expected_page = current_page + 1
                next_page.click()
                items = _wait_for_captured_page_items(page, expected_page)
                current_page = expected_page

            yielded_pages = 0
            while True:
                mapped_documents = documents_from_extra_gazette_items(items, page_url=EXTRA_GAZETTES_URL)
                years = [
                    int(document.published_date[:4])
                    for document in mapped_documents
                    if document.published_date
                ]
                documents = [
                    replace(document, archive_year=str(int(document.published_date[:4])))
                    for document in mapped_documents
                    if document.published_date
                    and from_year <= int(document.published_date[:4]) <= to_year
                ]
                yield DiscoveredDocumentPage(page_number=current_page, documents=documents)
                yielded_pages += 1

                if max_pages is not None and yielded_pages >= max_pages:
                    return
                if years and max(years) < from_year:
                    return

                next_page = page.get_by_role("button", name="next page button", exact=True).first
                if not next_page.is_enabled():
                    return
                expected_page = current_page + 1
                next_page.click()
                items = _wait_for_captured_page_items(page, expected_page)
                current_page = expected_page
        finally:
            browser.close()


def discover_document_pages_for_year_range(
    from_year: int, to_year: int, *, page_url: str, grid_name: str, document_label: str,
    documents_from_items: DocumentMapper, start_page: int = 1, max_pages: int | None = None,
) -> Iterator[DiscoveredDocumentPage]:
    """Yield bounded, year-filtered listing pages for any standard Printer grid."""
    if start_page < 1:
        raise ValueError("start_page must be positive")
    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:  # pragma: no cover
        raise RuntimeError(f'Historical {document_label} backfill requires: pip install -e ".[browser]"') from error
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.add_init_script(_CAPTURE_PAGE_RESPONSES_SCRIPT)
            page.goto(page_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
            page.get_by_role("grid", name=grid_name).wait_for(timeout=PAGE_LOAD_TIMEOUT_MS)
            current_page = 1
            items = _wait_for_captured_page_items(page, current_page, document_label=document_label)
            while current_page < start_page:
                next_button = page.get_by_role("button", name="next page button", exact=True).first
                if not next_button.is_enabled():
                    return
                current_page += 1
                next_button.click()
                items = _wait_for_captured_page_items(page, current_page, document_label=document_label)
            yielded = 0
            while True:
                mapped = documents_from_items(items)
                years = [int(item.published_date[:4]) for item in mapped if item.published_date]
                documents = [replace(item, archive_year=item.published_date[:4]) for item in mapped
                             if item.published_date and from_year <= int(item.published_date[:4]) <= to_year]
                yield DiscoveredDocumentPage(current_page, documents)
                yielded += 1
                if (max_pages is not None and yielded >= max_pages) or (years and max(years) < from_year):
                    return
                next_button = page.get_by_role("button", name="next page button", exact=True).first
                if not next_button.is_enabled():
                    return
                current_page += 1
                next_button.click()
                items = _wait_for_captured_page_items(page, current_page, document_label=document_label)
        finally:
            browser.close()
