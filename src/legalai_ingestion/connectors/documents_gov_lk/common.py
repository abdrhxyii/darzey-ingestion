"""Shared helpers for the documents.gov.lk connectors."""

from __future__ import annotations

import json
import re
from urllib.request import Request, urlopen


USER_AGENT = "LegalAI-ingestion/0.1 (+https://github.com/abdrhxyii/darzey-ingestion)"


def normalise_language(value: str) -> str:
    language = value.strip().lower()
    return {"english": "en", "sinhala": "si", "sinhalese": "si", "tamil": "ta"}.get(
        language, language
    )


def get(url: str, *, timeout: int = 60) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def initial_items(page_html: str) -> list[dict[str, object]]:
    """Read server-rendered initialData used by the official Next.js pages."""

    marker = r'\\"initialData\\":'
    match = re.search(
        marker + r'\{\\"items\\"\s*:\s*(\[.*?\])\s*,\s*\\"total\\"\s*:\s*\d+\}',
        page_html,
        re.S,
    )
    if not match:
        raise ValueError("Could not find initialData in official page")
    try:
        decoded_items = json.loads(f'"{match.group(1)}"')
        return json.loads(decoded_items)
    except json.JSONDecodeError as error:
        raise ValueError("Could not decode initialData") from error


def download_pdf(url: str) -> bytes:
    body = get(url)
    if not body.startswith(b"%PDF"):
        raise ValueError(f"Official download was not a PDF: {url}")
    return body
