"""Backfill official Extra Gazette PDFs from the Government Printer archive."""

from __future__ import annotations

import argparse
import hashlib
import os
import time

from legalai_ingestion.connectors.documents_gov_lk import (
    discover_extra_gazettes_for_year,
    download_pdf,
)
from legalai_ingestion.manifests import manifest_bytes
from legalai_ingestion.models import DiscoveredDocument, StoredDocument
from legalai_ingestion.object_keys import build_manifest_key, build_pdf_key, publication_year
from legalai_ingestion.storage.r2 import R2ObjectStore


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_years(value: str) -> list[int]:
    years: set[int] = set()
    for part in value.split(","):
        start_text, separator, end_text = part.strip().partition("-")
        if not start_text.isdigit():
            raise ValueError(f"Invalid year: {part}")
        start = int(start_text)
        end = int(end_text) if separator and end_text.isdigit() else start
        if separator and not end_text.isdigit():
            raise ValueError(f"Invalid year range: {part}")
        if start > end or start < 1900 or end > 2100:
            raise ValueError(f"Invalid year range: {part}")
        years.update(range(start, end + 1))
    return sorted(years)


def store_document(store: R2ObjectStore, document: DiscoveredDocument) -> bool:
    body = download_pdf(document.source_pdf_url)
    digest = hashlib.sha256(body).hexdigest()
    year = document.archive_year or publication_year(document.published_date)
    pdf_key = build_pdf_key(
        document.source, document.document_type, year, document.source_id, document.language, digest
    )
    manifest_key = build_manifest_key(
        document.source, document.document_type, year, document.source_id, digest
    )

    wrote = False
    if not store.exists(pdf_key):
        store.put(pdf_key, body, content_type="application/pdf", metadata={"sha256": digest})
        wrote = True

    stored = StoredDocument.from_discovered(
        document,
        r2_object_key=pdf_key,
        sha256=digest,
        byte_size=len(body),
        pipeline_version="0.3.0",
    )
    if not store.exists(manifest_key):
        store.put(
            manifest_key,
            manifest_bytes(stored),
            content_type="application/json",
            metadata={"sha256": digest},
        )
        wrote = True
    return wrote


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", required=True, help="Comma-separated years or ranges, e.g. 2010-2026")
    parser.add_argument("--delay-seconds", type=float, default=0.25)
    parser.add_argument("--max-documents", type=int, default=0, help="Optional limit; 0 means no limit")
    args = parser.parse_args()
    if args.delay_seconds < 0 or args.max_documents < 0:
        parser.error("delay-seconds and max-documents must be non-negative")

    store = R2ObjectStore(
        bucket=required("R2_BUCKET"),
        endpoint_url=required("R2_ENDPOINT_URL"),
        access_key_id=required("R2_ACCESS_KEY_ID"),
        secret_access_key=required("R2_SECRET_ACCESS_KEY"),
    )
    checked = written = failed = 0

    for year in parse_years(args.years):
        documents = discover_extra_gazettes_for_year(year)
        print(f"{year}: discovered {len(documents)} language PDFs")
        for document in documents:
            if args.max_documents and checked >= args.max_documents:
                print(f"Backfill stopped at requested limit of {args.max_documents} documents.")
                print(f"Checked {checked}; wrote {written}; failed {failed}.")
                return 1 if failed else 0
            try:
                written += store_document(store, document)
            except Exception as error:  # Continue so a single bad official file does not stop the archive.
                failed += 1
                print(f"FAILED {document.source_pdf_url}: {error}")
            checked += 1
            if args.delay_seconds:
                time.sleep(args.delay_seconds)

    print(f"Extra Gazette backfill complete: checked {checked}; wrote {written}; failed {failed}.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
