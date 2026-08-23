"""Historical General Forms through the official public page."""

from __future__ import annotations

from collections.abc import Iterator

from ..models import DiscoveredDocument
from .documents_gov_lk_archive import discover_documents_for_year_range
from .documents_gov_lk_forms import FORMS_URL, documents_from_form_items


def discover_forms_for_year_range(from_year: int, to_year: int, *, max_pages: int | None = None) -> Iterator[DiscoveredDocument]:
    yield from discover_documents_for_year_range(from_year, to_year, page_url=FORMS_URL, grid_name="General Forms",
        document_label="General Forms", documents_from_items=lambda items: documents_from_form_items(items, page_url=FORMS_URL),
        max_pages=max_pages)
