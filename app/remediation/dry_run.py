from pydantic import BaseModel, Field

from app.remediation.policy import validate_action
from app.remediation.schemas import RemediationRequest


class DryRunResult(BaseModel):
    allowed: bool
    action: str
    parameters: dict = Field(default_factory=dict)
    executed: bool = False


def dry_run(request: RemediationRequest) -> DryRunResult:
    """Validate a remediation request and return an execution plan without executing it."""
    action = validate_action(request.action.value)

    return DryRunResult(
        allowed=True,
        action=action.value,
        parameters=request.parameters,
        executed=False,
    )
