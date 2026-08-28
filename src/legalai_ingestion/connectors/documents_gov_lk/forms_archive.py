"""Historical General Forms through the official public page."""

from __future__ import annotations

from collections.abc import Iterator

from ...models import DiscoveredDocument
from .archive import DiscoveredDocumentPage, discover_documents_for_year_range, discover_document_pages_for_year_range
from .forms import FORMS_URL, documents_from_form_items


def discover_forms_for_year_range(from_year: int, to_year: int, *, max_pages: int | None = None) -> Iterator[DiscoveredDocument]:
    yield from discover_documents_for_year_range(from_year, to_year, page_url=FORMS_URL, grid_name="General Forms",
        document_label="General Forms", documents_from_items=lambda items: documents_from_form_items(items, page_url=FORMS_URL),
        max_pages=max_pages)


def discover_form_pages_for_year_range(from_year: int, to_year: int, *, start_page: int = 1, max_pages: int | None = None) -> Iterator[DiscoveredDocumentPage]:
    yield from discover_document_pages_for_year_range(from_year, to_year, page_url=FORMS_URL, grid_name="General Forms", document_label="General Forms", documents_from_items=lambda items: documents_from_form_items(items, page_url=FORMS_URL), start_page=start_page, max_pages=max_pages)
