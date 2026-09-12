import pytest
from pydantic import ValidationError

from app.remediation.policy import RemediationAction
from app.remediation.schemas import RemediationRequest


def test_remediation_request_accepts_allowlisted_action():
    request = RemediationRequest(
        incident_id=123,
        action="restart_service",
        parameters={"service": "aiops-app"},
    )

    assert request.incident_id == 123
    assert request.action == RemediationAction.RESTART_SERVICE
    assert request.parameters == {"service": "aiops-app"}


def test_remediation_request_defaults_parameters_to_empty_dict():
    request = RemediationRequest(
        incident_id=123,
        action="restart_service",
    )

    assert request.parameters == {}


@pytest.mark.parametrize(
    "action",
    [
        "run_shell",
        "kubectl_exec",
        "delete_database",
        "aws_delete",
    ],
)
def test_remediation_request_rejects_unapproved_action(action):
    with pytest.raises(ValidationError):
        RemediationRequest(
            incident_id=123,
            action=action,
        )
