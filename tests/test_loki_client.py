import json
from unittest.mock import patch
from urllib.error import URLError

import pytest

from app.evidence.loki import LokiClient


class MockResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def test_query_returns_log_evidence():
    response = {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [
                {
                    "stream": {
                        "service_name": "app",
                        "detected_level": "info",
                    },
                    "values": [
                        [
                            "1789150000000000000",
                            '{"message":"request completed"}',
                        ]
                    ],
                }
            ],
        },
    }

    client = LokiClient("http://loki:3100")

    with patch(
        "app.evidence.loki.urlopen",
        return_value=MockResponse(response),
    ):
        logs = client.query('{service_name="app"}')

    assert len(logs) == 1
    assert logs[0].message == '{"message":"request completed"}'
    assert logs[0].level == "info"
    assert logs[0].fields["service_name"] == "app"


def test_query_returns_empty_when_no_logs():
    response = {
        "status": "success",
        "data": {
            "resultType": "streams",
            "result": [],
        },
    }

    client = LokiClient("http://loki:3100")

    with patch(
        "app.evidence.loki.urlopen",
        return_value=MockResponse(response),
    ):
        assert client.query('{service_name="app"}') == []


def test_query_raises_when_loki_request_fails():
    client = LokiClient("http://loki:3100")

    with patch(
        "app.evidence.loki.urlopen",
        side_effect=URLError("connection failed"),
    ), pytest.raises(ConnectionError, match="Loki request failed"):
        client.query('{service_name="app"}')
