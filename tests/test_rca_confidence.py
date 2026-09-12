from app.evidence.schemas import (
    AlertEvidence,
    DeploymentEvidence,
    EvidenceBundle,
    IncidentEvidence,
    LogEvidence,
    MetricEvidence,
    RCAConfidence,
)
from app.rca.confidence import calculate_confidence


def build_evidence(**kwargs):
    return EvidenceBundle(
        incident=IncidentEvidence(
            incident_id=1,
            incident_key="INC-001",
            status="INVESTIGATING",
            severity="critical",
            title="High error rate",
        ),
        **kwargs,
    )


def test_confidence_is_low_with_only_incident():
    evidence = build_evidence()

    assert calculate_confidence(evidence) == RCAConfidence.LOW


def test_confidence_is_medium_with_single_metric_and_no_context():
    evidence = build_evidence(
        metrics=[
            MetricEvidence(
                name="error_rate",
                query="error_rate_query",
                value=0.8,
            )
        ],
    )

    assert calculate_confidence(evidence) == RCAConfidence.MEDIUM


def test_confidence_is_high_with_alert_and_matching_metric():
    evidence = build_evidence(
        alerts=[
            AlertEvidence(
                alert_name="HighErrorRate",
                status="firing",
                severity="critical",
            )
        ],
        metrics=[
            MetricEvidence(
                name="error_rate",
                query="error_rate_query",
                value=0.8,
            )
        ],
    )

    assert calculate_confidence(evidence) == RCAConfidence.HIGH


def test_confidence_is_high_with_metric_and_log():
    evidence = build_evidence(
        metrics=[
            MetricEvidence(
                name="error_rate",
                query="error_rate_query",
                value=0.8,
            )
        ],
        logs=[
            LogEvidence(message="Application error"),
        ],
    )

    assert calculate_confidence(evidence) == RCAConfidence.HIGH


def test_deployment_context_alone_does_not_create_high_confidence():
    evidence = build_evidence(
        deployment=DeploymentEvidence(
            version="0.1.0",
            commit="abc123",
        ),
    )

    assert calculate_confidence(evidence) == RCAConfidence.MEDIUM
