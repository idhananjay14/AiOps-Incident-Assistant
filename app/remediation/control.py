from enum import Enum

MAX_REMEDIATION_ATTEMPTS = 2


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RemediationStatus(str, Enum):
    PENDING = "pending"
    DRY_RUN = "dry_run"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ESCALATED = "escalated"


def approve_remediation(approval_status: ApprovalStatus) -> ApprovalStatus:
    """Approve a remediation only from the pending state."""
    if approval_status != ApprovalStatus.PENDING:
        raise ValueError(
            f"Remediation cannot be approved from status: {approval_status.value}"
        )

    return ApprovalStatus.APPROVED


def reject_remediation(approval_status: ApprovalStatus) -> ApprovalStatus:
    """Reject a remediation only from the pending state."""
    if approval_status != ApprovalStatus.PENDING:
        raise ValueError(
            f"Remediation cannot be rejected from status: {approval_status.value}"
        )

    return ApprovalStatus.REJECTED


def can_attempt_remediation(attempt_count: int) -> bool:
    """Return whether another remediation attempt is permitted."""
    return attempt_count < MAX_REMEDIATION_ATTEMPTS


def record_failed_attempt(attempt_count: int) -> tuple[int, bool]:
    """Record a failed attempt and report whether the circuit is now open."""
    next_attempt_count = attempt_count + 1
    circuit_open = next_attempt_count >= MAX_REMEDIATION_ATTEMPTS

    return next_attempt_count, circuit_open
