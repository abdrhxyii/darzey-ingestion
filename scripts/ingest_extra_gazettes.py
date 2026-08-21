"""Collect the first page of official Extra Gazettes into private R2 storage."""

from __future__ import annotations

import hashlib
import os

from legalai_ingestion.connectors.documents_gov_lk import download_pdf, discover_extra_gazettes
from legalai_ingestion.manifests import manifest_bytes
from legalai_ingestion.models import StoredDocument
from legalai_ingestion.object_keys import build_manifest_key, build_pdf_key, build_processed_key
from legalai_ingestion.processing import PROCESSOR_VERSION, process_pdf
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
    processed_count = 0
    ocr_count = 0
    ocr_problem_count = 0
    ocr_languages = os.environ.get("OCR_LANGUAGES", "eng+sin+tam").strip() or "eng+sin+tam"

    for document in documents:
        body = download_pdf(document.source_pdf_url)
        digest = hashlib.sha256(body).hexdigest()
        pdf_key = build_pdf_key(document.document_type, document.source_id, document.language, digest)
        manifest_key = build_manifest_key(document.source, document.source_id, digest)

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

        processed_key = build_processed_key(
            document.document_type,
            document.source_id,
            document.language,
            digest,
            PROCESSOR_VERSION,
        )
        if not store.exists(processed_key):
            processed = process_pdf(
                body,
                source_sha256=digest,
                source_pdf_key=pdf_key,
                ocr_languages=ocr_languages,
            )
            store.put(
                processed_key,
                processed.to_bytes(),
                content_type="application/json",
                metadata={
                    "source-sha256": digest,
                    "processor-version": PROCESSOR_VERSION,
                    "ocr-status": processed.ocr_status,
                },
            )
            processed_count += 1
            if processed.ocr_status == "completed":
                ocr_count += 1
            elif processed.ocr_status != "not_needed":
                ocr_problem_count += 1
        stored_count += 1

    print(
        "Extra Gazette ingestion complete: "
        f"{stored_count} language documents checked; "
        f"{processed_count} new processing artifacts; "
        f"{ocr_count} OCR completed; {ocr_problem_count} OCR issues."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
