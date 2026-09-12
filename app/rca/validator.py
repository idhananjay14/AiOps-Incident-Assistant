from app.evidence.schemas import EvidenceBundle, RCAResult

VALID_SOURCES = {
    "incident",
    "alert",
    "prometheus",
    "loki",
    "deployment",
}


def validate_rca(result: RCAResult, evidence: EvidenceBundle) -> None:
    """Validate that every RCA evidence citation exists in the evidence bundle."""
    for citation in result.evidence:
        if citation.source not in VALID_SOURCES:
            raise ValueError(
                f"Unsupported RCA evidence source: {citation.source}"
            )

        if citation.source == "incident":
            references = {
                evidence.incident.incident_key,
                str(evidence.incident.incident_id),
            }
        elif citation.source == "alert":
            references = {alert.alert_name for alert in evidence.alerts}
        elif citation.source == "prometheus":
            references = {metric.name for metric in evidence.metrics}
        elif citation.source == "loki":
            references = {log.message for log in evidence.logs}
        else:
            references = {
                value
                for value in (
                    evidence.deployment.version if evidence.deployment else None,
                    evidence.deployment.commit if evidence.deployment else None,
                )
                if value is not None
            }

        if citation.reference not in references:
            raise ValueError(
                "RCA evidence citation does not exist in the evidence bundle: "
                f"{citation.source}:{citation.reference}"
            )
