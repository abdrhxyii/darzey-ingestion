"""Backfill official Bills archive years into private R2 storage."""

from __future__ import annotations

import argparse
import os

from legalai_ingestion.connectors.documents_gov_lk import download_pdf
from legalai_ingestion.connectors.documents_gov_lk_bills_archive import discover_bills_for_year_range
from legalai_ingestion.pipeline import store_documents
from legalai_ingestion.storage.r2 import R2ObjectStore


PIPELINE_VERSION = "0.5.0"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-year", type=int, required=True)
    parser.add_argument("--to-year", type=int, required=True)
    parser.add_argument("--minimum-download-interval-seconds", type=float, default=0.25)
    arguments = parser.parse_args()
    if arguments.from_year > arguments.to_year:
        parser.error("--from-year must be less than or equal to --to-year")
    if arguments.minimum_download_interval_seconds < 0:
        parser.error("--minimum-download-interval-seconds cannot be negative")
    store = R2ObjectStore(bucket=required("R2_BUCKET"), endpoint_url=required("R2_ENDPOINT_URL"),
                          access_key_id=required("R2_ACCESS_KEY_ID"), secret_access_key=required("R2_SECRET_ACCESS_KEY"))
    print(f"Backfilling Bills published from {arguments.from_year} to {arguments.to_year}...")
    total = store_documents(discover_bills_for_year_range(arguments.from_year, arguments.to_year), store=store,
                            download_pdf=download_pdf, pipeline_version=PIPELINE_VERSION,
                            minimum_download_interval_seconds=arguments.minimum_download_interval_seconds)
    print(f"Bills backfill complete: {total.checked} checked; {total.pdfs_uploaded} PDFs uploaded; "
          f"{total.manifests_uploaded} manifests uploaded; {total.failures} failures.")
    return 1 if total.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
