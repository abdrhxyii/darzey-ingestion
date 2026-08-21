from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..models import DiscoveredDocument

EXTRA_GAZETTES_URL = "https://documents.gov.lk/web/extra_gazettes"
USER_AGENT = "LegalAI-ingestion/0.1 (+https://github.com/abdrhxyii/darzey-ingestion)"


def _get(url: str, *, timeout: int = 60) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _initial_items(page_html: str) -> list[dict[str, object]]:
    """Read the server-rendered initialData used by the official Next.js page."""

    marker = r'\\"initialData\\":'
    match = re.search(
        marker + r'\{\\"items\\"\s*:\s*(\[.*?\])\s*,\s*\\"total\\"\s*:\s*\d+\}',
        page_html,
        re.S,
    )
    if not match:
        raise ValueError("Could not find Extra Gazette initialData in official page")

    # The Next.js RSC payload escapes the JSON quotes once inside its script.
    return json.loads(match.group(1).replace(r'\"', '"'))


def discover_extra_gazettes(*, page_url: str = EXTRA_GAZETTES_URL) -> list[DiscoveredDocument]:
    items = _initial_items(_get(page_url).decode("utf-8"))
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
            language = str(content.get("language") or "").strip().lower()
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
                    source_id=f"{item_id}-{language}",
                    title=title,
                    official_page_url=page_url,
                    source_pdf_url=pdf_url,
                    published_date=published_date,
                    language=language,
                    document_number=number,
                )
            )

    return discovered


def download_pdf(url: str) -> bytes:
    body = _get(url)
    if not body.startswith(b"%PDF"):
        raise ValueError(f"Official download was not a PDF: {url}")
    return body
