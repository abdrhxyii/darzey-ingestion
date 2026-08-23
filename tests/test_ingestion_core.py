import hashlib
import json

from legalai_ingestion.manifests import manifest_bytes
from legalai_ingestion.models import DiscoveredDocument, StoredDocument
from legalai_ingestion.object_keys import build_manifest_key, build_pdf_key
from legalai_ingestion.pipeline import store_documents
from legalai_ingestion.storage.local import LocalObjectStore
from legalai_ingestion.connectors.documents_gov_lk import _initial_items
from legalai_ingestion.connectors.documents_gov_lk_acts import documents_from_act_items
from legalai_ingestion.connectors.documents_gov_lk_bills import documents_from_bill_items
from legalai_ingestion.connectors.documents_gov_lk_gazettes import (
    documents_from_gazette_issue_html,
    listed_gazette_dates,
)
from legalai_ingestion.connectors.documents_gov_lk_forms import documents_from_form_items


def test_pdf_key_is_language_specific_and_immutable():
    key = build_pdf_key("documents.gov.lk", "extra-gazette", "2501-95", "en", "a" * 64)
    assert key == (
        "raw/documents.gov.lk/extra-gazette/2501-95/en/"
        "2501-95--sha256-aaaaaaaaaaaaaaaa.pdf"
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
        r2_object_key=build_pdf_key(
            "documents.gov.lk", "extra-gazette", "2501-95", "en", digest
        ),
        sha256=digest,
        byte_size=len(body),
        pipeline_version="0.1.0",
    )

    manifest = json.loads(manifest_bytes(stored))
    assert manifest["sha256"] == digest
    assert manifest["official_page_url"] == discovered.official_page_url
    assert manifest["status"] == "downloaded"
    assert build_manifest_key(
        discovered.source, discovered.document_type, discovered.source_id, digest
    ).startswith(
        "manifests/documents.gov.lk/extra-gazette/2501-95/"
    )


def test_store_documents_creates_immutable_pdf_and_manifest(tmp_path):
    store = LocalObjectStore(tmp_path)
    document = DiscoveredDocument(
        source="documents.gov.lk",
        document_type="extra-gazette",
        source_id="2501-95",
        title="Example notice",
        official_page_url="https://documents.gov.lk/view/egz/egz_2026.html",
        source_pdf_url="https://documents.gov.lk/example.pdf",
        published_date="2026-08-14",
        archive_year="2026",
        language="en",
        document_number="2501/95",
    )

    summary = store_documents(
        [document],
        store=store,
        download_pdf=lambda _: b"%PDF-example",
        pipeline_version="test",
    )

    assert summary.checked == 1
    assert summary.pdfs_uploaded == 1
    assert summary.manifests_uploaded == 1
    assert summary.failures == 0
    assert list((tmp_path / "raw" / "documents.gov.lk" / "extra-gazette" / "2501-95").rglob("*.pdf"))
    assert list((tmp_path / "manifests" / "documents.gov.lk" / "extra-gazette" / "2501-95").rglob("*.json"))


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


def test_act_payload_preserves_languages_and_public_proxy():
    documents = documents_from_act_items(
        [
            {
                "actNoText": "18/2026",
                "date": "2026-08-04T00:00:00.000Z",
                "descriptionEnglish": "Convention on the Suppression of Terrorist Financing (Amendment)",
                "contents": [
                    {"language": "ENGLISH", "uploadedFile": "act-content/act (E).pdf"},
                    {"language": "SINHALA", "uploadedFile": "act-content/act (S).pdf"},
                    {"language": "TAMIL", "uploadedFile": "act-content/act (T).pdf"},
                ],
            }
        ]
    )

    assert [document.language for document in documents] == ["en", "si", "ta"]
    assert all(document.document_type == "act" for document in documents)
    assert all(document.source_id == "18-2026" for document in documents)
    assert documents[0].published_date == "2026-08-04"
    assert documents[0].source_pdf_url.endswith("act-content/act%20%28E%29.pdf")


def test_bill_payload_preserves_languages_and_public_proxy():
    documents = documents_from_bill_items(
        [{"billNoText": "57/2026", "date": "2026-08-07T00:00:00.000Z",
          "descriptionEnglish": "Twenty Second Amendment to the Constitution - GS",
          "contents": [{"language": "ENGLISH", "uploadedFile": "bill-content/57-2026_E.pdf"},
                       {"language": "SINHALA", "uploadedFile": "bill-content/57-2026_S.pdf"},
                       {"language": "TAMIL", "uploadedFile": "bill-content/57-2026_T.pdf"}]}]
    )

    assert [document.language for document in documents] == ["en", "si", "ta"]
    assert all(document.document_type == "bill" for document in documents)
    assert all(document.source_id == "57-2026" for document in documents)
    assert documents[0].published_date == "2026-08-07"
    assert documents[0].source_pdf_url.endswith("bill-content/57-2026_E.pdf")


def test_gazette_payload_uses_date_part_and_section_identity():
    dates_payload = 'x{"dates":["2026-08-21T00:00:00.000Z"]}'
    issue_payload = (
        'x{"partContentArray":{"1":{"2":[{"partNo":1,"sectionId":2,'
        '"section":"Advertising","language":"ENGLISH","uploadedFile":"gazette-content/example.pdf",'
        '"uploadedFileFormat":"PDF"},{"uploadedFile":"gazette-content/example.epub",'
        '"uploadedFileFormat":"EPUB"}]}}}'
    )
    dates_html = f'<script>self.__next_f.push({json.dumps([1, dates_payload])})</script>'
    issue_html = f'<script>self.__next_f.push({json.dumps([1, issue_payload])})</script>'

    assert listed_gazette_dates(dates_html) == ["2026-08-21"]
    documents = documents_from_gazette_issue_html(
        issue_html, issue_date="2026-08-21", page_url="https://documents.gov.lk/web/Gazette?date=2026-08-21"
    )
    assert len(documents) == 1
    assert documents[0].source_id == "2026-08-21-part-1-section-2"
    assert documents[0].language == "en"


def test_general_form_payload_uses_form_number_identity():
    documents = documents_from_form_items([{"formNoText":"0/21","date":"2026-07-08T00:00:00.000Z","descriptionEnglish":"Railway Warrant","contents":[{"language":"ENGLISH","uploadedFile":"form-content/00-0021_E.pdf"}]}])
    assert len(documents) == 1
    assert documents[0].document_type == "general-form"
    assert documents[0].source_id == "0-21"
    assert documents[0].language == "en"
