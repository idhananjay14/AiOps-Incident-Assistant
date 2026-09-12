import json
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.evidence.schemas import LogEvidence


class LokiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def query(self, log_query: str, limit: int = 50) -> list[LogEvidence]:
        params = urlencode(
            {
                "query": log_query,
                "limit": limit,
                "direction": "backward",
            }
        )

        request = Request(
            f"{self.base_url}/loki/api/v1/query_range?{params}",
            headers={"Accept": "application/json"},
        )

        try:
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode())
        except URLError as exc:
            raise ConnectionError("Loki request failed") from exc

        if payload.get("status") != "success":
            raise ConnectionError("Loki request failed")

        logs = []

        for stream in payload.get("data", {}).get("result", []):
            fields = stream.get("stream", {})

            for entry in stream.get("values", []):
                if len(entry) < 2:
                    continue

                timestamp_ns, message = entry[0], entry[1]

                timestamp = datetime.fromtimestamp(
                    int(timestamp_ns) / 1_000_000_000,
                    tz=UTC,
                )

                logs.append(
                    LogEvidence(
                        timestamp=timestamp,
                        level=fields.get("level") or fields.get("detected_level"),
                        message=message,
                        fields=fields,
                    )
                )

        return logs
