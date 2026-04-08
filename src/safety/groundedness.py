from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GroundednessCheckResult(BaseModel):
    weakly_grounded: bool
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


def evaluate_groundedness(
    *,
    observations_count: int,
    refs_count: int,
    hypotheses_count: int,
) -> GroundednessCheckResult:
    warnings: list[str] = []

    if hypotheses_count == 0:
        return GroundednessCheckResult(
            weakly_grounded=False,
            warnings=[],
        )

    if observations_count == 0 and refs_count == 0:
        warnings.append(
            "Groundedness is weak; generated hypotheses are not corroborated by "
            "observations or references."
        )
    elif refs_count == 0:
        warnings.append(
            "Groundedness is limited; hypotheses rely on live observations without "
            "corroborating references."
        )
    elif observations_count == 0:
        warnings.append(
            "Groundedness is limited; hypotheses rely on references without live "
            "operational observations."
        )

    return GroundednessCheckResult(
        weakly_grounded=bool(warnings),
        warnings=warnings,
    )
