from datetime import datetime

from pydantic import BaseModel, Field


class IncidentEvidence(BaseModel):
    incident_id: int
    incident_key: str
    status: str
    severity: str
    title: str
    description: str | None = None


class AlertEvidence(BaseModel):
    alert_name: str
    status: str
    severity: str
    summary: str | None = None
    description: str | None = None
    labels: dict = Field(default_factory=dict)
    annotations: dict = Field(default_factory=dict)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class MetricEvidence(BaseModel):
    name: str
    query: str
    value: float | None = None
    unit: str | None = None
    observed_at: datetime | None = None


class LogEvidence(BaseModel):
    timestamp: datetime | None = None
    level: str | None = None
    message: str
    fields: dict = Field(default_factory=dict)


class DeploymentEvidence(BaseModel):
    version: str | None = None
    commit: str | None = None
    deployed_at: datetime | None = None
    description: str | None = None


class EvidenceBundle(BaseModel):
    incident: IncidentEvidence
    alerts: list[AlertEvidence] = Field(default_factory=list)
    metrics: list[MetricEvidence] = Field(default_factory=list)
    logs: list[LogEvidence] = Field(default_factory=list)
    deployment: DeploymentEvidence | None = None
