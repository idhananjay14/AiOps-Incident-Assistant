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


def test_rca_endpoint_returns_structured_rca(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.dependencies import get_db
    from app.evidence.schemas import RCAConfidence, RCAResult
    from app.incident_api.main import app
    from app.models import Incident

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    session_local = sessionmaker(bind=engine)
    db = session_local()

    incident = Incident(
        incident_key="INC-004",
        status="INVESTIGATING",
        severity="critical",
        title="High error rate",
        description="Application errors increased.",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    expected_rca = RCAResult(
        root_cause="Application error rate increased",
        confidence=RCAConfidence.HIGH,
        impact="Task API requests are failing.",
        recommended_action="Investigate the application error path",
    )

    class FakeRCAEngine:
        def analyze(self, evidence):
            assert evidence.incident.incident_key == "INC-004"
            return expected_rca

    def override_get_db():
        try:
            yield db
        finally:
            pass

    monkeypatch.setattr(
        "app.incident_api.main.OpenAIRCAEngine",
        lambda: FakeRCAEngine(),
    )

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(f"/incidents/{incident.id}/rca")

        assert response.status_code == 200

        data = response.json()

        assert data["root_cause"] == "Application error rate increased"
        assert data["confidence"] == "high"
        assert data["impact"] == "Task API requests are failing."
        assert data["recommended_action"] == (
            "Investigate the application error path"
        )

        from app.models import RCA, IncidentEvent

        stored_rca = db.query(RCA).filter_by(incident_id=incident.id).one()
        assert stored_rca.root_cause == "Application error rate increased"
        assert stored_rca.confidence == "high"
        assert stored_rca.impact == "Task API requests are failing."
        assert stored_rca.recommended_action == (
            "Investigate the application error path"
        )

        db.refresh(incident)
        assert incident.status == "RCA_READY"

        event = (
            db.query(IncidentEvent)
            .filter_by(
                incident_id=incident.id,
                event_type="RCA_GENERATED",
            )
            .one()
        )
        assert event.message == "Root cause analysis generated"
        assert event.details["confidence"] == "high"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_rca_endpoint_returns_404_for_missing_incident(monkeypatch):
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
        response = client.post("/incidents/999/rca")

        assert response.status_code == 404
        assert response.json()["detail"] == "Incident not found"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_rca_endpoint_rejects_invalid_evidence_citation(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base
    from app.dependencies import get_db
    from app.evidence.schemas import RCAConfidence, RCAEvidence, RCAResult
    from app.incident_api.main import app
    from app.models import RCA, Incident, IncidentEvent

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    session_local = sessionmaker(bind=engine)
    db = session_local()

    incident = Incident(
        incident_key="INC-005",
        status="INVESTIGATING",
        severity="critical",
        title="High error rate",
        description="Application errors increased.",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    invalid_rca = RCAResult(
        root_cause="Database failure",
        confidence=RCAConfidence.HIGH,
        evidence=[
            RCAEvidence(
                source="prometheus",
                reference="nonexistent_metric",
                reasoning="This metric does not exist in the evidence bundle.",
            )
        ],
        impact="Task API requests are failing.",
        recommended_action="Investigate the database",
    )

    class FakeRCAEngine:
        def analyze(self, evidence):
            return invalid_rca

    def override_get_db():
        try:
            yield db
        finally:
            pass

    monkeypatch.setattr(
        "app.incident_api.main.OpenAIRCAEngine",
        lambda: FakeRCAEngine(),
    )

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(f"/incidents/{incident.id}/rca")

        assert response.status_code == 422
        assert "does not exist in the evidence bundle" in response.json()["detail"]

        assert db.query(RCA).filter_by(incident_id=incident.id).count() == 0

        db.refresh(incident)
        assert incident.status == "INVESTIGATING"

        assert (
            db.query(IncidentEvent)
            .filter_by(
                incident_id=incident.id,
                event_type="RCA_GENERATED",
            )
            .count()
            == 0
        )
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
