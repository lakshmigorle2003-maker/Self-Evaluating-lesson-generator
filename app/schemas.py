"""Typed data contracts shared across the graph, memory, and output layers."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.rubric import RUBRIC_IDS


class CheckpointVerdict(BaseModel):
    """One rubric checkpoint's verdict, as returned by the evaluator LLM."""

    checkpoint_id: str = Field(description="The rubric checkpoint id, e.g. 'C7'.")
    passed: bool = Field(description="True only if the lesson clearly satisfies this checkpoint.")
    reason: str = Field(
        description=(
            "One or two sentences citing specific evidence from the lesson "
            "text that justifies the verdict. Must be specific enough to act on."
        )
    )


class EvaluationResult(BaseModel):
    """Structured output contract for the evaluator LLM call.

    Deliberately does NOT include an overall pass/fail field -- that is
    always computed deterministically in code from `verdicts`
    (see evaluator.evaluate_node), so an inconsistent judge can never soften
    the "no partial credit" rule.
    """

    verdicts: list[CheckpointVerdict] = Field(
        description="Exactly one verdict per rubric checkpoint, covering every checkpoint id."
    )
    overall_impression: str = Field(
        description="One short sentence summarizing the lesson's biggest strength or weakness."
    )


def missing_checkpoint_ids(result: EvaluationResult) -> set[str]:
    returned = {v.checkpoint_id for v in result.verdicts}
    return set(RUBRIC_IDS) - returned


class LessonAttempt(BaseModel):
    """A full record of one generate -> evaluate cycle."""

    attempt_number: int
    lesson_markdown: str
    evaluation: EvaluationResult
    passed: bool
    failed_checkpoint_ids: list[str] = Field(default_factory=list)
    feedback_given_to_next_attempt: str | None = None
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
