"""Collect the first page of official Extra Gazettes into private R2 storage."""

from __future__ import annotations

import hashlib
import os

from legalai_ingestion.connectors.documents_gov_lk import download_pdf, discover_extra_gazettes
from legalai_ingestion.manifests import manifest_bytes
from legalai_ingestion.models import StoredDocument
from legalai_ingestion.object_keys import build_manifest_key, build_pdf_key, publication_year
from legalai_ingestion.storage.r2 import R2ObjectStore


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    store = R2ObjectStore(
        bucket=required("R2_BUCKET"),
        endpoint_url=required("R2_ENDPOINT_URL"),
        access_key_id=required("R2_ACCESS_KEY_ID"),
        secret_access_key=required("R2_SECRET_ACCESS_KEY"),
    )
    documents = discover_extra_gazettes()
    stored_count = 0

    for document in documents:
        body = download_pdf(document.source_pdf_url)
        digest = hashlib.sha256(body).hexdigest()
        year = publication_year(document.published_date)
        pdf_key = build_pdf_key(
            document.source,
            document.document_type,
            year,
            document.source_id,
            document.language,
            digest,
        )
        manifest_key = build_manifest_key(
            document.source, document.document_type, year, document.source_id, digest
        )

        if not store.exists(pdf_key):
            store.put(pdf_key, body, content_type="application/pdf", metadata={"sha256": digest})

        stored = StoredDocument.from_discovered(
            document,
            r2_object_key=pdf_key,
            sha256=digest,
            byte_size=len(body),
            pipeline_version="0.2.0",
        )
        if not store.exists(manifest_key):
            store.put(
                manifest_key,
                manifest_bytes(stored),
                content_type="application/json",
                metadata={"sha256": digest},
            )
        stored_count += 1

    print(f"Extra Gazette ingestion complete: {stored_count} language documents checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
