"""Official Sri Lankan Acts listed by documents.gov.lk."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from ..models import DiscoveredDocument
from .documents_gov_lk import _get, _initial_items, normalise_language


ACTS_URL = "https://documents.gov.lk/web/acts"


def documents_from_act_items(
    items: list[dict[str, object]], *, page_url: str = ACTS_URL
) -> list[DiscoveredDocument]:
    """Normalize official Acts table records into source documents."""

    discovered: list[DiscoveredDocument] = []
    for item in items:
        number = str(item.get("actNoText") or "").strip()
        if not number:
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

            discovered.append(
                DiscoveredDocument(
                    source="documents.gov.lk",
                    document_type="act",
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


def discover_acts(*, page_url: str = ACTS_URL) -> list[DiscoveredDocument]:
    """Discover the Acts on the first official listing page."""

    return documents_from_act_items(_initial_items(_get(page_url).decode("utf-8")), page_url=page_url)
