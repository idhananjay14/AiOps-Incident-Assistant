import pytest

from app.remediation.control import (
    MAX_REMEDIATION_ATTEMPTS,
    ApprovalStatus,
    RemediationStatus,
    approve_remediation,
    can_attempt_remediation,
    record_failed_attempt,
    reject_remediation,
)


def test_approval_starts_pending_and_can_be_approved():
    assert ApprovalStatus.PENDING.value == "pending"
    assert approve_remediation(ApprovalStatus.PENDING) == ApprovalStatus.APPROVED


def test_pending_remediation_can_be_rejected():
    assert reject_remediation(ApprovalStatus.PENDING) == ApprovalStatus.REJECTED


@pytest.mark.parametrize(
    "status",
    [
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
    ],
)
def test_non_pending_remediation_cannot_be_approved(status):
    with pytest.raises(ValueError, match="cannot be approved"):
        approve_remediation(status)


@pytest.mark.parametrize(
    "status",
    [
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
    ],
)
def test_non_pending_remediation_cannot_be_rejected(status):
    with pytest.raises(ValueError, match="cannot be rejected"):
        reject_remediation(status)


def test_remediation_statuses_are_defined():
    assert RemediationStatus.PENDING.value == "pending"
    assert RemediationStatus.DRY_RUN.value == "dry_run"
    assert RemediationStatus.APPROVED.value == "approved"
    assert RemediationStatus.EXECUTING.value == "executing"
    assert RemediationStatus.SUCCEEDED.value == "succeeded"
    assert RemediationStatus.FAILED.value == "failed"
    assert RemediationStatus.ESCALATED.value == "escalated"


def test_first_attempt_is_allowed():
    assert can_attempt_remediation(0) is True
    assert can_attempt_remediation(1) is True


def test_second_failed_attempt_opens_circuit():
    assert MAX_REMEDIATION_ATTEMPTS == 2

    attempt_count, circuit_open = record_failed_attempt(1)

    assert attempt_count == 2
    assert circuit_open is True


def test_first_failed_attempt_keeps_circuit_closed():
    attempt_count, circuit_open = record_failed_attempt(0)

    assert attempt_count == 1
    assert circuit_open is False


def test_no_attempt_allowed_after_circuit_opens():
    assert can_attempt_remediation(2) is False
    assert can_attempt_remediation(3) is False
