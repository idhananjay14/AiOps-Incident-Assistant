from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evidence.schemas import AlertEvidence, EvidenceBundle, IncidentEvidence
from app.models import Alert, Incident


class EvidenceCollector:
    def __init__(self, db: Session):
        self.db = db

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

        return EvidenceBundle(
            incident=incident_evidence,
            alerts=alert_evidence,
        )
