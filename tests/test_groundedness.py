from src.safety.groundedness import evaluate_groundedness


def test_groundedness_warns_when_hypotheses_have_no_evidence() -> None:
    result = evaluate_groundedness(
        observations_count=0,
        refs_count=0,
        hypotheses_count=1,
    )

    assert result.weakly_grounded is True
    assert result.warnings != []
    assert "not corroborated" in result.warnings[0]


def test_groundedness_is_ok_when_hypotheses_have_observations_and_refs() -> None:
    result = evaluate_groundedness(
        observations_count=2,
        refs_count=2,
        hypotheses_count=1,
    )

    assert result.weakly_grounded is False
    assert result.warnings == []
