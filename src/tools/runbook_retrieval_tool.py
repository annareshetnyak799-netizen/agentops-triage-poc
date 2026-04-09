from __future__ import annotations

import re
from pathlib import Path
from time import monotonic

from src.domain.enums import ToolCallStatus
from src.tools.base import BaseTool, ToolRequest, ToolResult

# Runbooks are stored as markdown files in src/kb/runbooks/.
# The tool performs a real filesystem lookup: exact service match first,
# then fuzzy prefix match, then the generic fallback runbook.
_KB_DIR = Path(__file__).resolve().parents[1] / "kb" / "runbooks"

# Maximum characters extracted per section heading match.
_SECTION_MAX_CHARS = 400


def _load_runbook(service: str) -> tuple[str, str] | None:
    """Return (path_label, content) for the best matching runbook file, or None."""
    # 1. Exact filename match: payments-api.md for "payments-api"
    candidate = _KB_DIR / f"{service}.md"
    if candidate.is_file():
        return (str(candidate.relative_to(_KB_DIR.parent.parent)), candidate.read_text("utf-8"))

    # 2. Prefix match: "payments" matches "payments-api.md"
    slug = service.split("-")[0].lower()
    for path in sorted(_KB_DIR.glob("*.md")):
        if path.stem.startswith(slug) and path.stem != "generic-service":
            return (str(path.relative_to(_KB_DIR.parent.parent)), path.read_text("utf-8"))

    return None


def _extract_snippets(content: str, ref: str) -> list[dict[str, str]]:
    """Split markdown into section-level snippets (one per ## heading)."""
    sections = re.split(r"\n(?=## )", content.strip())
    snippets: list[dict[str, str]] = []
    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue
        heading = lines[0].lstrip("#").strip()
        body = "\n".join(lines[1:]).strip()
        if not body:
            continue
        snippets.append({
            "title": heading,
            "content": body[:_SECTION_MAX_CHARS],
            "ref": ref,
        })
    return snippets or [{"title": "Runbook", "content": content[:_SECTION_MAX_CHARS], "ref": ref}]


class RunbookRetrievalTool(BaseTool):
    name = "runbook_retrieval_tool"

    async def execute(self, request: ToolRequest) -> ToolResult:
        started_at = monotonic()

        service = request.payload.get("service", "unknown-service")

        result = _load_runbook(service)
        if result is None:
            # Fall back to the generic runbook.
            generic = _KB_DIR / "generic-service.md"
            ref = "kb/runbooks/generic-service.md"
            content = generic.read_text("utf-8") if generic.is_file() else (
                "Correlate the incident window with recent deploys, dependency health, "
                "and endpoint-specific degradation before risky actions."
            )
        else:
            ref, content = result

        snippets = _extract_snippets(content, ref)
        latency_ms = int((monotonic() - started_at) * 1000)

        return ToolResult(
            tool_name=self.name,
            status=ToolCallStatus.SUCCESS,
            latency_ms=latency_ms,
            summary=(
                f"Retrieved {len(snippets)} runbook sections for {service} from {ref}. "
                "Key steps: deploy correlation, dependency health, retry saturation, rollback criteria."
            ),
            data={
                "service": service,
                "source": ref,
                "snippets": snippets,
            },
        )
