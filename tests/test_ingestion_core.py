import hashlib
import json

from legalai_ingestion.manifests import manifest_bytes
from legalai_ingestion.models import DiscoveredDocument, StoredDocument
from legalai_ingestion.object_keys import build_manifest_key, build_pdf_key, build_processed_key
from legalai_ingestion.storage.local import LocalObjectStore
from legalai_ingestion.connectors.documents_gov_lk import _initial_items
from legalai_ingestion.processing import PageText, build_citation_chunks, process_pdf


def test_pdf_key_is_language_specific_and_immutable():
    key = build_pdf_key("extra-gazette", "2501-95", "en", "a" * 64)
    assert key == "raw/extra-gazette/2501-95/en/2501-95--sha256-aaaaaaaaaaaaaaaa.pdf"


def test_processed_key_is_language_and_processor_specific():
    key = build_processed_key("extra-gazette", "2501-95-en", "en", "a" * 64, "legal-pdf-v1")
    assert key == (
        "derived/extra-gazette/2501-95-en/en/"
        "2501-95-en--sha256-aaaaaaaaaaaaaaaa--legal-pdf-v1.json"
    )


def test_manifest_contains_provenance_and_hash():
    discovered = DiscoveredDocument(
        source="documents.gov.lk",
        document_type="extra-gazette",
        source_id="2501-95",
        title="Example notice",
        official_page_url="https://documents.gov.lk/web/extra_gazettes",
        source_pdf_url="https://documents.gov.lk/example.pdf",
        published_date="2026-08-14",
        language="en",
        document_number="2501/95",
    )
    body = b"%PDF-example"
    digest = hashlib.sha256(body).hexdigest()
    stored = StoredDocument.from_discovered(
        discovered,
        r2_object_key=build_pdf_key("extra-gazette", "2501-95", "en", digest),
        sha256=digest,
        byte_size=len(body),
        pipeline_version="0.1.0",
    )

    manifest = json.loads(manifest_bytes(stored))
    assert manifest["sha256"] == digest
    assert manifest["official_page_url"] == discovered.official_page_url
    assert manifest["status"] == "downloaded"
    assert build_manifest_key(discovered.source, discovered.source_id, digest).startswith(
        "manifests/documents.gov.lk/2501-95/"
    )


def test_local_store_refuses_overwrite_of_changed_bytes(tmp_path):
    store = LocalObjectStore(tmp_path)
    store.put("raw/example.pdf", b"first", content_type="application/pdf", metadata={})
    store.put("raw/example.pdf", b"first", content_type="application/pdf", metadata={})

    try:
        store.put("raw/example.pdf", b"changed", content_type="application/pdf", metadata={})
    except FileExistsError:
        pass
    else:
        raise AssertionError("changed content must not overwrite an existing object")


def test_extra_gazette_payload_preserves_languages_and_public_proxy():
    payload = {
        "items": [
            {
                "id": "item-1",
                "gazetteNoText": "2501/95",
                "date": "2026-08-14T00:00:00.000Z",
                "descriptionEnglish": "Example notice: He said \"read this\"\\nNext line",
                "contents": [
                    {
                        "language": "ENGLISH",
                        "uploadedFile": "extra-gazette-content/example (E).pdf",
                    }
                ],
            }
        ],
        "total": 1,
    }
    escaped = json.dumps(json.dumps(payload, ensure_ascii=False))[1:-1]
    items_html = f'<script>\\"initialData\\":{escaped}</script>'
    assert _initial_items(items_html) == payload["items"]


def test_page_chunks_keep_exact_page_and_character_ranges():
    chunks = build_citation_chunks([PageText(page=8, text="one two three four five")], size=15, overlap=4)
    assert [chunk.page_start for chunk in chunks] == [8, 8]
    assert [chunk.page_end for chunk in chunks] == [8, 8]
    assert chunks[0].text == "one two three"
    assert chunks[1].char_start < chunks[0].char_end


def test_process_pdf_uses_native_text_without_ocr():
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Gazette Extraordinary No. 2501/95\nA legal notice for testing.")
    pdf_bytes = document.tobytes()
    document.close()

    processed = process_pdf(
        pdf_bytes,
        source_sha256="a" * 64,
        source_pdf_key="raw/extra-gazette/example.pdf",
    )

    assert processed.extraction_method == "native"
    assert processed.ocr_status == "not_needed"
    assert processed.page_count == 1
    assert processed.chunks[0].page_start == 1


def test_process_pdf_uses_ocr_when_native_text_is_insufficient(monkeypatch):
    from legalai_ingestion import processing

    extracted = iter(
        [
            [PageText(page=1, text="")],
            [PageText(page=1, text="OCR text from Extraordinary Gazette No. 2501/95")],
        ]
    )
    monkeypatch.setattr(processing, "extract_native_pages", lambda _: next(extracted))
    monkeypatch.setattr(processing, "_ocr_pdf", lambda _pdf, *, languages: b"ocr-result")

    processed = processing.process_pdf(
        b"%PDF-example",
        source_sha256="b" * 64,
        source_pdf_key="raw/extra-gazette/example.pdf",
    )

    assert processed.extraction_method == "ocr"
    assert processed.ocr_status == "completed"
    assert processed.ocr_languages == "eng+sin+tam"
    assert processed.chunks[0].page_start == 1
