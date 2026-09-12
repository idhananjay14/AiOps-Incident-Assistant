import pytest

from app.remediation.executor import ControlledExecutor, ExecutionResult
from app.remediation.schemas import RemediationRequest


def test_controlled_executor_returns_execution_result():
    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
        parameters={"service": "app"},
    )

    result = ControlledExecutor().execute(request)

    assert isinstance(result, ExecutionResult)
    assert result.success is True
    assert result.action == "restart_service"
    assert result.service == "app"


def test_controlled_executor_requires_service():
    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
    )

    with pytest.raises(ValueError, match="service is required"):
        ControlledExecutor().execute(request)


def test_controlled_executor_rejects_unapproved_service():
    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
        parameters={"service": "postgres"},
    )

    with pytest.raises(ValueError, match="service is not allowed"):
        ControlledExecutor().execute(request)


def test_controlled_executor_rejects_invalid_service_type():
    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
        parameters={"service": 123},
    )

    with pytest.raises(TypeError, match="service must be a string"):
        ControlledExecutor().execute(request)


def test_build_restart_command_for_allowed_service():
    from app.remediation.executor import build_restart_command

    assert build_restart_command("app") == [
        "docker",
        "compose",
        "restart",
        "app",
    ]


def test_build_restart_command_rejects_unapproved_service():
    from app.remediation.executor import build_restart_command

    with pytest.raises(ValueError, match="service is not allowed"):
        build_restart_command("postgres")


def test_controlled_executor_runs_fixed_restart_command():
    calls = []

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))

        class Result:
            returncode = 0
            stdout = "app restarted"
            stderr = ""

        return Result()

    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
        parameters={"service": "app"},
    )

    result = ControlledExecutor(runner=fake_runner).execute(request)

    assert result.success is True
    assert result.message == "app restarted"
    assert calls[0][0] == ["docker", "compose", "restart", "app"]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["timeout"] == 30


def test_controlled_executor_reports_command_failure():
    def fake_runner(command, **kwargs):
        class Result:
            returncode = 1
            stdout = ""
            stderr = "restart failed"

        return Result()

    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
        parameters={"service": "app"},
    )

    result = ControlledExecutor(runner=fake_runner).execute(request)

    assert result.success is False
    assert result.message == "restart failed"


def test_controlled_executor_does_not_execute_other_actions():
    calls = []

    def fake_runner(command, **kwargs):
        calls.append(command)

    request = RemediationRequest(
        incident_id=1,
        action="scale_service",
        parameters={"service": "app", "replicas": 2},
    )

    with pytest.raises(ValueError, match="not executable yet"):
        ControlledExecutor(runner=fake_runner).execute(request)

    assert calls == []
