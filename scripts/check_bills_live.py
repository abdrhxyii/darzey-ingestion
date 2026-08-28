"""Safely verify live Bills discovery without downloading or uploading documents."""

from __future__ import annotations

import argparse

from legalai_ingestion.connectors.documents_gov_lk.bills_archive import (
    discover_bill_pages_for_year_range,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-year", type=int, default=2026)
    parser.add_argument("--to-year", type=int, default=2026)
    parser.add_argument("--pages", type=int, default=3)
    arguments = parser.parse_args()
    if arguments.pages < 1:
        parser.error("--pages must be positive")

    pages = list(
        discover_bill_pages_for_year_range(
            arguments.from_year,
            arguments.to_year,
            start_page=1,
            max_pages=arguments.pages,
        )
    )
    for page in pages:
        numbers = sorted({document.document_number for document in page.documents})
        print(f"page={page.page_number} documents={len(page.documents)} bills={numbers}")
    if [page.page_number for page in pages] != list(range(1, arguments.pages + 1)):
        raise RuntimeError("Live Bills pagination did not return every requested page")
    print("Live Bills discovery check passed; no PDFs were downloaded or uploaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
