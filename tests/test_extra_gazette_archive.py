import pytest

from legalai_ingestion.connectors import documents_gov_lk_archive as archive


def test_server_action_response_extracts_official_records():
    response = "\n".join(
        [
            '0:{"a":"$@1"}',
            '1:{"data":[{"id":"one","gazetteNoText":"2501/95"}]}',
        ]
    )

    assert archive._items_from_server_action(response) == [
        {"id": "one", "gazetteNoText": "2501/95"}
    ]


def test_server_action_response_requires_record_data():
    with pytest.raises(ValueError, match="no record data"):
        archive._items_from_server_action('0:{"a":"$@1"}')
