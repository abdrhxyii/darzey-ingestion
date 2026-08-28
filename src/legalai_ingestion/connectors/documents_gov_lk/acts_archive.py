"""Historical Acts discovery through the official documents.gov.lk public page."""

from __future__ import annotations

from collections.abc import Iterator

from ...models import DiscoveredDocument
from .archive import DiscoveredDocumentPage, discover_documents_for_year_range, discover_document_pages_for_year_range
from .acts import ACTS_URL, documents_from_act_items


def discover_acts_for_year_range(
    from_year: int, to_year: int, *, page_size: int = 10, max_pages: int | None = None
) -> Iterator[DiscoveredDocument]:
    """Yield official Acts in the requested publication-year range."""

    yield from discover_documents_for_year_range(
        from_year,
        to_year,
        page_url=ACTS_URL,
        grid_name="Acts",
        document_label="Acts",
        documents_from_items=lambda items: documents_from_act_items(items, page_url=ACTS_URL),
        page_size=page_size,
        max_pages=max_pages,
    )


def discover_act_pages_for_year_range(from_year: int, to_year: int, *, start_page: int = 1, max_pages: int | None = None) -> Iterator[DiscoveredDocumentPage]:
    yield from discover_document_pages_for_year_range(from_year, to_year, page_url=ACTS_URL, grid_name="Acts", document_label="Acts", documents_from_items=lambda items: documents_from_act_items(items, page_url=ACTS_URL), start_page=start_page, max_pages=max_pages)
