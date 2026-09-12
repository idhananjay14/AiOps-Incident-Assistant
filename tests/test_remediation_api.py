from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_db
from app.incident_api.main import app
from app.models import Incident, IncidentEvent, Remediation


def create_test_database():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)


def create_ready_incident(db):
    incident = Incident(
        incident_key="INC-READY",
        status="RCA_READY",
        severity="high",
        title="Test incident",
        description="Test incident",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


def test_create_remediation_runs_dry_run_and_waits_for_approval():
    engine, session_local = create_test_database()
    db = session_local()

    incident = Incident(
        incident_key="INC-001",
        status="RCA_READY",
        severity="high",
        title="High error rate",
        description="Test incident",
    )
    db.add(incident)
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
        response = client.post(
            f"/incidents/{incident.id}/remediation",
            json={
                "action": "restart_service",
                "parameters": {"service": "app"},
            },
        )

        assert response.status_code == 201

        body = response.json()
        assert body["incident_id"] == incident.id
        assert body["action"] == "restart_service"
        assert body["status"] == "dry_run"
        assert body["approval_status"] == "pending"
        assert body["attempt_count"] == 0
        assert body["result"]["allowed"] is True
        assert body["result"]["executed"] is False

        db.expire_all()
        saved_remediation = db.get(Remediation, body["id"])
        saved_incident = db.get(Incident, incident.id)

        assert saved_remediation is not None
        assert saved_incident.status == "REMEDIATION_PENDING"

        events = (
            db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident.id)
            .all()
        )
        assert len(events) == 1
        assert events[0].event_type == "REMEDIATION_CREATED"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_create_remediation_requires_existing_incident():
    engine, session_local = create_test_database()
    db = session_local()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            "/incidents/999/remediation",
            json={"action": "restart_service"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Incident not found"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_create_remediation_requires_rca_ready_status():
    engine, session_local = create_test_database()
    db = session_local()

    incident = Incident(
        incident_key="INC-002",
        status="INVESTIGATING",
        severity="high",
        title="Test incident",
    )
    db.add(incident)
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
        response = client.post(
            f"/incidents/{incident.id}/remediation",
            json={"action": "restart_service"},
        )

        assert response.status_code == 409
        assert "RCA_READY" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_create_remediation_rejects_unallowlisted_action():
    engine, session_local = create_test_database()
    db = session_local()

    incident = Incident(
        incident_key="INC-003",
        status="RCA_READY",
        severity="high",
        title="High error rate",
        description="Test incident",
    )
    db.add(incident)
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
        response = client.post(
            f"/incidents/{incident.id}/remediation",
            json={"action": "delete_database"},
        )

        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_approve_remediation_updates_status_and_records_event():
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)
    incident.status = "REMEDIATION_PENDING"
    db.commit()

    remediation = Remediation(
        incident_id=incident.id,
        action="restart_service",
        status="dry_run",
        parameters={"service": "app"},
        approval_status="pending",
        attempt_count=0,
        result={"allowed": True, "executed": False},
    )
    db.add(remediation)
    db.commit()
    db.refresh(remediation)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/remediations/{remediation.id}/approve",
            json={"approved": True},
        )

        assert response.status_code == 200

        body = response.json()
        assert body["id"] == remediation.id
        assert body["approval_status"] == "approved"
        assert body["status"] == "approved"

        db.expire_all()
        saved_remediation = db.get(Remediation, remediation.id)
        saved_incident = db.get(Incident, incident.id)

        assert saved_remediation.approval_status == "approved"
        assert saved_remediation.status == "approved"
        assert saved_incident.status == "REMEDIATION_PENDING"

        events = (
            db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident.id)
            .all()
        )
        assert len(events) == 1
        assert events[0].event_type == "REMEDIATION_APPROVED"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_approve_remediation_requires_existing_remediation():
    engine, session_local = create_test_database()
    db = session_local()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            "/remediations/999/approve",
            json={"approved": True},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Remediation not found"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_approve_remediation_rejects_second_approval():
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)

    remediation = Remediation(
        incident_id=incident.id,
        action="restart_service",
        status="approved",
        parameters={"service": "app"},
        approval_status="approved",
        attempt_count=0,
        result={"allowed": True, "executed": False},
    )
    db.add(remediation)
    db.commit()
    db.refresh(remediation)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/remediations/{remediation.id}/approve",
            json={"approved": True},
        )

        assert response.status_code == 409
        assert "cannot be approved" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_approve_remediation_requires_positive_approval():
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)

    remediation = Remediation(
        incident_id=incident.id,
        action="restart_service",
        status="dry_run",
        parameters={"service": "app"},
        approval_status="pending",
        attempt_count=0,
        result={"allowed": True, "executed": False},
    )
    db.add(remediation)
    db.commit()
    db.refresh(remediation)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/remediations/{remediation.id}/approve",
            json={"approved": False},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Remediation approval must be true"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
