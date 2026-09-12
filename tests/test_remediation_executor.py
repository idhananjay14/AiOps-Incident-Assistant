import pytest

from app.remediation.executor import ControlledExecutor, ExecutionResult
from app.remediation.schemas import RemediationRequest


def test_controlled_executor_returns_execution_result():
    class FakeContainer:
        def restart(self, timeout):
            pass

    class FakeContainers:
        def list(self, **kwargs):
            return [FakeContainer()]

    class FakeDockerClient:
        containers = FakeContainers()

    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
        parameters={"service": "app"},
    )

    result = ControlledExecutor(docker_client=FakeDockerClient()).execute(request)

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


def test_controlled_executor_restarts_allowed_container():
    calls = []

    class FakeContainer:
        def restart(self, timeout):
            calls.append(timeout)

    class FakeContainers:
        def list(self, **kwargs):
            calls.append(kwargs)
            return [FakeContainer()]

    class FakeDockerClient:
        containers = FakeContainers()

    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
        parameters={"service": "app"},
    )

    result = ControlledExecutor(docker_client=FakeDockerClient()).execute(request)

    assert result.success is True
    assert result.action == "restart_service"
    assert result.service == "app"
    assert result.message == "Remediation executed successfully for app"
    assert calls[0]["all"] is True
    assert calls[0]["filters"]["label"] == [
        "com.docker.compose.project=aiops-incident-assistant",
        "com.docker.compose.service=app",
    ]
    assert calls[1] == 30


def test_controlled_executor_rejects_multiple_containers():
    class FakeContainers:
        def list(self, **kwargs):
            return [object(), object()]

    class FakeDockerClient:
        containers = FakeContainers()

    request = RemediationRequest(
        incident_id=1,
        action="restart_service",
        parameters={"service": "app"},
    )

    with pytest.raises(ValueError, match="Expected exactly one remediation target"):
        ControlledExecutor(docker_client=FakeDockerClient()).execute(request)


def test_controlled_executor_does_not_execute_other_actions():
    class FakeDockerClient:
        containers = None

    request = RemediationRequest(
        incident_id=1,
        action="scale_service",
        parameters={"service": "app", "replicas": 2},
    )

    with pytest.raises(ValueError, match="not executable yet"):
        ControlledExecutor(docker_client=FakeDockerClient()).execute(request)
