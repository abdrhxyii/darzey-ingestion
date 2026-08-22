import hashlib
import json

from legalai_ingestion.manifests import manifest_bytes
from legalai_ingestion.models import DiscoveredDocument, StoredDocument
from legalai_ingestion.object_keys import build_manifest_key, build_pdf_key, publication_year
from legalai_ingestion.storage.local import LocalObjectStore
from legalai_ingestion.connectors.documents_gov_lk import _archive_documents, _initial_items


def test_pdf_key_is_language_specific_and_immutable():
    key = build_pdf_key(
        "documents.gov.lk", "extra-gazette", "2026", "2501-95", "en", "a" * 64
    )
    assert key == (
        "raw/documents.gov.lk/extra-gazette/2026/2501-95/en/"
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
            "documents.gov.lk", "extra-gazette", "2026", "2501-95", "en", digest
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
        discovered.source, discovered.document_type, publication_year(discovered.published_date), discovered.source_id, digest
    ).startswith(
        "manifests/documents.gov.lk/extra-gazette/2026/2501-95/"
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


def test_archive_discovery_preserves_year_and_language_specific_pdf_urls():
    html = """
    <table><tr>
      <td>2424/49</td><td>2025-02-19</td><td>Land Acquisition Notice</td>
      <td><a href="../extra-gazettes/2025/2/2424-49_E.pdf">English</a>
          <a href="../extra-gazettes/2025/2/2424-49_S.pdf">Sinhala</a>
          <a href="../extra-gazettes/2025/2/2424-49_T.pdf">Tamil</a></td>
    </tr></table>
    """
    documents = _archive_documents(
        html,
        year=2025,
        page_url="https://www.documents.gov.lk/view/egz/egz_2025.html",
    )

    assert [document.language for document in documents] == ["en", "si", "ta"]
    assert all(document.archive_year == "2025" for document in documents)
    assert all(document.source_id == "2424-49" for document in documents)
    assert documents[0].source_pdf_url.endswith("2424-49_E.pdf")
