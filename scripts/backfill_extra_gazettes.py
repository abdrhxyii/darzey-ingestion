"""Backfill official Extra Gazette archive years into private R2 storage.

This command is intentionally separate from the recurring latest-document sync.
Run small year ranges so interrupted work can be safely re-run.
"""

from __future__ import annotations

import argparse
import os

from legalai_ingestion.connectors.documents_gov_lk import download_pdf
from legalai_ingestion.connectors.documents_gov_lk_archive import (
    discover_extra_gazette_archive_years,
    discover_extra_gazettes_for_year,
)
from legalai_ingestion.pipeline import IngestionSummary, store_documents
from legalai_ingestion.storage.r2 import R2ObjectStore


PIPELINE_VERSION = "0.3.0"


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
    return arguments


def main() -> int:
    arguments = parse_arguments()
    store = R2ObjectStore(
        bucket=required("R2_BUCKET"),
        endpoint_url=required("R2_ENDPOINT_URL"),
        access_key_id=required("R2_ACCESS_KEY_ID"),
        secret_access_key=required("R2_SECRET_ACCESS_KEY"),
    )
    years = [
        year
        for year in discover_extra_gazette_archive_years()
        if arguments.from_year <= year <= arguments.to_year
    ]
    if not years:
        raise RuntimeError("No official Extra Gazette archive years matched the requested range")

    total = IngestionSummary()
    for year in years:
        print(f"Backfilling Extra Gazettes for {year}...")
        summary = store_documents(
            discover_extra_gazettes_for_year(year),
            store=store,
            download_pdf=download_pdf,
            pipeline_version=PIPELINE_VERSION,
            minimum_download_interval_seconds=arguments.minimum_download_interval_seconds,
        )
        total.add(summary)
        print(
            f"{year}: {summary.checked} checked; {summary.pdfs_uploaded} PDFs uploaded; "
            f"{summary.manifests_uploaded} manifests uploaded; {summary.failures} failures."
        )

    print(
        f"Extra Gazette backfill complete: {total.checked} checked; {total.pdfs_uploaded} PDFs "
        f"uploaded; {total.manifests_uploaded} manifests uploaded; {total.failures} failures."
    )
    return 1 if total.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
