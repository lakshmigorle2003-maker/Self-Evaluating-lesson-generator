"""LangGraph state definition for the generate -> evaluate -> regenerate loop."""

from __future__ import annotations

from typing import TypedDict

from app.schemas import EvaluationResult, LessonAttempt


class LessonState(TypedDict, total=False):
    topic: str
    max_retries: int
    memory_pitfalls: list[str]

    attempt_number: int  # how many generations have happened so far
    current_lesson: str
    current_evaluation: EvaluationResult
    current_passed: bool
    attempts_log: list[LessonAttempt]

    final_lesson: str
    final_attempt_number: int
    final_passed: bool
