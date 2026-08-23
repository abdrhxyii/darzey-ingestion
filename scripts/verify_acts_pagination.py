"""Verify that the official Acts page works through a small page range."""

from __future__ import annotations

import argparse

from legalai_ingestion.connectors.documents_gov_lk_acts_archive import discover_acts_for_year_range


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=2)
    arguments = parser.parse_args()
    documents = list(discover_acts_for_year_range(1900, 9999, max_pages=arguments.pages))
    if not documents:
        raise RuntimeError("Official Acts page returned no documents during preflight")
    print(
        f"Official Acts preflight passed: {arguments.pages} pages; {len(documents)} files; "
        f"first={documents[0].document_number}; last={documents[-1].document_number}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
