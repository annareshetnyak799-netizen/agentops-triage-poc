from __future__ import annotations

from src.orchestrator.context import SessionContext


def build_analysis_prompt(template: str, context: SessionContext) -> str:
    """Build the LLM analysis prompt from a template and assembled session context.

    Includes the rolling summary section (G15 / STATE_MEMORY.md §3) so the model
    has a compact view of what has been established and what remains open.
    G20: known_facts removed — observations are the single source of truth.
    """
    observations_text = (
        "\n".join(f"- {item}" for item in context.observations) or "- none"
    )
    refs_text = "\n".join(f"- {item}" for item in context.refs) or "- none"

    rs = context.rolling_summary
    what_we_know_text = (
        "\n".join(f"  * {item}" for item in rs.what_we_know) or "  * (nothing confirmed yet)"
    )
    what_we_tried_text = (
        "\n".join(f"  * {item}" for item in rs.what_we_tried) or "  * (no tools executed yet)"
    )
    open_questions_text = (
        "\n".join(f"  * {item}" for item in rs.open_questions) or "  * (none)"
    )

    return (
        f"{template.strip()}\n\n"
        f"Incident title: {context.incident_title}\n"
        f"Service: {context.service}\n"
        f"Summary: {context.summary}\n\n"
        f"Memory (rolling summary):\n"
        f"  What we know:\n{what_we_know_text}\n"
        f"  What we tried:\n{what_we_tried_text}\n"
        f"  Open questions:\n{open_questions_text}\n\n"
        f"Observations:\n{observations_text}\n\n"
        f"References:\n{refs_text}\n\n"
        "Return:\n"
        "- a concise summary of the current incident state,\n"
        "- 1 to 3 grounded hypotheses,\n"
        "- 2 to 5 practical next steps ordered by usefulness.\n"
    )
