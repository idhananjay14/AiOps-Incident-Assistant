from abc import ABC, abstractmethod

import docker
from pydantic import BaseModel, Field

from app.remediation.policy import validate_action, validate_service
from app.remediation.schemas import RemediationRequest


class ExecutionResult(BaseModel):
    success: bool
    action: str
    service: str
    parameters: dict = Field(default_factory=dict)
    message: str


class RemediationExecutor(ABC):
    @abstractmethod
    def execute(self, request: RemediationRequest) -> ExecutionResult:
        """Execute an approved remediation request."""
        raise NotImplementedError


class ControlledExecutor(RemediationExecutor):
    def __init__(
        self,
        timeout: int = 30,
        docker_client=None,
    ) -> None:
        self.timeout = timeout
        self.docker_client = docker_client or docker.from_env()

    def execute(self, request: RemediationRequest) -> ExecutionResult:
        action = validate_action(request.action.value)

        if action.value != "restart_service":
            raise ValueError(
                f"Remediation action is not executable yet: {action.value}"
            )

        if "service" not in request.parameters:
            raise ValueError("Remediation service is required")

        service = request.parameters["service"]
        if not isinstance(service, str):
            raise TypeError("Remediation service must be a string")

        validate_service(service)

        containers = self.docker_client.containers.list(
            all=True,
            filters={
                "label": [
                    "com.docker.compose.project=aiops-incident-assistant",
                    f"com.docker.compose.service={service}",
                ]
            },
        )

        if len(containers) != 1:
            raise ValueError(
                f"Expected exactly one remediation target for service: {service}"
            )

        container = containers[0]
        container.restart(timeout=self.timeout)

        return ExecutionResult(
            success=True,
            action=action.value,
            service=service,
            parameters=request.parameters,
            message=f"Remediation executed successfully for {service}",
        )


def build_restart_command(service: str) -> list[str]:
    """Build the fixed Docker Compose restart command for an allowed service."""
    validated_service = validate_service(service)

    return ["docker", "compose", "restart", validated_service]
