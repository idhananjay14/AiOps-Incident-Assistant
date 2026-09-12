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


def metric(name, value):
    return MetricEvidence(
        name=name,
        query=f"{name}_query",
        value=value,
    )


def test_confidence_is_low_with_only_incident():
    evidence = build_evidence()

    assert calculate_confidence(evidence) == RCAConfidence.LOW


def test_confidence_is_low_with_healthy_metrics():
    evidence = build_evidence(
        metrics=[
            metric("error_rate", 0.01),
            metric("http_p95_latency", 0.2),
            metric("app_health", 1.0),
            metric("db_health", 1.0),
        ],
    )

    assert calculate_confidence(evidence) == RCAConfidence.LOW


def test_high_error_rate_is_medium():
    evidence = build_evidence(
        metrics=[metric("error_rate", 0.25)],
    )

    assert calculate_confidence(evidence) == RCAConfidence.MEDIUM


def test_high_latency_is_medium():
    evidence = build_evidence(
        metrics=[metric("http_p95_latency", 1.8)],
    )

    assert calculate_confidence(evidence) == RCAConfidence.MEDIUM


def test_database_unavailable_is_medium():
    evidence = build_evidence(
        metrics=[metric("db_health", 0.0)],
    )

    assert calculate_confidence(evidence) == RCAConfidence.MEDIUM


def test_two_operational_signals_are_high():
    evidence = build_evidence(
        metrics=[
            metric("error_rate", 0.25),
            metric("http_p95_latency", 1.8),
        ],
    )

    assert calculate_confidence(evidence) == RCAConfidence.HIGH


def test_alert_and_matching_metric_are_high():
    evidence = build_evidence(
        alerts=[
            AlertEvidence(
                alert_name="HighErrorRate",
                status="firing",
                severity="critical",
            )
        ],
        metrics=[
            metric("error_rate", 0.25),
        ],
    )

    assert calculate_confidence(evidence) == RCAConfidence.HIGH


def test_operational_signal_with_logs_is_high():
    evidence = build_evidence(
        metrics=[metric("error_rate", 0.25)],
        logs=[
            LogEvidence(message="Application error"),
        ],
    )

    assert calculate_confidence(evidence) == RCAConfidence.HIGH


def test_deployment_context_alone_does_not_create_confidence():
    evidence = build_evidence(
        deployment=DeploymentEvidence(
            version="0.1.0",
            commit="abc123",
        ),
    )

    assert calculate_confidence(evidence) == RCAConfidence.LOW
