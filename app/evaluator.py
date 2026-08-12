

from __future__ import annotations

from typing import Protocol

from app.llm import invoke_with_retry
from app.prompts import EVALUATOR_SYSTEM_PROMPT, build_evaluation_prompt, build_regeneration_feedback
from app.rubric import RUBRIC_IDS
from app.schemas import CheckpointVerdict, EvaluationResult, LessonAttempt, missing_checkpoint_ids
from app.state import LessonState


class EvaluatorLLM(Protocol):
   

    def invoke(self, messages: list) -> EvaluationResult: ...


def _fill_missing_verdicts(result: EvaluationResult) -> EvaluationResult:

    missing = missing_checkpoint_ids(result)
    if not missing:
        return result
    patched = list(result.verdicts)
    for checkpoint_id in sorted(missing):
        patched.append(
            CheckpointVerdict(
                checkpoint_id=checkpoint_id,
                passed=False,
                reason="The evaluator did not return a verdict for this checkpoint.",
            )
        )
    return EvaluationResult(verdicts=patched, overall_impression=result.overall_impression)


def build_evaluate_node(evaluator_llm: EvaluatorLLM):
    def evaluate_node(state: LessonState) -> dict:
        user_prompt = build_evaluation_prompt(state["topic"], state["current_lesson"])
        messages = [
            ("system", EVALUATOR_SYSTEM_PROMPT),
            ("human", user_prompt),
        ]
        raw_result = invoke_with_retry(evaluator_llm, messages)
        result = _fill_missing_verdicts(raw_result)

      
        passed = all(v.passed for v in result.verdicts) and {
            v.checkpoint_id for v in result.verdicts
        } >= RUBRIC_IDS
        failed_ids = [v.checkpoint_id for v in result.verdicts if not v.passed]

        attempt_record = LessonAttempt(
            attempt_number=state["attempt_number"],
            lesson_markdown=state["current_lesson"],
            evaluation=result,
            passed=passed,
            failed_checkpoint_ids=failed_ids,
            feedback_given_to_next_attempt=(
                build_regeneration_feedback(result.verdicts) if not passed else None
            ),
        )

        attempts_log = [*state.get("attempts_log", []), attempt_record]

        return {
            "current_evaluation": result,
            "current_passed": passed,
            "attempts_log": attempts_log,
        }

    return evaluate_node
