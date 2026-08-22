from legalai_ingestion.connectors import documents_gov_lk_archive as archive


def test_archive_discovery_filters_years_and_preserves_languages(monkeypatch):
    monkeypatch.setattr(
        archive,
        "_get_json",
        lambda _: {
            "data": [
                {
                    "id": "one",
                    "gazetteNoText": "2501/95",
                    "date": "2026-08-14T00:00:00.000Z",
                    "descriptionEnglish": "Example notice",
                    "contents": [
                        {"language": "ENGLISH", "uploadedFile": "notice_E.pdf"},
                        {"language": "SINHALA", "uploadedFile": "notice_S.pdf"},
                    ],
                }
            ],
            "pagination": {"totalPages": 1},
        },
    )

    documents = list(archive.discover_extra_gazettes_for_year_range(2026, 2026))

    assert [document.language for document in documents] == ["en", "si"]
    assert all(document.source_id == "2501-95" for document in documents)
    assert all(document.archive_year == "2026" for document in documents)


def test_archive_discovery_reads_each_page_once(monkeypatch):
    calls = []

    def get_json(url):
        calls.append(url)
        if "page=1" in url:
            return {
                "data": [
                    {
                        "id": "one",
                        "gazetteNoText": "2200/1",
                        "date": "2020-01-01T00:00:00.000Z",
                        "contents": [{"language": "ENGLISH", "uploadedFile": "one.pdf"}],
                    }
                ],
                "pagination": {"totalPages": 2},
            }
        return {
            "data": [
                {
                    "id": "two",
                    "gazetteNoText": "2200/2",
                    "date": "2021-01-01T00:00:00.000Z",
                    "contents": [{"language": "ENGLISH", "uploadedFile": "two.pdf"}],
                }
            ],
            "pagination": {"totalPages": 2},
        }

    monkeypatch.setattr(archive, "_get_json", get_json)

    documents = list(archive.discover_extra_gazettes_for_year_range(2021, 2021))

    assert [document.source_id for document in documents] == ["2200-2"]
    assert len(calls) == 2
