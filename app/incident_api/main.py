from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.evidence.collector import EvidenceCollector
from app.evidence.loki import LokiClient
from app.evidence.prometheus import PrometheusClient
from app.evidence.schemas import EvidenceBundle, RCAResult
from app.models import RCA, Incident, IncidentEvent
from app.rca.openai_engine import OpenAIRCAEngine
from app.schemas import IncidentCreate, IncidentResponse, IncidentTransition

INCIDENT_STATUSES = (
    "OPEN",
    "INVESTIGATING",
    "RCA_READY",
    "REMEDIATION_PENDING",
    "REMEDIATING",
    "VERIFYING",
    "RESOLVED",
    "ESCALATED",
)


INCIDENT_TRANSITIONS = {
    "OPEN": {"INVESTIGATING"},
    "INVESTIGATING": {"RCA_READY"},
    "RCA_READY": {"REMEDIATION_PENDING"},
    "REMEDIATION_PENDING": {"REMEDIATING"},
    "REMEDIATING": {"VERIFYING"},
    "VERIFYING": {"RESOLVED", "ESCALATED"},
    "RESOLVED": set(),
    "ESCALATED": set(),
}


app = FastAPI(
    title="AIOps Incident API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/incidents", response_model=IncidentResponse, status_code=201)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)) -> Incident:
    incident = Incident(
        incident_key=payload.incident_key,
        status="OPEN",
        severity=payload.severity,
        title=payload.title,
        description=payload.description,
    )
    db.add(incident)
    db.flush()

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="INCIDENT_CREATED",
        message="Incident created",
        details={"status": incident.status},
    )
    db.add(event)

    db.commit()
    db.refresh(incident)

    return incident


@app.post("/incidents/{incident_id}/transition", response_model=IncidentResponse)
def transition_incident(
    incident_id: int,
    payload: IncidentTransition,
    db: Session = Depends(get_db),
) -> Incident:
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    allowed_transitions = INCIDENT_TRANSITIONS.get(incident.status, set())

    if payload.status not in allowed_transitions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition from {incident.status} to {payload.status}",
        )

    previous_status = incident.status
    incident.status = payload.status

    if payload.status == "RESOLVED":
        incident.resolved_at = datetime.now(UTC)

    event = IncidentEvent(
        incident_id=incident.id,
        event_type="STATUS_CHANGED",
        message=payload.message or f"Incident status changed from {previous_status} to {payload.status}",
        details={
            "from_status": previous_status,
            "to_status": payload.status,
        },
    )
    db.add(event)

    db.commit()
    db.refresh(incident)

    return incident


@app.post("/alerts")
def receive_alert(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "status": "received",
        "alerts": str(len(payload.get("alerts", []))),
    }


@app.get("/incidents/{incident_id}/evidence", response_model=EvidenceBundle)
def get_incident_evidence(
    incident_id: int,
    db: Session = Depends(get_db),
) -> EvidenceBundle:
    try:
        prometheus = PrometheusClient(settings.prometheus_url)
        loki = LokiClient(settings.loki_url)
        return EvidenceCollector(
            db,
            prometheus=prometheus,
            loki=loki,
        ).collect(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/incidents/{incident_id}/rca", response_model=RCAResult)
def generate_incident_rca(
    incident_id: int,
    db: Session = Depends(get_db),
) -> RCAResult:
    try:
        prometheus = PrometheusClient(settings.prometheus_url)
        loki = LokiClient(settings.loki_url)
        evidence = EvidenceCollector(
            db,
            prometheus=prometheus,
            loki=loki,
        ).collect(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    rca_result = OpenAIRCAEngine().analyze(evidence)

    rca = RCA(
        incident_id=incident_id,
        root_cause=rca_result.root_cause,
        confidence=rca_result.confidence.value,
        evidence=[item.model_dump() for item in rca_result.evidence],
        impact=rca_result.impact,
        contributing_factors=rca_result.contributing_factors,
        recommended_action=rca_result.recommended_action,
        verification_steps=rca_result.verification_steps,
    )
    db.add(rca)

    incident = db.get(Incident, incident_id)
    if incident is not None:
        incident.status = "RCA_READY"

        event = IncidentEvent(
            incident_id=incident_id,
            event_type="RCA_GENERATED",
            message="Root cause analysis generated",
            details={
                "confidence": rca_result.confidence.value,
            },
        )
        db.add(event)

    db.commit()

    return rca_result
