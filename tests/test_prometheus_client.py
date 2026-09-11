import json
from unittest.mock import patch
from urllib.error import URLError

import pytest

from app.evidence.prometheus import PrometheusClient


def test_query_returns_metric_value():
    response = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {
                    "metric": {"__name__": "app_health"},
                    "value": [1789150000.0, "1"],
                }
            ],
        },
    }

    client = PrometheusClient("http://prometheus:9090")

    with patch(
        "app.evidence.prometheus.urlopen",
        return_value=MockResponse(response),
    ):
        assert client.query("app_health") == 1.0


def test_query_returns_none_when_metric_is_missing():
    response = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [],
        },
    }

    client = PrometheusClient("http://prometheus:9090")

    with patch(
        "app.evidence.prometheus.urlopen",
        return_value=MockResponse(response),
    ):
        assert client.query("app_health") is None


def test_query_raises_when_prometheus_request_fails():
    client = PrometheusClient("http://prometheus:9090")

    with patch(
        "app.evidence.prometheus.urlopen",
        side_effect=URLError("connection failed"),
    ), pytest.raises(ConnectionError, match="Prometheus request failed"):
        client.query("app_health")


class MockResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode()
