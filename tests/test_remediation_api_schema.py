import pytest
from pydantic import ValidationError

from app.schemas import RemediationCreate


def test_remediation_create_accepts_action_and_parameters():
    payload = RemediationCreate(
        action="restart_service",
        parameters={"service": "app"},
    )

    assert payload.action == "restart_service"
    assert payload.parameters == {"service": "app"}


def test_remediation_create_defaults_parameters():
    payload = RemediationCreate(action="restart_service")

    assert payload.parameters == {}


def test_remediation_create_requires_action():
    with pytest.raises(ValidationError):
        RemediationCreate()
