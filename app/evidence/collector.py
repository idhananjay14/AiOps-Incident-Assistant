from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.evidence.loki import LokiClient
from app.evidence.prometheus import PrometheusClient
from app.evidence.sanitizer import sanitize_mapping, sanitize_text
from app.evidence.schemas import (
    AlertEvidence,
    DeploymentEvidence,
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
            description=(
                sanitize_text(incident.description)
                if incident.description is not None
                else None
            ),
        )

        alert_evidence = [
            AlertEvidence(
                alert_name=alert.alert_name,
                status=alert.status,
                severity=alert.severity,
                summary=(
                    sanitize_text(alert.summary)
                    if alert.summary is not None
                    else None
                ),
                description=(
                    sanitize_text(alert.description)
                    if alert.description is not None
                    else None
                ),
                labels=sanitize_mapping(alert.labels),
                annotations=sanitize_mapping(alert.annotations),
                starts_at=alert.starts_at,
                ends_at=alert.ends_at,
            )
            for alert in alerts
        ]

        metric_evidence = []

        log_evidence = []

        deployment_evidence = DeploymentEvidence(
            version=settings.deployment_version,
            commit=settings.deployment_commit,
            description=settings.deployment_description,
        )

        if settings.deployment_deployed_at:
            try:
                deployment_evidence.deployed_at = datetime.fromisoformat(
                    settings.deployment_deployed_at
                )
            except ValueError:
                deployment_evidence.deployed_at = None

        if self.loki is not None:
            log_evidence = self.loki.query(
                '{service_name="app"} |= "request completed"'
            )

        log_evidence = [
            log.model_copy(
                update={
                    "message": sanitize_text(log.message),
                    "fields": sanitize_mapping(log.fields),
                }
            )
            for log in log_evidence
        ]

        deployment_evidence = deployment_evidence.model_copy(
            update={
                "version": (
                    sanitize_text(deployment_evidence.version)
                    if deployment_evidence.version is not None
                    else None
                ),
                "commit": (
                    sanitize_text(deployment_evidence.commit)
                    if deployment_evidence.commit is not None
                    else None
                ),
                "description": (
                    sanitize_text(deployment_evidence.description)
                    if deployment_evidence.description is not None
                    else None
                ),
            }
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
            deployment=deployment_evidence,
        )
