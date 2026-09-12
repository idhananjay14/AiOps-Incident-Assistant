import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable

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
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        timeout: int = 30,
    ) -> None:
        self.runner = runner or subprocess.run
        self.timeout = timeout

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

        command = build_restart_command(service)
        result = self.runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            shell=False,
        )

        if result.returncode != 0:
            return ExecutionResult(
                success=False,
                action=action.value,
                service=service,
                parameters=request.parameters,
                message=result.stderr.strip() or "Remediation command failed",
            )

        return ExecutionResult(
            success=True,
            action=action.value,
            service=service,
            parameters=request.parameters,
            message=result.stdout.strip() or "Remediation executed successfully",
        )


def build_restart_command(service: str) -> list[str]:
    """Build the fixed Docker Compose restart command for an allowed service."""
    validated_service = validate_service(service)

    return ["docker", "compose", "restart", validated_service]
