from legalai_ingestion.connectors import documents_gov_lk_archive as archive


def test_archive_year_discovery_includes_1900s_and_2000s(monkeypatch):
    monkeypatch.setattr(
        archive,
        "_get_html",
        lambda _: '<a href="egz_1998.html">1998</a><a href="egz_2024.html">2024</a>',
    )

    assert archive.discover_extra_gazette_archive_years() == [1998, 2024]


def test_archive_year_discovery_preserves_document_language_and_year(monkeypatch):
    monkeypatch.setattr(
        archive,
        "_get_html",
        lambda _: """
        <table><tr><td>2501/95</td><td>2026-08-14</td><td>Example notice</td>
        <td><a href="notice_E.pdf">English</a><a href="notice_S.pdf">Sinhala</a></td></tr></table>
        """,
    )

    documents = archive.discover_extra_gazettes_for_year(2026)

    assert [document.language for document in documents] == ["en", "si"]
    assert all(document.source_id == "2501-95" for document in documents)
    assert all(document.archive_year == "2026" for document in documents)
