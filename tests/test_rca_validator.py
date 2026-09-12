import pytest

from app.evidence.schemas import (
    DeploymentEvidence,
    EvidenceBundle,
    IncidentEvidence,
    LogEvidence,
    MetricEvidence,
    RCAConfidence,
    RCAEvidence,
    RCAResult,
)
from app.rca.validator import validate_rca


def build_evidence() -> EvidenceBundle:
    return EvidenceBundle(
        incident=IncidentEvidence(
            incident_id=1,
            incident_key="INC-001",
            status="INVESTIGATING",
            severity="critical",
            title="High error rate",
        ),
        metrics=[
            MetricEvidence(
                name="error_rate",
                query="error_rate_query",
                value=0.8,
            )
        ],
        logs=[
            LogEvidence(message="Database connection failed"),
        ],
        deployment=DeploymentEvidence(
            version="0.1.0",
            commit="abc123",
        ),
    )


def test_validator_accepts_existing_evidence():
    evidence = build_evidence()

    result = RCAResult(
        root_cause="Application error rate increased",
        confidence=RCAConfidence.HIGH,
        evidence=[
            RCAEvidence(
                source="incident",
                reference="INC-001",
                reasoning="The incident reports elevated errors.",
            ),
            RCAEvidence(
                source="prometheus",
                reference="error_rate",
                reasoning="Prometheus reports a high error rate.",
            ),
            RCAEvidence(
                source="loki",
                reference="Database connection failed",
                reasoning="The log reports a database connection failure.",
            ),
            RCAEvidence(
                source="deployment",
                reference="abc123",
                reasoning="The deployment commit matches the incident window.",
            ),
        ],
        impact="Task API requests are failing.",
        recommended_action="Investigate the application error path",
    )

    validate_rca(result, evidence)


def test_validator_rejects_nonexistent_evidence():
    evidence = build_evidence()

    result = RCAResult(
        root_cause="Application CPU saturation",
        confidence=RCAConfidence.HIGH,
        evidence=[
            RCAEvidence(
                source="prometheus",
                reference="cpu_usage_95_percent",
                reasoning="CPU usage is allegedly high.",
            )
        ],
        impact="Service is degraded.",
        recommended_action="Investigate CPU usage",
    )

    with pytest.raises(ValueError, match="does not exist"):
        validate_rca(result, evidence)


def test_validator_rejects_unsupported_source():
    evidence = build_evidence()

    result = RCAResult(
        root_cause="Unknown root cause",
        confidence=RCAConfidence.LOW,
        evidence=[
            RCAEvidence(
                source="kubernetes",
                reference="pod-123",
                reasoning="Pod information was allegedly observed.",
            )
        ],
        impact="Service impact observed.",
        recommended_action="Collect additional evidence",
    )

    with pytest.raises(ValueError, match="Unsupported RCA evidence source"):
        validate_rca(result, evidence)


def test_validator_allows_unknown_root_cause_without_evidence():
    evidence = build_evidence()

    result = RCAResult(
        root_cause="Unknown root cause",
        confidence=RCAConfidence.LOW,
        impact="Service impact observed.",
        recommended_action="Collect additional evidence",
    )

    validate_rca(result, evidence)
