"""Official General Forms listed by documents.gov.lk."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from ..models import DiscoveredDocument
from .documents_gov_lk import _get, _initial_items, normalise_language


FORMS_URL = "https://documents.gov.lk/web/general_forms"


def documents_from_form_items(items: list[dict[str, object]], *, page_url: str = FORMS_URL) -> list[DiscoveredDocument]:
    """Normalize official General Forms records into source documents."""

    documents: list[DiscoveredDocument] = []
    for item in items:
        number = str(item.get("formNoText") or "").strip()
        if not number:
            continue
        published = item.get("date")
        published_date = datetime.fromisoformat(published.replace("Z", "+00:00")).date().isoformat() if isinstance(published, str) and published else None
        title = str(item.get("descriptionEnglish") or item.get("descriptionSinhala") or number)
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
            documents.append(DiscoveredDocument(
                source="documents.gov.lk", document_type="general-form", source_id=number.replace("/", "-"),
                title=title, official_page_url=page_url,
                source_pdf_url="https://documents.gov.lk/api/content-file-proxy?file=" + quote("/" + uploaded_file, safe="/"),
                published_date=published_date, language=language, document_number=number,
            ))
    return documents


def discover_forms(*, page_url: str = FORMS_URL) -> list[DiscoveredDocument]:
    return documents_from_form_items(_initial_items(_get(page_url).decode("utf-8")), page_url=page_url)
