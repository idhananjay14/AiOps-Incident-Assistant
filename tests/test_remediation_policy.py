import pytest

from app.remediation.policy import (
    ALLOWED_REMEDIATION_ACTIONS,
    RemediationAction,
    validate_action,
)


def test_allowlisted_actions_are_supported():
    assert ALLOWED_REMEDIATION_ACTIONS == {
        RemediationAction.RESTART_SERVICE,
        RemediationAction.SCALE_SERVICE,
        RemediationAction.ROLLBACK_DEPLOYMENT,
    }


@pytest.mark.parametrize(
    "action",
    [
        "restart_service",
        "scale_service",
        "rollback_deployment",
    ],
)
def test_allowlisted_action_is_accepted(action):
    assert validate_action(action).value == action


@pytest.mark.parametrize(
    "action",
    [
        "delete_database",
        "kubectl_exec",
        "run_shell",
        "aws_delete",
    ],
)
def test_unapproved_action_is_rejected(action):
    with pytest.raises(ValueError, match="not allowed"):
        validate_action(action)
