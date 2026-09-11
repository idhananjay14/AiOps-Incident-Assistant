import json
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class PrometheusClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def query(self, expression: str) -> float | None:
        params = urlencode({"query": expression})
        request = Request(
            f"{self.base_url}/api/v1/query?{params}",
            headers={"Accept": "application/json"},
        )

        try:
            with urlopen(request, timeout=5) as response:
                payload = json.loads(response.read().decode())
        except URLError as exc:
            raise ConnectionError("Prometheus request failed") from exc

        if payload.get("status") != "success":
            raise ConnectionError("Prometheus request failed")

        results = payload.get("data", {}).get("result", [])

        if not results:
            return None

        value = results[0].get("value")

        if not value or len(value) < 2:
            return None

        return float(value[1])
