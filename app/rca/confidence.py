from app.evidence.schemas import EvidenceBundle, RCAConfidence


def calculate_confidence(evidence: EvidenceBundle) -> RCAConfidence:
    """Calculate RCA confidence from corroborating operational evidence."""
    has_alert = bool(evidence.alerts)
    metric_names = {metric.name for metric in evidence.metrics}
    has_logs = bool(evidence.logs)
    has_deployment = evidence.deployment is not None

    has_error_signal = (
        "error_rate" in metric_names
        or any(alert.alert_name == "HighErrorRate" for alert in evidence.alerts)
    )

    has_latency_signal = (
        "http_p95_latency" in metric_names
        or "db_p95_latency" in metric_names
        or any(alert.alert_name == "HighLatency" for alert in evidence.alerts)
    )

    has_health_signal = (
        "app_health" in metric_names
        or "db_health" in metric_names
        or any(
            alert.alert_name in {"ServiceDown", "DatabaseUnavailable"}
            for alert in evidence.alerts
        )
    )

    operational_signals = sum(
        [
            has_error_signal,
            has_latency_signal,
            has_health_signal,
        ]
    )

    corroboration = sum(
        [
            has_alert and bool(metric_names),
            bool(metric_names) and has_logs,
            has_alert and has_logs,
        ]
    )

    if corroboration > 0:
        return RCAConfidence.HIGH

    if operational_signals > 0 or has_deployment:
        return RCAConfidence.MEDIUM

    return RCAConfidence.LOW
