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
