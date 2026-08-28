# Agent Instructions

## Project purpose

This repository preserves original legal documents published by government
websites. The ingestion system stores the raw source files and their metadata
manifests in R2. Text extraction, OCR, chunking, embeddings, search, and RAG
are separate later stages.

The system must support multiple government websites and multiple document
types under each website.

## Repository organization

Keep source-specific behavior separate from shared ingestion behavior:

```text
src/legalai_ingestion/
├── core/                         # shared models, manifests, pipeline, state
├── storage/                      # R2 and local storage adapters
└── sources/
    ├── <government-source>/
    │   ├── common.py             # shared rules for this website
    │   ├── acts.py               # Acts discovery and normalization
    │   ├── bills.py              # Bills discovery and normalization
    │   ├── gazettes.py           # Gazette discovery and normalization
    │   └── forms.py              # Forms discovery and normalization
    └── <another-source>/
        └── ...
```

The existing connector layout may be retained while the codebase is migrated.
The same ownership rule applies: each source/document-type file owns only its
website URLs, discovery method, pagination, response parsing, metadata mapping,
and official file URL construction.

Shared code owns downloading, PDF validation, hashing, R2 keys, manifests,
checkpoints, retries, and common logging. Do not copy shared behavior into
individual source connectors.

Use matching organization for scripts, tests, and documentation:

```text
scripts/<action>_<source>.py
tests/connectors/<source>/test_<document-type>.py
docs/source-contracts/<source>.md
.github/workflows/<action>-<source>.yml
```

## Source-of-truth rules

- Treat each official government website as the source of truth for its own
  records and files.
- Use the public official interface or documented public endpoint actually
  used by that website.
- Do not use private internal hosts, guessed endpoints, stale URLs, or
  third-party snapshots as production sources.
- Keep source URLs and source metadata in every manifest.
- Do not mix records from different websites under one source identity.

## Preservation and correctness

- Preserve raw files unchanged.
- Validate that a downloaded file is the expected document type before saving.
- Calculate and record a SHA-256 checksum and byte size.
- Store an immutable raw object and its JSON manifest in R2.
- Use deterministic object keys containing source, document type, identity,
  language where applicable, and content hash.
- Make reruns idempotent: existing verified immutable objects must not be
  overwritten.
- Record progress after successful units of work so interrupted jobs resume
  safely and retry only incomplete work.

## Testing rules

- Never run tests or commands that erase databases, buckets, or stored source
  documents.
- Do not run a full production backfill as a development test.
- Prefer unit tests with saved response fixtures for parsers and normalizers.
- For live checks, use a small page/document limit and disable uploads when
  testing discovery or pagination.
- Before a production run, verify the current official response shape and the
  official download URL pattern.
- Test one source and document type at a time.
- Keep credentials in environment variables or deployment secrets; never
  commit them or print them in logs.

## Change workflow

Before changing ingestion code:

1. inspect the current connector, workflow, tests, and working-tree changes;
2. confirm the behavior against the official source when the change concerns
   discovery or downloading;
3. make the smallest source-specific change possible;
4. add or update non-destructive tests;
5. run the relevant tests and review the diff;
6. clearly report what was verified and what was not verified.

Do not silently broaden a task from one source or document type to another.
