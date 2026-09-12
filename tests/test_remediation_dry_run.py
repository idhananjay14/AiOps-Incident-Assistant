from app.remediation.dry_run import dry_run
from app.remediation.schemas import RemediationRequest


def test_dry_run_returns_allowed_plan_without_execution():
    request = RemediationRequest(
        incident_id=123,
        action="restart_service",
        parameters={"service": "aiops-app"},
    )

    result = dry_run(request)

    assert result.allowed is True
    assert result.action == "restart_service"
    assert result.parameters == {"service": "aiops-app"}
    assert result.executed is False


def test_dry_run_preserves_scale_parameters():
    request = RemediationRequest(
        incident_id=456,
        action="scale_service",
        parameters={"service": "aiops-app", "replicas": 3},
    )

    result = dry_run(request)

    assert result.action == "scale_service"
    assert result.parameters == {
        "service": "aiops-app",
        "replicas": 3,
    }
    assert result.executed is False


def test_dry_run_preserves_rollback_parameters():
    request = RemediationRequest(
        incident_id=789,
        action="rollback_deployment",
        parameters={"service": "aiops-app", "version": "0.1.0"},
    )

    result = dry_run(request)

    assert result.action == "rollback_deployment"
    assert result.parameters == {
        "service": "aiops-app",
        "version": "0.1.0",
    }
    assert result.executed is False
