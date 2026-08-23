"""Run one resumable, page-bounded Extra Gazette archive batch into R2."""

from __future__ import annotations

import argparse
import os

from legalai_ingestion.connectors.documents_gov_lk import download_pdf
from legalai_ingestion.connectors.documents_gov_lk_archive import (
    discover_extra_gazette_pages_for_year_range,
)
from legalai_ingestion.backfill_state import (
    load_extra_gazette_checkpoint,
    save_extra_gazette_checkpoint,
)
from legalai_ingestion.pipeline import IngestionSummary, store_documents
from legalai_ingestion.storage.r2 import R2ObjectStore


PIPELINE_VERSION = "0.4.0"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument(
        "--pages-per-run",
        type=int,
        default=10,
        help="Maximum official listing pages to preserve in this run (default: 10).",
    )
    parser.add_argument(
        "--minimum-download-interval-seconds",
        type=float,
        default=0.25,
        help="Minimum delay between official PDF downloads (default: 0.25).",
    )
    arguments = parser.parse_args()
    if arguments.from_year > arguments.to_year:
        parser.error("--from-year must be less than or equal to --to-year")
    if arguments.minimum_download_interval_seconds < 0:
        parser.error("--minimum-download-interval-seconds cannot be negative")
    if arguments.pages_per_run < 1:
        parser.error("--pages-per-run must be positive")
    return arguments


def main() -> int:
    arguments = parse_arguments()
    store = R2ObjectStore(
        bucket=required("R2_BUCKET"),
        endpoint_url=required("R2_ENDPOINT_URL"),
        access_key_id=required("R2_ACCESS_KEY_ID"),
        secret_access_key=required("R2_SECRET_ACCESS_KEY"),
    )
    checkpoint = load_extra_gazette_checkpoint(
        store, from_year=arguments.from_year, to_year=arguments.to_year
    )
    if checkpoint.status == "completed":
        print(
            f"Extra Gazette backfill {arguments.from_year}-{arguments.to_year} is already complete "
            f"(next page: {checkpoint.next_page})."
        )
        return 0

    print(
        f"Backfilling Extra Gazettes published from {arguments.from_year} to {arguments.to_year}, "
        f"starting at official page {checkpoint.next_page}; maximum {arguments.pages_per_run} pages."
    )
    total = IngestionSummary()
    pages_processed = 0
    for discovered_page in discover_extra_gazette_pages_for_year_range(
        arguments.from_year,
        arguments.to_year,
        start_page=checkpoint.next_page,
        max_pages=arguments.pages_per_run,
    ):
        page_summary = store_documents(
            discovered_page.documents,
            store=store,
            download_pdf=download_pdf,
            pipeline_version=PIPELINE_VERSION,
            minimum_download_interval_seconds=arguments.minimum_download_interval_seconds,
        )
        total.add(page_summary)
        if page_summary.failures:
            print(
                f"Stopped at page {discovered_page.page_number}; the checkpoint remains at "
                f"page {checkpoint.next_page} so the page can be retried safely."
            )
            break
        checkpoint = checkpoint.with_progress(next_page=discovered_page.page_number + 1)
        save_extra_gazette_checkpoint(store, checkpoint)
        pages_processed += 1
        print(f"Checkpoint saved: next official page is {checkpoint.next_page}.")

    if total.failures == 0 and pages_processed < arguments.pages_per_run:
        checkpoint = checkpoint.with_progress(next_page=checkpoint.next_page, completed=True)
        save_extra_gazette_checkpoint(store, checkpoint)
        print(f"Extra Gazette backfill {arguments.from_year}-{arguments.to_year} is complete.")

    print(
        f"Extra Gazette batch complete: {total.checked} checked; {total.pdfs_uploaded} PDFs "
        f"uploaded; {total.manifests_uploaded} manifests uploaded; {total.failures} failures."
    )
    return 1 if total.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
