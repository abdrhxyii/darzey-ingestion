"""Sync the current official Bills listing into private R2 storage."""

from __future__ import annotations

import os

from legalai_ingestion.connectors.documents_gov_lk import download_pdf
from legalai_ingestion.connectors.documents_gov_lk_bills import discover_bills
from legalai_ingestion.pipeline import store_documents
from legalai_ingestion.storage.r2 import R2ObjectStore


PIPELINE_VERSION = "0.5.0"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main() -> int:
    store = R2ObjectStore(
        bucket=required("R2_BUCKET"), endpoint_url=required("R2_ENDPOINT_URL"),
        access_key_id=required("R2_ACCESS_KEY_ID"), secret_access_key=required("R2_SECRET_ACCESS_KEY"),
    )
    summary = store_documents(discover_bills(), store=store, download_pdf=download_pdf,
                              pipeline_version=PIPELINE_VERSION, minimum_download_interval_seconds=0.25)
    print(f"Bills sync complete: {summary.checked} checked; {summary.pdfs_uploaded} PDFs uploaded; "
          f"{summary.manifests_uploaded} manifests uploaded; {summary.failures} failures.")
    return 1 if summary.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
