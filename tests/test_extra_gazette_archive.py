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


def test_server_action_response_extracts_compact_official_records():
    response = '0:{"a":"$@1"} 1:{"data":[{"id":"one","gazetteNoText":"2501/95"}]}'

    assert archive._items_from_server_action(response) == [
        {"id": "one", "gazetteNoText": "2501/95"}
    ]


def test_server_action_response_requires_record_data():
    with pytest.raises(ValueError, match="no record data"):
        archive._items_from_server_action('0:{"a":"$@1"}')


def test_wait_for_page_items_skips_ancillary_action_response():
    class Page:
        def evaluate(self, *_):
            return [
                {"url": "/web/extra_gazettes", "status": 200, "text": '0:{"a":"$@1"}'},
                {"url": "/web/extra_gazettes", "status": 200, "text": '1:{"data":[{"id":"one"}]}'},
            ]

        def wait_for_timeout(self, _):
            raise AssertionError("record data was already available")

    assert archive._wait_for_captured_page_items(Page(), 2) == [{"id": "one"}]
