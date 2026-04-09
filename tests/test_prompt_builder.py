from src.llm.prompt_builder import build_analysis_prompt
from src.orchestrator.context import SessionContext


def test_build_analysis_prompt_includes_context_sections() -> None:
    context = SessionContext(
        incident_title="High 5xx rate",
        service="payments-api",
        summary="Error rate increased after deploy",
        observations=[
            "Retrieved mock metrics for service=payments-api in environment=prod.",
            "Retrieved mock logs for service=payments-api in environment=prod.",
        ],
        refs=[
            "runbooks/payments-api.md",
            "runbooks/5xx-spike.md",
        ],
    )

    prompt = build_analysis_prompt(
        template="Analyze the incident safely.",
        context=context,
    )

    assert "Analyze the incident safely." in prompt
    assert "Incident title: High 5xx rate" in prompt
    assert "Service: payments-api" in prompt
    assert "Observations:" in prompt
    assert "References:" in prompt
    assert "runbooks/payments-api.md" in prompt
    # known_facts section removed (G20) — observations are the single source
    assert "Known facts:" not in prompt
