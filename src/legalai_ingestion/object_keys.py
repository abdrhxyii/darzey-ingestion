from __future__ import annotations

import re


def _safe(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    return cleaned.strip("-") or "unknown"


def build_pdf_key(document_type: str, document_id: str, language: str | None, sha256: str) -> str:
    """Build an immutable, human-auditable R2 key for a PDF."""

    language_part = _safe(language or "und")
    return (
        f"raw/{_safe(document_type)}/{_safe(document_id)}/"
        f"{language_part}/{_safe(document_id)}--sha256-{sha256[:16]}.pdf"
    )


def build_manifest_key(source: str, source_id: str, sha256: str) -> str:
    return (
        f"manifests/{_safe(source)}/{_safe(source_id)}/"
        f"{_safe(source_id)}--sha256-{sha256[:16]}.json"
    )
