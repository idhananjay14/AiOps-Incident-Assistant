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
from app.models import RCA, Incident, IncidentEvent, Remediation
from app.rca.confidence import calculate_confidence
from app.rca.gemini_engine import GeminiRCAEngine
from app.rca.openai_engine import OpenAIRCAEngine
from app.rca.validator import validate_rca
from app.remediation.control import (
    ApprovalStatus,
    RemediationStatus,
    approve_remediation,
    can_attempt_remediation,
    record_failed_attempt,
)
from app.remediation.dry_run import dry_run
from app.remediation.executor import ControlledExecutor
from app.remediation.policy import validate_action
from app.remediation.schemas import RemediationRequest
from app.remediation.verifier import verify_service
from app.schemas import (
    IncidentCreate,
    IncidentResponse,
    IncidentTransition,
    RCAResponse,
    RemediationApproval,
    RemediationCreate,
    RemediationResponse,
)

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



@app.get("/incidents/{incident_id}/rca", response_model=RCAResponse)
def get_incident_rca(
    incident_id: int,
    db: Session = Depends(get_db),
) -> RCA:
    rca = (
        db.query(RCA)
        .filter(RCA.incident_id == incident_id)
        .order_by(RCA.id.desc())
        .first()
    )

    if rca is None:
        raise HTTPException(status_code=404, detail="RCA not found")

    return rca


@app.post(
    "/incidents/{incident_id}/remediation",
    response_model=RemediationResponse,
    status_code=201,
)
def create_remediation(
    incident_id: int,
    payload: RemediationCreate,
    db: Session = Depends(get_db),
) -> Remediation:
    incident = db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status != "RCA_READY":
        raise HTTPException(
            status_code=409,
            detail=(
                "Remediation can only be created for RCA_READY incidents, "
                f"current status: {incident.status}"
            ),
        )

    try:
        action = validate_action(payload.action)
        request = RemediationRequest(
            incident_id=incident_id,
            action=action,
            parameters=payload.parameters,
        )
        dry_run_result = dry_run(request)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    remediation = Remediation(
        incident_id=incident_id,
        action=action.value,
        status=RemediationStatus.DRY_RUN.value,
        parameters=payload.parameters,
        approval_status=ApprovalStatus.PENDING.value,
        attempt_count=0,
        result=dry_run_result.model_dump(),
    )
    db.add(remediation)
    db.flush()

    incident.status = "REMEDIATION_PENDING"

    event = IncidentEvent(
        incident_id=incident_id,
        event_type="REMEDIATION_CREATED",
        message="Remediation dry run created and awaiting approval",
        details={
            "remediation_id": remediation.id,
            "action": action.value,
            "status": remediation.status,
            "approval_status": remediation.approval_status,
        },
    )
    db.add(event)

    db.commit()
    db.refresh(remediation)

    return remediation

