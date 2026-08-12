"""Lesson generation endpoints: run the same generate -> evaluate ->
regenerate loop app/cli.py runs for the terminal, over HTTP, and let the
frontend list/reload past runs from the artifacts app/output.py writes to
disk.

    POST /api/lessons/generate       run the loop for one topic (blocking;
                                      FastAPI runs sync `def` handlers in a
                                      threadpool, so this doesn't block
                                      other requests)
    GET  /api/lessons/runs           list past runs, newest first
    GET  /api/lessons/runs/{run_id}  reload one past run's full detail
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.llm import build_evaluator_llm, build_generator_llm
from app.loop import build_graph
from app.memory import MemoryStore
from app.output import write_run_artifacts
from app.rubric import describe_checkpoint
from app.schemas import EvaluationResult, LessonAttempt

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


# --------------------------------------------------------------- models

class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=1, description="The topic to teach, assuming the learner starts from zero.")
    max_retries: int | None = Field(None, ge=0, le=10, description="Override MAX_RETRIES from config.")
    generator_model: str | None = Field(None, description="Override GENERATOR_MODEL from config.")
    evaluator_model: str | None = Field(None, description="Override EVALUATOR_MODEL from config.")
    use_memory: bool | None = Field(None, description="Enable/disable the persistent cross-run memory for this run.")
    save_as_example: bool = Field(True, description="Also mirror artifacts into examples/<topic-slug>/.")


class CheckpointVerdictOut(BaseModel):
    checkpoint_id: str
    passed: bool
    reason: str
    question: str


class AttemptOut(BaseModel):
    attempt_number: int
    passed: bool
    lesson_markdown: str
    failed_checkpoint_ids: list[str]
    overall_impression: str
    feedback_given_to_next_attempt: str | None
    generated_at: str
    verdicts: list[CheckpointVerdictOut]


class GenerateResponse(BaseModel):
    run_id: str
    topic: str
    generator_model: str
    evaluator_model: str
    memory_pitfalls_used: list[str]
    final_passed: bool
    final_attempt_number: int
    total_attempts: int
    lesson_markdown: str
    attempts: list[AttemptOut]


class RunSummary(BaseModel):
    run_id: str
    topic: str
    timestamp: str
    final_passed: bool
    final_attempt_number: int
    total_attempts: int


# --------------------------------------------------------------- helpers

def _settings_with_overrides(request: GenerateRequest) -> Settings:
    settings = get_settings()
    overrides: dict = {}
    if request.max_retries is not None:
        overrides["max_retries"] = request.max_retries
    if request.generator_model:
        overrides["generator_model"] = request.generator_model
    if request.evaluator_model:
        overrides["evaluator_model"] = request.evaluator_model
    if request.use_memory is not None:
        overrides["memory_enabled"] = request.use_memory
    if overrides:
        settings = dataclasses.replace(settings, **overrides)
    return settings


def _attempt_to_out(attempt: LessonAttempt) -> AttemptOut:
    verdicts = [
        CheckpointVerdictOut(
            checkpoint_id=v.checkpoint_id,
            passed=v.passed,
            reason=v.reason,
            question=describe_checkpoint(v.checkpoint_id),
        )
        for v in attempt.evaluation.verdicts
    ]
    return AttemptOut(
        attempt_number=attempt.attempt_number,
        passed=attempt.passed,
        lesson_markdown=attempt.lesson_markdown,
        failed_checkpoint_ids=attempt.failed_checkpoint_ids,
        overall_impression=attempt.evaluation.overall_impression,
        feedback_given_to_next_attempt=attempt.feedback_given_to_next_attempt,
        generated_at=attempt.generated_at,
        verdicts=verdicts,
    )


# --------------------------------------------------------------- routes

@router.post("/generate", response_model=GenerateResponse)
def generate(request: GenerateRequest) -> GenerateResponse:
    settings = _settings_with_overrides(request)

    try:
        generator_llm = build_generator_llm(settings)
        evaluator_llm = build_evaluator_llm(settings, EvaluationResult)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    memory_store = MemoryStore(settings.memory_path) if settings.memory_enabled else None

    memory_pitfalls: list[str] = []
    if memory_store is not None:
        memory_pitfalls = memory_store.get_pitfalls_for_generation(
            threshold=settings.memory_failure_threshold,
            max_pitfalls=settings.memory_max_pitfalls,
        )

    graph = build_graph(generator_llm, evaluator_llm, memory_store=memory_store)

    initial_state = {
        "topic": request.topic,
        "max_retries": settings.max_retries,
        "memory_pitfalls": memory_pitfalls,
        "attempt_number": 0,
        "attempts_log": [],
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:  # noqa: BLE001 - surface any run failure as a 500 with a clear message
        raise HTTPException(status_code=500, detail=f"Lesson generation failed: {exc}") from exc

    run_dir = write_run_artifacts(
        output_dir=settings.output_dir,
        examples_dir=settings.examples_dir,
        topic=request.topic,
        final_lesson=final_state["final_lesson"],
        final_passed=final_state["final_passed"],
        final_attempt_number=final_state["final_attempt_number"],
        attempts_log=final_state["attempts_log"],
        generator_model=settings.generator_model,
        evaluator_model=settings.evaluator_model,
        save_as_example=request.save_as_example,
    )

    attempts = [_attempt_to_out(a) for a in final_state["attempts_log"]]

    return GenerateResponse(
        run_id=run_dir.name,
        topic=request.topic,
        generator_model=settings.generator_model,
        evaluator_model=settings.evaluator_model,
        memory_pitfalls_used=memory_pitfalls,
        final_passed=final_state["final_passed"],
        final_attempt_number=final_state["final_attempt_number"],
        total_attempts=len(attempts),
        lesson_markdown=final_state["final_lesson"],
        attempts=attempts,
    )


@router.get("/runs", response_model=list[RunSummary])
def list_runs() -> list[RunSummary]:
    """Scan runs/ for past artifacts, newest first. Skips any directory
    that isn't a completed run (missing rejection_log.json) since runs/ is
    scratch space and can contain partial/in-progress folders."""
    output_dir: Path = get_settings().output_dir
    if not output_dir.exists():
        return []

    summaries = []
    for run_dir in sorted(output_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        rejection_json_path = run_dir / "rejection_log.json"
        if not rejection_json_path.exists():
            continue
        try:
            data = json.loads(rejection_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        summaries.append(
            RunSummary(
                run_id=run_dir.name,
                topic=data.get("topic", ""),
                timestamp=run_dir.name.split("__", 1)[0],
                final_passed=data.get("final_passed", False),
                final_attempt_number=data.get("final_attempt_number", 0),
                total_attempts=data.get("total_attempts", 0),
            )
        )
    return summaries


@router.get("/runs/{run_id}", response_model=GenerateResponse)
def get_run(run_id: str) -> GenerateResponse:
    """Reload one past run's full detail from its on-disk artifacts.

    rejection_log.json has per-attempt verdicts/feedback but not the
    lesson text of non-final attempts; trace.json has every attempt's
    lesson text. Merged here so this returns the same shape as
    POST /generate whether the run just finished or is reloaded from disk.
    """
    output_dir: Path = get_settings().output_dir
    run_dir = output_dir / run_id
    rejection_json_path = run_dir / "rejection_log.json"
    trace_path = run_dir / "trace.json"
    lesson_path = run_dir / "lesson.md"
    if not (rejection_json_path.exists() and trace_path.exists() and lesson_path.exists()):
        raise HTTPException(status_code=404, detail=f"No such run: {run_id}")

    rejection = json.loads(rejection_json_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    lesson_markdown = lesson_path.read_text(encoding="utf-8")

    lesson_by_attempt = {a["attempt_number"]: a["lesson_markdown"] for a in trace.get("attempts", [])}

    attempts = []
    for a in rejection.get("attempts", []):
        verdicts = [
            CheckpointVerdictOut(
                checkpoint_id=v["checkpoint_id"],
                passed=v["passed"],
                reason=v["reason"],
                question=describe_checkpoint(v["checkpoint_id"]),
            )
            for v in a.get("verdicts", [])
        ]
        attempts.append(
            AttemptOut(
                attempt_number=a["attempt_number"],
                passed=a["passed"],
                lesson_markdown=lesson_by_attempt.get(a["attempt_number"], ""),
                failed_checkpoint_ids=a.get("failed_checkpoint_ids", []),
                overall_impression=a.get("overall_impression", ""),
                feedback_given_to_next_attempt=a.get("feedback_given_to_next_attempt"),
                generated_at=a.get("generated_at", ""),
                verdicts=verdicts,
            )
        )

    return GenerateResponse(
        run_id=run_id,
        topic=rejection.get("topic", trace.get("topic", "")),
        generator_model=trace.get("generator_model", ""),
        evaluator_model=trace.get("evaluator_model", ""),
        memory_pitfalls_used=[],
        final_passed=rejection.get("final_passed", False),
        final_attempt_number=rejection.get("final_attempt_number", 0),
        total_attempts=rejection.get("total_attempts", len(attempts)),
        lesson_markdown=lesson_markdown,
        attempts=attempts,
    )
