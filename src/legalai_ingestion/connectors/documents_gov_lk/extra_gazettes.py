from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from ...models import DiscoveredDocument
from .common import download_pdf, get, initial_items, normalise_language

EXTRA_GAZETTES_URL = "https://documents.gov.lk/web/extra_gazettes"
def documents_from_extra_gazette_items(
    items: list[dict[str, object]], *, page_url: str, archive_year: str | None = None
) -> list[DiscoveredDocument]:
    """Normalize official Extra Gazette API records into source documents."""

    discovered: list[DiscoveredDocument] = []
    for item in items:
        item_id = str(item.get("id") or "").strip()
        number = str(item.get("gazetteNoText") or "").strip()
        if not item_id or not number:
            continue

        title = str(item.get("descriptionEnglish") or item.get("descriptionSinhala") or number)
        published = item.get("date")
        published_date = None
        if isinstance(published, str) and published:
            published_date = datetime.fromisoformat(published.replace("Z", "+00:00")).date().isoformat()

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

            # This is the public proxy used by the official site's own buttons.
            pdf_url = "https://documents.gov.lk/api/content-file-proxy?file=" + quote(
                "/" + uploaded_file, safe="/"
            )
            discovered.append(
                DiscoveredDocument(
                    source="documents.gov.lk",
                    document_type="extra-gazette",
                    source_id=number.replace("/", "-"),
                    title=title,
                    official_page_url=page_url,
                    source_pdf_url=pdf_url,
                    published_date=published_date,
                    archive_year=archive_year,
                    language=language,
                    document_number=number,
                )
            )

    return discovered


def discover_extra_gazettes(*, page_url: str = EXTRA_GAZETTES_URL) -> list[DiscoveredDocument]:
    """Discover the current page shown on the official Extra Gazette site."""

    return documents_from_extra_gazette_items(initial_items(get(page_url).decode("utf-8")), page_url=page_url)
