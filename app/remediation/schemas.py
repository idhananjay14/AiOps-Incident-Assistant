from pydantic import BaseModel, Field

from app.remediation.policy import RemediationAction


class RemediationRequest(BaseModel):
    incident_id: int
    action: RemediationAction
    parameters: dict = Field(default_factory=dict)
