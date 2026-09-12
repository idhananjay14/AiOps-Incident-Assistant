from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evidence.loki import LokiClient
from app.evidence.prometheus import PrometheusClient
from app.evidence.schemas import (
    AlertEvidence,
    EvidenceBundle,
    IncidentEvidence,
    MetricEvidence,
)
from app.models import Alert, Incident

METRIC_QUERIES = [
    (
        "request_rate",
        "sum(rate(http_requests_total[5m]))",
        "requests/sec",
    ),
    (
        "error_rate",
        (
            "sum(rate(http_requests_errors_total[5m]))"
            " / sum(rate(http_requests_total[5m]))"
        ),
        "ratio",
    ),
    (
        "http_p95_latency",
        (
            "histogram_quantile("
            "0.95, "
            "sum by (le) (rate(http_request_duration_seconds_bucket[5m]))"
            ")"
        ),
        "seconds",
    ),
    (
        "db_p95_latency",
        (
            "histogram_quantile("
            "0.95, "
            "sum by (le) (rate(db_query_duration_seconds_bucket[5m]))"
            ")"
        ),
        "seconds",
    ),
    ("active_requests", "http_requests_in_progress", "requests"),
    ("app_health", "app_health", "status"),
    ("db_health", "db_health", "status"),
]


class EvidenceCollector:
    def __init__(
        self,
        db: Session,
        prometheus: PrometheusClient | None = None,
        loki: LokiClient | None = None,
    ):
        self.db = db
        self.prometheus = prometheus
        self.loki = loki

    def collect(self, incident_id: int) -> EvidenceBundle:
        incident = self.db.get(Incident, incident_id)

        if incident is None:
            raise ValueError("Incident not found")

        alerts = self.db.scalars(
            select(Alert).order_by(Alert.created_at.desc())
        ).all()

        incident_evidence = IncidentEvidence(
            incident_id=incident.id,
            incident_key=incident.incident_key,
            status=incident.status,
            severity=incident.severity,
            title=incident.title,
            description=incident.description,
        )

        alert_evidence = [
            AlertEvidence(
                alert_name=alert.alert_name,
                status=alert.status,
                severity=alert.severity,
                summary=alert.summary,
                description=alert.description,
                labels=alert.labels,
                annotations=alert.annotations,
                starts_at=alert.starts_at,
                ends_at=alert.ends_at,
            )
            for alert in alerts
        ]

        metric_evidence = []

        log_evidence = []

        if self.loki is not None:
            log_evidence = self.loki.query(
                '{service_name="app"} |= "request completed"'
            )

        if self.prometheus is not None:
            for name, query, unit in METRIC_QUERIES:
                metric_evidence.append(
                    MetricEvidence(
                        name=name,
                        query=query,
                        value=self.prometheus.query(query),
                        unit=unit,
                    )
                )

        return EvidenceBundle(
            incident=incident_evidence,
            alerts=alert_evidence,
            metrics=metric_evidence,
            logs=log_evidence,
        )
