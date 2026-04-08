from src.safety.policy import evaluate_next_steps


def test_policy_requires_approval_for_natural_language_rollback_recommendation() -> None:
    result = evaluate_next_steps(
        [
            "Review recent deploy changes for regressions.",
            "Consider rolling back the deployment if the service continues to degrade.",
        ]
    )

    assert result.requires_approval is True
    assert result.recommended_action is not None
    assert result.trigger == "rollback"
    assert "rolling back the deployment" in result.recommended_action.lower()
    assert len(result.safety_notes) >= 2
