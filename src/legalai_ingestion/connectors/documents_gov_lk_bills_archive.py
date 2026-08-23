"""Historical Bills discovery through the official documents.gov.lk public page."""

from __future__ import annotations

from collections.abc import Iterator

from ..models import DiscoveredDocument
from .documents_gov_lk_archive import discover_documents_for_year_range
from .documents_gov_lk_bills import BILLS_URL, documents_from_bill_items


def discover_bills_for_year_range(
    from_year: int, to_year: int, *, page_size: int = 10, max_pages: int | None = None
) -> Iterator[DiscoveredDocument]:
    """Yield official Bills in the requested publication-year range."""

    yield from discover_documents_for_year_range(
        from_year,
        to_year,
        page_url=BILLS_URL,
        grid_name="Bills",
        document_label="Bills",
        documents_from_items=lambda items: documents_from_bill_items(items, page_url=BILLS_URL),
        page_size=page_size,
        max_pages=max_pages,
    )
