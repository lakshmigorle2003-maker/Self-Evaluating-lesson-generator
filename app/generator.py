

from __future__ import annotations

from typing import Protocol

from app.llm import extract_text, invoke_with_retry
from app.prompts import GENERATOR_SYSTEM_PROMPT, build_generation_prompt, build_regeneration_feedback
from app.state import LessonState


class GeneratorLLM(Protocol):
    def invoke(self, messages: list) -> object: ...


def build_generate_node(generator_llm: GeneratorLLM):
    def generate_node(state: LessonState) -> dict:
        attempts_log = state.get("attempts_log", [])
        feedback = None
        if attempts_log:
            last = attempts_log[-1]
            feedback = build_regeneration_feedback(last.evaluation.verdicts)

        user_prompt = build_generation_prompt(
            state["topic"],
            feedback=feedback,
            memory_pitfalls=state.get("memory_pitfalls") or [],
        )
        messages = [
            ("system", GENERATOR_SYSTEM_PROMPT),
            ("human", user_prompt),
        ]
        response = invoke_with_retry(generator_llm, messages)
        lesson_text = extract_text(response)

        return {
            "current_lesson": lesson_text,
            "attempt_number": state.get("attempt_number", 0) + 1,
        }

    return generate_node
