from abc import ABC, abstractmethod

from app.evidence.schemas import EvidenceBundle, RCAResult


class RCAEngine(ABC):
    @abstractmethod
    def analyze(self, evidence: EvidenceBundle) -> RCAResult:
        """Analyze incident evidence and return a structured RCA."""
        raise NotImplementedError
