from typing import Any

from google import genai

from app.config import settings
from app.evidence.schemas import EvidenceBundle, RCAResult
from app.rca.engine import RCAEngine
from app.rca.openai_engine import RCA_INSTRUCTIONS


class GeminiRCAEngine(RCAEngine):
    def __init__(
        self,
        client: Any | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        resolved_api_key = api_key or settings.gemini_api_key

        if client is None and not resolved_api_key:
            raise ValueError("Gemini API key is required")

        self.client = client or genai.Client(api_key=resolved_api_key)
        self.model = model or settings.gemini_model

    def analyze(self, evidence: EvidenceBundle) -> RCAResult:
        response = self.client.models.generate_content(
            model=self.model,
            contents=evidence.model_dump_json(),
            config={
                "system_instruction": RCA_INSTRUCTIONS,
                "response_mime_type": "application/json",
                "response_schema": RCAResult,
            },
        )

        if response.parsed is None:
            raise ValueError("Gemini returned no structured RCA result")

        return response.parsed
