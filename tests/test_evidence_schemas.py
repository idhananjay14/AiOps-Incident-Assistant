from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.evidence.schemas import (
    AlertEvidence,
    DeploymentEvidence,
    EvidenceBundle,
    IncidentEvidence,
    LogEvidence,
    MetricEvidence,
)


def test_evidence_bundle_accepts_complete_evidence():
    bundle = EvidenceBundle(
        incident=IncidentEvidence(
            incident_id=1,
            incident_key="INC-001",
            status="OPEN",
            severity="critical",
            title="High error rate",
            description="Application is returning elevated 5xx responses.",
        ),
        alerts=[
            AlertEvidence(
                alert_name="HighErrorRate",
                status="firing",
                severity="critical",
                summary="High application error rate",
            )
        ],
        metrics=[
            MetricEvidence(
                name="http_requests_errors_total",
                query="rate(http_requests_errors_total[5m])",
                value=12.5,
                unit="requests/second",
                observed_at=datetime.now(UTC),
            )
        ],
        logs=[
            LogEvidence(
                timestamp=datetime.now(UTC),
                level="ERROR",
                message="request failed",
                fields={"status_code": 500},
            )
        ],
        deployment=DeploymentEvidence(
            version="v1.2.0",
            commit="abc123",
            description="Latest application deployment",
        ),
    )

    assert bundle.incident.incident_key == "INC-001"
    assert len(bundle.alerts) == 1
    assert len(bundle.metrics) == 1
    assert len(bundle.logs) == 1
    assert bundle.deployment is not None


def test_evidence_bundle_allows_empty_optional_evidence():
    bundle = EvidenceBundle(
        incident=IncidentEvidence(
            incident_id=1,
            incident_key="INC-002",
            status="OPEN",
            severity="warning",
            title="Service issue",
        )
    )

    assert bundle.alerts == []
    assert bundle.metrics == []
    assert bundle.logs == []
    assert bundle.deployment is None


def test_evidence_bundle_requires_incident():
    with pytest.raises(ValidationError):
        EvidenceBundle()
