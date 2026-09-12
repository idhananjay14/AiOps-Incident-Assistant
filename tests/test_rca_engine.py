import pytest

from app.evidence.schemas import RCAResult
from app.rca.engine import RCAEngine


def test_rca_engine_requires_analyze_implementation():
    with pytest.raises(TypeError):
        RCAEngine()


def test_rca_result_rejects_invalid_confidence():
    with pytest.raises(ValueError):
        RCAResult(
            root_cause="Unknown root cause",
            confidence="certain",
            impact="Service impact observed.",
            recommended_action="Collect additional evidence",
        )
