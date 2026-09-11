from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.evidence.collector import EvidenceCollector
from app.models import Alert, Incident


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    session_local = sessionmaker(bind=engine)
    session = session_local()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_collects_incident_and_alert_evidence(db_session):
    incident = Incident(
        incident_key="INC-001",
        status="OPEN",
        severity="critical",
        title="High error rate",
        description="Application is returning elevated 5xx responses.",
    )
    db_session.add(incident)
    db_session.flush()

    alert = Alert(
        alert_key="HighErrorRate:task-api",
        alert_name="HighErrorRate",
        status="firing",
        severity="critical",
        summary="High application error rate",
        description="Error rate exceeded threshold.",
        labels={"service": "task-api"},
        annotations={"runbook": "investigate-errors"},
        starts_at=datetime(2026, 9, 11, 10, 0, 0, tzinfo=UTC),
    )
    db_session.add(alert)
    db_session.commit()

    bundle = EvidenceCollector(db_session).collect(incident.id)

    assert bundle.incident.incident_key == "INC-001"
    assert bundle.incident.status == "OPEN"
    assert bundle.incident.severity == "critical"

    assert len(bundle.alerts) == 1
    assert bundle.alerts[0].alert_name == "HighErrorRate"
    assert bundle.alerts[0].labels == {"service": "task-api"}
    assert bundle.alerts[0].annotations == {"runbook": "investigate-errors"}


def test_collects_incident_without_alerts(db_session):
    incident = Incident(
        incident_key="INC-002",
        status="INVESTIGATING",
        severity="warning",
        title="Service issue",
    )
    db_session.add(incident)
    db_session.commit()

    bundle = EvidenceCollector(db_session).collect(incident.id)

    assert bundle.incident.incident_key == "INC-002"
    assert bundle.alerts == []


def test_raises_error_when_incident_does_not_exist(db_session):
    with pytest.raises(ValueError, match="Incident not found"):
        EvidenceCollector(db_session).collect(999)


class FakePrometheusClient:
    def __init__(self, values):
        self.values = values
        self.queries = []

    def query(self, expression):
        self.queries.append(expression)
        return self.values.get(expression)


def test_collects_prometheus_metric_evidence(db_session):
    incident = Incident(
        incident_key="INC-003",
        status="INVESTIGATING",
        severity="critical",
        title="Application degradation",
    )
    db_session.add(incident)
    db_session.commit()

    metrics = {
        "sum(rate(http_requests_total[5m]))": 12.5,
        (
            "sum(rate(http_requests_errors_total[5m]))"
            " / sum(rate(http_requests_total[5m]))"
        ): 0.25,
        (
            "histogram_quantile("
            "0.95, "
            "sum by (le) (rate(http_request_duration_seconds_bucket[5m]))"
            ")"
        ): 1.8,
        (
            "histogram_quantile("
            "0.95, "
            "sum by (le) (rate(db_query_duration_seconds_bucket[5m]))"
            ")"
        ): 0.12,
        "http_requests_in_progress": 3.0,
        "app_health": 1.0,
        "db_health": 1.0,
    }

    prometheus = FakePrometheusClient(metrics)

    bundle = EvidenceCollector(
        db_session,
        prometheus=prometheus,
    ).collect(incident.id)

    assert len(bundle.metrics) == 7

    evidence = {metric.name: metric for metric in bundle.metrics}

    assert evidence["request_rate"].value == 12.5
    assert evidence["request_rate"].unit == "requests/sec"

    assert evidence["error_rate"].value == 0.25
    assert evidence["error_rate"].unit == "ratio"

    assert evidence["http_p95_latency"].value == 1.8
    assert evidence["http_p95_latency"].unit == "seconds"

    assert evidence["db_p95_latency"].value == 0.12
    assert evidence["db_p95_latency"].unit == "seconds"

    assert evidence["active_requests"].value == 3.0
    assert evidence["active_requests"].unit == "requests"

    assert evidence["app_health"].value == 1.0
    assert evidence["app_health"].unit == "status"

    assert evidence["db_health"].value == 1.0
    assert evidence["db_health"].unit == "status"

    assert len(prometheus.queries) == 7
