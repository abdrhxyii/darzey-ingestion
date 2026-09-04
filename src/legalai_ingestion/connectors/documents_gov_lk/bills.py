"""Official Sri Lankan Bills listed by documents.gov.lk."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from ...models import DiscoveredDocument
from .common import get, initial_items, normalise_language


BILLS_URL = "https://documents.gov.lk/web/bills"


def documents_from_bill_items(
    items: list[dict[str, object]], *, page_url: str = BILLS_URL
) -> list[DiscoveredDocument]:
    """Normalize official Bills table records into source documents."""

    discovered: list[DiscoveredDocument] = []
    for item in items:
        number = str(item.get("billNoText") or "").strip()
        if not number:
            continue
        title = str(item.get("descriptionEnglish") or item.get("descriptionSinhala") or number)
        published = item.get("date")
        published_date = (
            datetime.fromisoformat(published.replace("Z", "+00:00")).date().isoformat()
            if isinstance(published, str) and published
            else None
        )
        contents = item.get("contents")
        if not isinstance(contents, list):
            continue
        for content in contents:
            if not isinstance(content, dict):
                continue
            uploaded_file = content.get("uploadedFile")
            language = normalise_language(str(content.get("language") or ""))
            if not isinstance(uploaded_file, str) or not uploaded_file or not language:
                continue
            discovered.append(
                DiscoveredDocument(
                    source="documents.gov.lk",
                    document_type="bill",
                    source_id=number.replace("/", "-"),
                    title=title,
                    official_page_url=page_url,
                    source_pdf_url="https://documents.gov.lk/api/content-file-proxy?file="
                    + quote("/" + uploaded_file, safe="/"),
                    published_date=published_date,
                    language=language,
                    document_number=number,
                )
            )
    return discovered


def discover_bills(*, page_url: str = BILLS_URL) -> list[DiscoveredDocument]:
    """Discover Bills on the first official listing page."""

    return documents_from_bill_items(initial_items(get(page_url).decode("utf-8")), page_url=page_url)
