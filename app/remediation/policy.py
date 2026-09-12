from enum import Enum


class RemediationAction(str, Enum):
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"


ALLOWED_REMEDIATION_ACTIONS = frozenset(RemediationAction)


def validate_action(action: str) -> RemediationAction:
    """Validate that a remediation action is explicitly allowlisted."""
    try:
        return RemediationAction(action)
    except ValueError as exc:
        raise ValueError(f"Remediation action is not allowed: {action}") from exc


ALLOWED_REMEDIATION_SERVICES = frozenset({"app"})


def validate_service(service: str) -> str:
    """Validate that a remediation target is explicitly allowlisted."""
    if service not in ALLOWED_REMEDIATION_SERVICES:
        raise ValueError(
            f"Remediation service is not allowed: {service}"
        )

    return service
