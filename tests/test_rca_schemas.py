from app.evidence.schemas import RCAEvidence, RCAResult


def test_rca_result_accepts_structured_analysis():
    result = RCAResult(
        root_cause="Database latency increased",
        confidence="high",
        evidence=[
            RCAEvidence(
                source="prometheus",
                reference="db_latency",
                reasoning="Database latency increased during the incident.",
            )
        ],
        impact="Task API requests became slow.",
        contributing_factors=["Increased database latency"],
        recommended_action="Investigate database performance",
        verification_steps=["Check database latency", "Check API response time"],
    )

    assert result.root_cause == "Database latency increased"
    assert result.confidence == "high"
    assert len(result.evidence) == 1
    assert result.recommended_action == "Investigate database performance"


def test_rca_result_allows_unknown_root_cause():
    result = RCAResult(
        root_cause="Unknown root cause",
        confidence="low",
        impact="Service impact observed.",
        recommended_action="Collect additional evidence",
    )

    assert result.root_cause == "Unknown root cause"
    assert result.confidence == "low"
    assert result.evidence == []
