from time import sleep
from urllib.error import URLError
from urllib.request import urlopen

from pydantic import BaseModel


class VerificationResult(BaseModel):
    healthy: bool
    service: str
    message: str


def verify_service(
    service: str,
    base_url: str = "http://app:8000",
    timeout: int = 5,
    retry_window: int = 10,
    retry_interval: int = 1,
) -> VerificationResult:
    if service != "app":
        raise ValueError(f"Verification service is not allowed: {service}")

    url = f"{base_url.rstrip('/')}/health"

    last_error = None

    for attempt in range(retry_window + 1):
        try:
            with urlopen(url, timeout=timeout) as response:
                if response.status != 200:
                    return VerificationResult(
                        healthy=False,
                        service=service,
                        message=f"Health check returned HTTP {response.status}",
                    )

                return VerificationResult(
                    healthy=True,
                    service=service,
                    message="Service health check passed",
                )
        except (OSError, URLError, TimeoutError) as exc:
            last_error = exc

            if attempt < retry_window:
                sleep(retry_interval)

    return VerificationResult(
        healthy=False,
        service=service,
        message=f"Health check failed after retries: {last_error}",
    )
