from __future__ import annotations

from src.orchestrator.context import SessionContext


def build_analysis_prompt(
    template: str,
    context: SessionContext,
) -> str:
    observations = "\n".join(f"- {item}" for item in context.observations) or "- none"
    refs = "\n".join(f"- {item}" for item in context.refs) or "- none"
    known_facts = "\n".join(f"- {item.value}" for item in context.known_facts) or "- none"

    return (
        f"{template.strip()}\n\n"
        f"Incident title: {context.incident_title}\n"
        f"Service: {context.service}\n"
        f"Summary: {context.summary}\n\n"
        f"Known facts:\n{known_facts}\n\n"
        f"Observations:\n{observations}\n\n"
        f"References:\n{refs}\n\n"
        "Return:\n"
        "- a concise summary of the current incident state,\n"
        "- 1 to 3 grounded hypotheses,\n"
        "- 2 to 5 practical next steps ordered by usefulness.\n"
    )

