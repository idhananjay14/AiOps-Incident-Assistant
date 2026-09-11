from app.incident_api.main import INCIDENT_STATUSES, INCIDENT_TRANSITIONS


def test_all_incident_statuses_have_transition_rules():
    assert set(INCIDENT_TRANSITIONS) == set(INCIDENT_STATUSES)


def test_incident_lifecycle_transitions():
    assert INCIDENT_TRANSITIONS["OPEN"] == {"INVESTIGATING"}
    assert INCIDENT_TRANSITIONS["INVESTIGATING"] == {"RCA_READY"}
    assert INCIDENT_TRANSITIONS["RCA_READY"] == {"REMEDIATION_PENDING"}
    assert INCIDENT_TRANSITIONS["REMEDIATION_PENDING"] == {"REMEDIATING"}
    assert INCIDENT_TRANSITIONS["REMEDIATING"] == {"VERIFYING"}


def test_verifying_can_resolve_or_escalate():
    assert INCIDENT_TRANSITIONS["VERIFYING"] == {"RESOLVED", "ESCALATED"}


def test_terminal_states_have_no_transitions():
    assert INCIDENT_TRANSITIONS["RESOLVED"] == set()
    assert INCIDENT_TRANSITIONS["ESCALATED"] == set()


def test_invalid_transition_is_not_allowed():
    assert "RESOLVED" not in INCIDENT_TRANSITIONS["OPEN"]
    assert "ESCALATED" not in INCIDENT_TRANSITIONS["INVESTIGATING"]
    assert "OPEN" not in INCIDENT_TRANSITIONS["RESOLVED"]


def test_evidence_endpoint_returns_incident_evidence():
    from datetime import UTC, datetime

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.dependencies import get_db
    from app.incident_api.main import app
    from app.models import Alert, Incident

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    session_local = sessionmaker(bind=engine)
    db = session_local()

    incident = Incident(
        incident_key="INC-003",
        status="OPEN",
        severity="critical",
        title="High error rate",
        description="Application errors increased.",
    )
    db.add(incident)
    db.flush()

    alert = Alert(
        alert_key="HighErrorRate:task-api",
        alert_name="HighErrorRate",
        status="firing",
        severity="critical",
        summary="High application error rate",
        description="Error rate exceeded threshold.",
        labels={"service": "task-api"},
        annotations={},
        starts_at=datetime(2026, 9, 11, 10, 0, 0, tzinfo=UTC),
    )
    db.add(alert)
    db.commit()
    db.refresh(incident)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.get(f"/incidents/{incident.id}/evidence")

        assert response.status_code == 200

        data = response.json()

        assert data["incident"]["incident_key"] == "INC-003"
        assert data["incident"]["severity"] == "critical"
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["alert_name"] == "HighErrorRate"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_evidence_endpoint_returns_404_for_missing_incident():
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.dependencies import get_db
    from app.incident_api.main import app

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    session_local = sessionmaker(bind=engine)
    db = session_local()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.get("/incidents/999/evidence")

        assert response.status_code == 404
        assert response.json()["detail"] == "Incident not found"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
