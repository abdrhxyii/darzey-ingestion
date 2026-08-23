"""Immutable source-preservation pipeline for documents discovered on official sites.

This module deliberately stops after storing original PDFs and manifests in R2.
Text extraction, OCR, legal sectioning, and database indexing are separate
future processing stages.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

from .manifests import manifest_bytes
from .models import DiscoveredDocument, StoredDocument
from .object_keys import build_manifest_key, build_pdf_key


class ObjectStore(Protocol):
    """Small storage contract shared by the R2 and local test stores."""

    def exists(self, key: str) -> bool: ...

    def put(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None: ...

    def get(self, key: str) -> bytes | None: ...

    def replace(self, key: str, body: bytes, *, content_type: str, metadata: dict[str, str]) -> None: ...


DownloadPdf = Callable[[str], bytes]


@dataclass
class IngestionSummary:
    """Outcome counts for a sync or historical-backfill run."""

    checked: int = 0
    pdfs_uploaded: int = 0
    manifests_uploaded: int = 0
    failures: int = 0

    def add(self, other: "IngestionSummary") -> None:
        self.checked += other.checked
        self.pdfs_uploaded += other.pdfs_uploaded
        self.manifests_uploaded += other.manifests_uploaded
        self.failures += other.failures


def store_documents(
    documents: Iterable[DiscoveredDocument],
    *,
    store: ObjectStore,
    download_pdf: DownloadPdf,
    pipeline_version: str,
    minimum_download_interval_seconds: float = 0.0,
) -> IngestionSummary:
    """Download and preserve documents while continuing after individual failures.

    Each object key includes source, type, document ID, language, and content
    hash. Dates stay in the manifest because their meaning differs by source.
    Re-running is safe: existing immutable PDFs and manifests are left untouched.
    """

    summary = IngestionSummary()
    next_download_at = 0.0

    for document in documents:
        summary.checked += 1
        try:
            wait_seconds = next_download_at - time.monotonic()
            if wait_seconds > 0:
                time.sleep(wait_seconds)

            next_download_at = time.monotonic() + minimum_download_interval_seconds
            body = download_pdf(document.source_pdf_url)
            digest = hashlib.sha256(body).hexdigest()
            pdf_key = build_pdf_key(
                document.source,
                document.document_type,
                document.source_id,
                document.language,
                digest,
            )
            manifest_key = build_manifest_key(
                document.source,
                document.document_type,
                document.source_id,
                digest,
            )

            if not store.exists(pdf_key):
                store.put(
                    pdf_key,
                    body,
                    content_type="application/pdf",
                    metadata={"sha256": digest},
                )
                summary.pdfs_uploaded += 1

            stored = StoredDocument.from_discovered(
                document,
                r2_object_key=pdf_key,
                sha256=digest,
                byte_size=len(body),
                pipeline_version=pipeline_version,
            )
            if not store.exists(manifest_key):
                store.put(
                    manifest_key,
                    manifest_bytes(stored),
                    content_type="application/json",
                    metadata={"sha256": digest},
                )
                summary.manifests_uploaded += 1
        except Exception as error:
            summary.failures += 1
            print(f"Failed to preserve {document.source_id} ({document.language or 'und'}): {error}")

    return summary