@app.post(
    "/remediations/{remediation_id}/approve",
    response_model=RemediationResponse,
)
def approve_incident_remediation(
    remediation_id: int,
    payload: RemediationApproval,
    db: Session = Depends(get_db),
) -> Remediation:
    remediation = db.get(Remediation, remediation_id)

    if remediation is None:
        raise HTTPException(status_code=404, detail="Remediation not found")

    if not payload.approved:
        raise HTTPException(
            status_code=400,
            detail="Remediation approval must be true",
        )

    try:
        approval_status = approve_remediation(
            ApprovalStatus(remediation.approval_status)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    remediation.approval_status = approval_status.value
    remediation.status = RemediationStatus.APPROVED.value

    event = IncidentEvent(
        incident_id=remediation.incident_id,
        event_type="REMEDIATION_APPROVED",
        message="Remediation approved and ready for controlled execution",
        details={
            "remediation_id": remediation.id,
            "action": remediation.action,
            "approval_status": remediation.approval_status,
            "status": remediation.status,
        },
    )
    db.add(event)

    db.commit()
    db.refresh(remediation)

    return remediation


@app.post(
    "/remediations/{remediation_id}/execute",
    response_model=RemediationResponse,
)
def execute_incident_remediation(
    remediation_id: int,
    db: Session = Depends(get_db),
) -> Remediation:
    remediation = db.get(Remediation, remediation_id)

    if remediation is None:
        raise HTTPException(status_code=404, detail="Remediation not found")

    if remediation.approval_status != ApprovalStatus.APPROVED.value:
        raise HTTPException(
            status_code=409,
            detail="Remediation must be approved before execution",
        )

    if not can_attempt_remediation(remediation.attempt_count):
        remediation.status = RemediationStatus.ESCALATED.value
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Remediation circuit breaker is open",
        )

    remediation.status = RemediationStatus.EXECUTING.value

    event = IncidentEvent(
        incident_id=remediation.incident_id,
        event_type="REMEDIATION_EXECUTING",
        message="Approved remediation execution started",
        details={
            "remediation_id": remediation.id,
            "action": remediation.action,
            "attempt_count": remediation.attempt_count + 1,
        },
    )
    db.add(event)

    incident = db.get(Incident, remediation.incident_id)
    if incident is not None:
        incident.status = "REMEDIATING"

    db.commit()

    request = RemediationRequest(
        incident_id=remediation.incident_id,
        action=remediation.action,
        parameters=remediation.parameters,
    )

    try:
        result = ControlledExecutor().execute(request)
    except Exception as exc:  # noqa: BLE001
        attempt_count, circuit_open = record_failed_attempt(
            remediation.attempt_count
        )
        remediation.attempt_count = attempt_count
        remediation.status = (
            RemediationStatus.ESCALATED.value
            if circuit_open
            else RemediationStatus.FAILED.value
        )
        remediation.result = {
            "success": False,
            "error": str(exc),
            "attempt_count": attempt_count,
        }

        if incident is not None:
            incident.status = (
                "ESCALATED" if circuit_open else "REMEDIATION_PENDING"
            )

        event = IncidentEvent(
            incident_id=remediation.incident_id,
            event_type="REMEDIATION_FAILED",
            message=(
                "Remediation failed and circuit breaker opened"
                if circuit_open
                else "Remediation execution failed"
            ),
            details={
                "remediation_id": remediation.id,
                "attempt_count": attempt_count,
                "circuit_open": circuit_open,
                "error": str(exc),
            },
        )
        db.add(event)
        db.commit()
        db.refresh(remediation)

        return remediation

    remediation.attempt_count += 1
    remediation.status = RemediationStatus.SUCCEEDED.value
    remediation.result = result.model_dump()

    service = remediation.parameters.get("service")
    verification = verify_service(service)

    remediation.result["verification"] = verification.model_dump()

    if not verification.healthy:
        circuit_open = not can_attempt_remediation(
            remediation.attempt_count
        )
        remediation.status = (
            RemediationStatus.ESCALATED.value
            if circuit_open
            else RemediationStatus.FAILED.value
        )
        remediation.result["attempt_count"] = remediation.attempt_count

        if incident is not None:
            incident.status = (
                "ESCALATED" if circuit_open else "REMEDIATION_PENDING"
            )

        event = IncidentEvent(
            incident_id=remediation.incident_id,
            event_type="REMEDIATION_VERIFICATION_FAILED",
            message=(
                "Service recovery verification failed and circuit breaker opened"
                if circuit_open
                else "Service recovery verification failed"
            ),
            details={
                "remediation_id": remediation.id,
                "attempt_count": remediation.attempt_count,
                "circuit_open": circuit_open,
                "verification": verification.model_dump(),
            },
        )
        db.add(event)
        db.commit()
        db.refresh(remediation)

        return remediation

    if incident is not None:
        incident.status = "VERIFYING"

    event = IncidentEvent(
        incident_id=remediation.incident_id,
        event_type="REMEDIATION_SUCCEEDED",
        message="Remediation executed successfully and incident moved to verification",
        details={
            "remediation_id": remediation.id,
            "attempt_count": remediation.attempt_count,
            "status": remediation.status,
        },
    )
    db.add(event)

    db.commit()
    db.refresh(remediation)

    return remediation


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

    if settings.rca_provider == "gemini":
        rca_result = GeminiRCAEngine().analyze(evidence)
    else:
        rca_result = OpenAIRCAEngine().analyze(evidence)

    try:
        validate_rca(rca_result, evidence)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    confidence = calculate_confidence(evidence)
    rca_result = rca_result.model_copy(update={"confidence": confidence})

    rca = RCA(
        incident_id=incident_id,
        root_cause=rca_result.root_cause,
        confidence=confidence.value,
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
                "confidence": confidence.value,
            },
        )
        db.add(event)

    db.commit()

    return rca_result
