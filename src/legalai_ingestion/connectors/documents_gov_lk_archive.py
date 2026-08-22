"""Paginated historical Extra Gazette discovery from the current official data API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..models import DiscoveredDocument
from .documents_gov_lk import EXTRA_GAZETTES_URL, USER_AGENT, documents_from_extra_gazette_items


# This is the public API configured by the Department of Government Printing's
# current Extra Gazette page. It replaces the retired /view/egz HTML archive.
EXTRA_GAZETTE_RECORDS_URL = "http://203.143.21.148:4500/website-data/extra-gazette/get-all"
DEFAULT_PAGE_SIZE = 100


def _get_json(url: str) -> dict[str, object]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Official Extra Gazette API returned a non-object response")
    return payload


def _page_url(page: int, page_size: int) -> str:
    return EXTRA_GAZETTE_RECORDS_URL + "?" + urlencode({"limit": page_size, "page": page})


def discover_extra_gazettes_for_year_range(
    from_year: int, to_year: int, *, page_size: int = DEFAULT_PAGE_SIZE
) -> Iterator[DiscoveredDocument]:
    """Yield official records in the requested publication-year range, one API page at a time."""

    if from_year > to_year:
        raise ValueError("from_year must be less than or equal to to_year")
    if page_size < 1:
        raise ValueError("page_size must be positive")

    page = 1
    while True:
        payload = _get_json(_page_url(page, page_size))
        items = payload.get("data")
        if not isinstance(items, list):
            raise ValueError("Official Extra Gazette API response has no data list")
        typed_items = [item for item in items if isinstance(item, dict)]

        for document in documents_from_extra_gazette_items(typed_items, page_url=EXTRA_GAZETTES_URL):
            if not document.published_date:
                continue
            year = int(document.published_date[:4])
            if from_year <= year <= to_year:
                yield replace(document, archive_year=str(year))

        pagination = payload.get("pagination")
        if not isinstance(pagination, dict):
            raise ValueError("Official Extra Gazette API response has no pagination object")
        total_pages = pagination.get("totalPages")
        if not isinstance(total_pages, int) or total_pages < page:
            raise ValueError("Official Extra Gazette API response has an invalid totalPages value")
        if page >= total_pages:
            return
        page += 1
