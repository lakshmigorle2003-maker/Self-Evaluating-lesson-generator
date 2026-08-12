
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.rubric import describe_checkpoint
from app.schemas import LessonAttempt


def slugify(topic: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return slug or "lesson"


def _attempt_markdown_section(attempt: LessonAttempt) -> str:
    status = "PASSED" if attempt.passed else "FAILED"
    lines = [f"## Attempt {attempt.attempt_number} -- {status}", ""]

    passed_ids = sorted(v.checkpoint_id for v in attempt.evaluation.verdicts if v.passed)
    failed = [v for v in attempt.evaluation.verdicts if not v.passed]

    if failed:
        lines.append(f"### Failed checkpoints ({len(failed)})")
        for v in sorted(failed, key=lambda v: v.checkpoint_id):
            lines.append(f"- **{describe_checkpoint(v.checkpoint_id)}**")
            lines.append(f"  - Why it failed: {v.reason}")
        lines.append("")

    if passed_ids:
        lines.append(f"### Passed checkpoints ({len(passed_ids)}): {', '.join(passed_ids)}")
        lines.append("")

    lines.append(f"*Judge's overall impression:* {attempt.evaluation.overall_impression}")

    if attempt.feedback_given_to_next_attempt:
        lines.append("")
        lines.append("### What was fed back into the next attempt")
        lines.append(attempt.feedback_given_to_next_attempt)

    return "\n".join(lines)


def build_rejection_log_markdown(
    *,
    topic: str,
    attempts_log: list[LessonAttempt],
    final_passed: bool,
    final_attempt_number: int,
    generator_model: str,
    evaluator_model: str,
) -> str:
    header = [
        f"# Rejection Log -- {topic}",
        "",
        f"- Generator model: `{generator_model}`",
        f"- Evaluator model: `{evaluator_model}`",
        f"- Total attempts: {len(attempts_log)}",
        f"- Final result: {'PASSED all rubric checkpoints' if final_passed else 'DID NOT PASS -- shipped best-effort attempt after exhausting retries'}",
        f"- Final attempt used: {final_attempt_number}",
        "",
        "---",
        "",
    ]
    sections = [_attempt_markdown_section(a) for a in attempts_log]
    return "\n".join(header) + "\n\n---\n\n".join(sections) + "\n"


def build_rejection_log_json(
    *,
    topic: str,
    attempts_log: list[LessonAttempt],
    final_passed: bool,
    final_attempt_number: int,
) -> dict:
    return {
        "topic": topic,
        "final_passed": final_passed,
        "final_attempt_number": final_attempt_number,
        "total_attempts": len(attempts_log),
        "attempts": [
            {
                "attempt_number": a.attempt_number,
                "passed": a.passed,
                "failed_checkpoint_ids": a.failed_checkpoint_ids,
                "verdicts": [v.model_dump() for v in a.evaluation.verdicts],
                "overall_impression": a.evaluation.overall_impression,
                "feedback_given_to_next_attempt": a.feedback_given_to_next_attempt,
                "generated_at": a.generated_at,
            }
            for a in attempts_log
        ],
    }


def write_run_artifacts(
    *,
    output_dir: Path,
    examples_dir: Path,
    topic: str,
    final_lesson: str,
    final_passed: bool,
    final_attempt_number: int,
    attempts_log: list[LessonAttempt],
    generator_model: str,
    evaluator_model: str,
    save_as_example: bool = True,
) -> Path:
    """Writes lesson.md, rejection_log.md, rejection_log.json, trace.json to
    a timestamped run directory, and optionally mirrors the same artifacts
    into a stable `examples/<topic-slug>/` directory meant to be committed
    to the repo as the graded deliverable (runs/ itself is scratch space)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = slugify(topic)
    run_dir = output_dir / f"{timestamp}__{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)

    lesson_path = run_dir / "lesson.md"
    lesson_path.write_text(final_lesson, encoding="utf-8")

    rejection_md = build_rejection_log_markdown(
        topic=topic,
        attempts_log=attempts_log,
        final_passed=final_passed,
        final_attempt_number=final_attempt_number,
        generator_model=generator_model,
        evaluator_model=evaluator_model,
    )
    (run_dir / "rejection_log.md").write_text(rejection_md, encoding="utf-8")

    rejection_json = build_rejection_log_json(
        topic=topic,
        attempts_log=attempts_log,
        final_passed=final_passed,
        final_attempt_number=final_attempt_number,
    )
    (run_dir / "rejection_log.json").write_text(
        json.dumps(rejection_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    trace = {
        "topic": topic,
        "generator_model": generator_model,
        "evaluator_model": evaluator_model,
        "final_passed": final_passed,
        "final_attempt_number": final_attempt_number,
        "attempts": [
            {
                "attempt_number": a.attempt_number,
                "lesson_markdown": a.lesson_markdown,
                "passed": a.passed,
                "evaluation": a.evaluation.model_dump(),
                "generated_at": a.generated_at,
            }
            for a in attempts_log
        ],
    }
    (run_dir / "trace.json").write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")

    if save_as_example:
        example_dir = examples_dir / slug
        example_dir.mkdir(parents=True, exist_ok=True)
        (example_dir / "lesson.md").write_text(final_lesson, encoding="utf-8")
        (example_dir / "rejection_log.md").write_text(rejection_md, encoding="utf-8")
        (example_dir / "rejection_log.json").write_text(
            json.dumps(rejection_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (example_dir / "trace.json").write_text(
            json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return run_dir
