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


def test_execute_approved_remediation_succeeds(monkeypatch):
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)
    incident.status = "REMEDIATION_PENDING"

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

    class FakeExecutionResult:
        def model_dump(self):
            return {
                "success": True,
                "action": "restart_service",
                "service": "app",
                "parameters": {"service": "app"},
                "message": "Remediation executed successfully for app",
            }

    class FakeExecutor:
        def execute(self, request):
            return FakeExecutionResult()

    monkeypatch.setattr(
        "app.incident_api.main.ControlledExecutor",
        lambda: FakeExecutor(),
    )

    class FakeVerificationResult:
        healthy = True

        def model_dump(self):
            return {
                "healthy": True,
                "service": "app",
                "message": "Service health check passed",
            }

    monkeypatch.setattr(
        "app.incident_api.main.verify_service",
        lambda service: FakeVerificationResult(),
    )

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/remediations/{remediation.id}/execute"
        )

        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "succeeded"
        assert body["attempt_count"] == 1
        assert body["result"]["success"] is True

        db.expire_all()
        saved_incident = db.get(Incident, incident.id)
        assert saved_incident.status == "VERIFYING"

        events = (
            db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident.id)
            .all()
        )
        assert [event.event_type for event in events] == [
            "REMEDIATION_EXECUTING",
            "REMEDIATION_SUCCEEDED",
        ]
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_execute_remediation_requires_approval():
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
            f"/remediations/{remediation.id}/execute"
        )

        assert response.status_code == 409
        assert "must be approved" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_execute_remediation_requires_existing_remediation():
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
        response = client.post("/remediations/999/execute")

        assert response.status_code == 404
        assert response.json()["detail"] == "Remediation not found"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_first_execution_failure_keeps_circuit_closed(monkeypatch):
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)
    incident.status = "REMEDIATION_PENDING"

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

    class FakeExecutor:
        def execute(self, request):
            raise RuntimeError("Docker restart failed")

    monkeypatch.setattr(
        "app.incident_api.main.ControlledExecutor",
        lambda: FakeExecutor(),
    )

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/remediations/{remediation.id}/execute"
        )

        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "failed"
        assert body["attempt_count"] == 1
        assert body["result"]["success"] is False

        db.expire_all()
        saved_incident = db.get(Incident, incident.id)
        assert saved_incident.status == "REMEDIATION_PENDING"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_second_execution_failure_escalates(monkeypatch):
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)
    incident.status = "REMEDIATION_PENDING"

    remediation = Remediation(
        incident_id=incident.id,
        action="restart_service",
        status="approved",
        parameters={"service": "app"},
        approval_status="approved",
        attempt_count=1,
        result={"success": False, "error": "Previous failure"},
    )
    db.add(remediation)
    db.commit()
    db.refresh(remediation)

    class FakeExecutor:
        def execute(self, request):
            raise RuntimeError("Docker restart failed again")

    monkeypatch.setattr(
        "app.incident_api.main.ControlledExecutor",
        lambda: FakeExecutor(),
    )

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/remediations/{remediation.id}/execute"
        )

        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "escalated"
        assert body["attempt_count"] == 2
        assert body["result"]["success"] is False

        db.expire_all()
        saved_incident = db.get(Incident, incident.id)
        assert saved_incident.status == "ESCALATED"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_execute_remediation_rejects_open_circuit():
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)
    incident.status = "REMEDIATION_PENDING"

    remediation = Remediation(
        incident_id=incident.id,
        action="restart_service",
        status="failed",
        parameters={"service": "app"},
        approval_status="approved",
        attempt_count=2,
        result={"success": False, "error": "Repeated failure"},
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
            f"/remediations/{remediation.id}/execute"
        )

        assert response.status_code == 409
        assert "circuit breaker is open" in response.json()["detail"]

        db.expire_all()
        saved_remediation = db.get(Remediation, remediation.id)
        assert saved_remediation.status == "escalated"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_verification_failure_keeps_circuit_closed(monkeypatch):
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)
    incident.status = "REMEDIATION_PENDING"

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

    class FakeExecutionResult:
        def model_dump(self):
            return {
                "success": True,
                "action": "restart_service",
                "service": "app",
                "parameters": {"service": "app"},
                "message": "Remediation executed successfully for app",
            }

    class FakeExecutor:
        def execute(self, request):
            return FakeExecutionResult()

    class FakeVerificationResult:
        healthy = False

        def model_dump(self):
            return {
                "healthy": False,
                "service": "app",
                "message": "Health check returned HTTP 503",
            }

    monkeypatch.setattr(
        "app.incident_api.main.ControlledExecutor",
        lambda: FakeExecutor(),
    )
    monkeypatch.setattr(
        "app.incident_api.main.verify_service",
        lambda service: FakeVerificationResult(),
    )

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/remediations/{remediation.id}/execute"
        )

        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "failed"
        assert body["attempt_count"] == 1
        assert body["result"]["verification"]["healthy"] is False

        db.expire_all()
        saved_incident = db.get(Incident, incident.id)
        assert saved_incident.status == "REMEDIATION_PENDING"

        events = (
            db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident.id)
            .all()
        )
        assert events[-1].event_type == "REMEDIATION_VERIFICATION_FAILED"
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_second_verification_failure_escalates(monkeypatch):
    engine, session_local = create_test_database()
    db = session_local()

    incident = create_ready_incident(db)
    incident.status = "REMEDIATION_PENDING"

    remediation = Remediation(
        incident_id=incident.id,
        action="restart_service",
        status="approved",
        parameters={"service": "app"},
        approval_status="approved",
        attempt_count=1,
        result={"success": False, "error": "Previous verification failure"},
    )
    db.add(remediation)
    db.commit()
    db.refresh(remediation)

    class FakeExecutionResult:
        def model_dump(self):
            return {
                "success": True,
                "action": "restart_service",
                "service": "app",
                "parameters": {"service": "app"},
                "message": "Remediation executed successfully for app",
            }

    class FakeExecutor:
        def execute(self, request):
            return FakeExecutionResult()

    class FakeVerificationResult:
        healthy = False

        def model_dump(self):
            return {
                "healthy": False,
                "service": "app",
                "message": "Health check returned HTTP 503",
            }

    monkeypatch.setattr(
        "app.incident_api.main.ControlledExecutor",
        lambda: FakeExecutor(),
    )
    monkeypatch.setattr(
        "app.incident_api.main.verify_service",
        lambda service: FakeVerificationResult(),
    )

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)
        response = client.post(
            f"/remediations/{remediation.id}/execute"
        )

        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "escalated"
        assert body["attempt_count"] == 2
        assert body["result"]["verification"]["healthy"] is False

        db.expire_all()
        saved_incident = db.get(Incident, incident.id)
        assert saved_incident.status == "ESCALATED"

        events = (
            db.query(IncidentEvent)
            .filter(IncidentEvent.incident_id == incident.id)
            .all()
        )
        assert events[-1].event_type == "REMEDIATION_VERIFICATION_FAILED"
        assert events[-1].details["circuit_open"] is True
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
