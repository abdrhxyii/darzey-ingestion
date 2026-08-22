from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DiscoveredDocument:
    """A document announced by an official source before download."""

    source: str
    document_type: str
    source_id: str
    title: str
    official_page_url: str
    source_pdf_url: str
    published_date: str | None = None
    archive_year: str | None = None
    language: str | None = None
    document_number: str | None = None


@dataclass(frozen=True)
class StoredDocument:
    """Audit record for one immutable PDF object in R2."""

    source: str
    document_type: str
    source_id: str
    title: str
    official_page_url: str
    source_pdf_url: str
    r2_object_key: str
    sha256: str
    byte_size: int
    content_type: str
    published_date: str | None
    archive_year: str | None
    language: str | None
    document_number: str | None
    downloaded_at: str
    pipeline_version: str
    status: str = "downloaded"

    @classmethod
    def from_discovered(
        cls,
        document: DiscoveredDocument,
        *,
        r2_object_key: str,
        sha256: str,
        byte_size: int,
        pipeline_version: str,
        downloaded_at: datetime | None = None,
    ) -> "StoredDocument":
        timestamp = downloaded_at or utc_now()
        return cls(
            **asdict(document),
            r2_object_key=r2_object_key,
            sha256=sha256,
            byte_size=byte_size,
            content_type="application/pdf",
            downloaded_at=timestamp.isoformat(),
            pipeline_version=pipeline_version,
        )

    def to_manifest(self) -> dict[str, Any]:
        return asdict(self)
