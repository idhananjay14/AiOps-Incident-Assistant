from app.evidence.schemas import EvidenceBundle, RCAConfidence

ERROR_RATE_THRESHOLD = 0.10
HTTP_P95_LATENCY_THRESHOLD = 1.0


def calculate_confidence(evidence: EvidenceBundle) -> RCAConfidence:
    """Calculate RCA confidence from incident-relevant operational evidence."""
    metrics = {metric.name: metric.value for metric in evidence.metrics}

    has_error_signal = (
        metrics.get("error_rate") is not None
        and metrics["error_rate"] > ERROR_RATE_THRESHOLD
    ) or any(
        alert.alert_name == "HighErrorRate" for alert in evidence.alerts
    )

    has_latency_signal = (
        metrics.get("http_p95_latency") is not None
        and metrics["http_p95_latency"] > HTTP_P95_LATENCY_THRESHOLD
    ) or any(
        alert.alert_name == "HighLatency" for alert in evidence.alerts
    )

    has_app_health_signal = (
        metrics.get("app_health") is not None
        and metrics["app_health"] == 0
    ) or any(
        alert.alert_name == "ServiceDown" for alert in evidence.alerts
    )

    has_db_health_signal = (
        metrics.get("db_health") is not None
        and metrics["db_health"] == 0
    ) or any(
        alert.alert_name == "DatabaseUnavailable"
        for alert in evidence.alerts
    )

    operational_signals = sum(
        [
            has_error_signal,
            has_latency_signal,
            has_app_health_signal,
            has_db_health_signal,
        ]
    )

    has_alert = bool(evidence.alerts)
    has_logs = bool(evidence.logs)
    has_operational_signal = operational_signals > 0

    if operational_signals >= 2:
        return RCAConfidence.HIGH

    if has_operational_signal and (has_alert or has_logs):
        return RCAConfidence.HIGH

    if has_operational_signal:
        return RCAConfidence.MEDIUM

    return RCAConfidence.LOW
