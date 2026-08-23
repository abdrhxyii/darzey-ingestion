"""Run one checkpointed, five-page backfill batch for documents.gov.lk."""

from __future__ import annotations

import argparse
import os
from collections.abc import Callable, Iterator

from legalai_ingestion.backfill_state import load_checkpoint, save_checkpoint
from legalai_ingestion.connectors.documents_gov_lk import download_pdf
from legalai_ingestion.connectors.documents_gov_lk_acts_archive import discover_act_pages_for_year_range
from legalai_ingestion.connectors.documents_gov_lk_bills_archive import discover_bill_pages_for_year_range
from legalai_ingestion.connectors.documents_gov_lk_forms_archive import discover_form_pages_for_year_range
from legalai_ingestion.connectors.documents_gov_lk_gazettes_archive import discover_gazette_pages_for_year_range
from legalai_ingestion.connectors.documents_gov_lk_archive import DiscoveredDocumentPage
from legalai_ingestion.pipeline import IngestionSummary, store_documents
from legalai_ingestion.storage.r2 import R2ObjectStore

Discoverer = Callable[..., Iterator[DiscoveredDocumentPage]]
DISCOVERERS: dict[str, Discoverer] = {
    "act": discover_act_pages_for_year_range,
    "bill": discover_bill_pages_for_year_range,
    "gazette": discover_gazette_pages_for_year_range,
    "general-form": discover_form_pages_for_year_range,
}


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-type", choices=DISCOVERERS)
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument("--pages-per-run", type=int, default=5)
    parser.add_argument("--minimum-download-interval-seconds", type=float, default=0.25)
    arguments = parser.parse_args()
    if arguments.from_year > arguments.to_year or arguments.pages_per_run < 1:
        parser.error("use a valid year range and positive --pages-per-run")
    store = R2ObjectStore(bucket=required("R2_BUCKET"), endpoint_url=required("R2_ENDPOINT_URL"), access_key_id=required("R2_ACCESS_KEY_ID"), secret_access_key=required("R2_SECRET_ACCESS_KEY"))
    checkpoint = load_checkpoint(store, document_type=arguments.document_type, from_year=arguments.from_year, to_year=arguments.to_year)
    if checkpoint.status == "completed":
        print(f"{arguments.document_type} backfill is already complete (next page: {checkpoint.next_page}).")
        return 0
    total = IngestionSummary()
    processed = 0
    for discovered_page in DISCOVERERS[arguments.document_type](arguments.from_year, arguments.to_year, start_page=checkpoint.next_page, max_pages=arguments.pages_per_run):
        summary = store_documents(discovered_page.documents, store=store, download_pdf=download_pdf, pipeline_version="0.8.0", minimum_download_interval_seconds=arguments.minimum_download_interval_seconds)
        total.add(summary)
        if summary.failures:
            print(f"Stopped at page {discovered_page.page_number}; retry begins at page {checkpoint.next_page}.")
            break
        checkpoint = checkpoint.with_progress(next_page=discovered_page.page_number + 1)
        save_checkpoint(store, checkpoint)
        processed += 1
        print(f"Checkpoint saved: next official page is {checkpoint.next_page}.")
    if total.failures == 0 and processed < arguments.pages_per_run:
        checkpoint = checkpoint.with_progress(next_page=checkpoint.next_page, completed=True)
        save_checkpoint(store, checkpoint)
        print(f"{arguments.document_type} backfill is complete.")
    print(f"{arguments.document_type} batch complete: {total.checked} checked; {total.pdfs_uploaded} PDFs uploaded; {total.failures} failures.")
    return 1 if total.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
