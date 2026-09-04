"""Verify that the official Extra Gazette page works through a small page range."""

from __future__ import annotations

import argparse

from legalai_ingestion.connectors.documents_gov_lk.archive import (
    discover_extra_gazettes_for_year_range,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=2, help="Official pages to verify (default: 2)")
    arguments = parser.parse_args()
    if arguments.pages < 1:
        parser.error("--pages must be positive")
    return arguments


def main() -> int:
    arguments = parse_arguments()
    documents = list(
        discover_extra_gazettes_for_year_range(1900, 9999, max_pages=arguments.pages)
    )
    if not documents:
        raise RuntimeError("Official Extra Gazette page returned no documents during preflight")
    print(
        f"Official Extra Gazette preflight passed: {arguments.pages} pages; "
        f"{len(documents)} PDF records; first={documents[0].document_number}; "
        f"last={documents[-1].document_number}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
