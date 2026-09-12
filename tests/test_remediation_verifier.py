from app.remediation.verifier import VerificationResult, verify_service


def test_verify_service_returns_healthy(monkeypatch):
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.remediation.verifier.urlopen",
        lambda url, timeout: FakeResponse(),
    )

    result = verify_service("app")

    assert result == VerificationResult(
        healthy=True,
        service="app",
        message="Service health check passed",
    )


def test_verify_service_returns_unhealthy_for_non_200(monkeypatch):
    class FakeResponse:
        status = 503

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.remediation.verifier.urlopen",
        lambda url, timeout: FakeResponse(),
    )

    result = verify_service("app")

    assert result.healthy is False
    assert result.service == "app"
    assert result.message == "Health check returned HTTP 503"


def test_verify_service_retries_after_connection_failure(monkeypatch):
    calls = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(url, timeout):
        calls.append(1)

        if len(calls) == 1:
            raise OSError("connection refused")

        return FakeResponse()

    monkeypatch.setattr(
        "app.remediation.verifier.urlopen",
        fake_urlopen,
    )
    monkeypatch.setattr(
        "app.remediation.verifier.sleep",
        lambda seconds: None,
    )

    result = verify_service("app", retry_window=1)

    assert result == VerificationResult(
        healthy=True,
        service="app",
        message="Service health check passed",
    )
    assert len(calls) == 2


def test_verify_service_returns_unhealthy_after_retry_window(monkeypatch):
    def fake_urlopen(url, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(
        "app.remediation.verifier.urlopen",
        fake_urlopen,
    )
    monkeypatch.setattr(
        "app.remediation.verifier.sleep",
        lambda seconds: None,
    )

    result = verify_service("app", retry_window=1)

    assert result.healthy is False
    assert result.service == "app"
    assert "connection refused" in result.message
    assert "after retries" in result.message


def test_verify_service_rejects_unapproved_service():
    try:
        verify_service("postgres")
    except ValueError as exc:
        assert str(exc) == "Verification service is not allowed: postgres"
    else:
        raise AssertionError("Expected ValueError")
