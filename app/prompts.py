

from __future__ import annotations

from app.rubric import RUBRIC, rubric_as_prompt_block
from app.schemas import CheckpointVerdict

AUDIENCE_DESCRIPTION = (
    "The reader is a 12th-grade graduate from India who wants to start a career "
    "in AI. They do not come from an English-medium school, so their English "
    "vocabulary is limited -- avoid idioms, rare words, and long academic "
    "sentences. They have never studied this topic before: assume zero "
    "background, not even adjacent technical concepts."
)

GENERATOR_SYSTEM_PROMPT = f"""You are an expert teacher who writes beginner lessons for learners just \
starting an AI career.

{AUDIENCE_DESCRIPTION}

Write a single, standalone, beginner lesson in Markdown that:
1. States plainly WHAT the topic is.
2. Explains WHY it matters -- what problem it solves, when someone would use it.
3. Explains HOW it works, as a sequence of simple, understandable steps.
4. Includes at least one concrete, fully-walked-through example or everyday-life \
analogy that makes the mechanism click.
5. Defines every technical term in plain language the first time it is used. \
Never assume a word is already known.
6. Uses short sentences and common words. No idioms, no unnecessary jargon.
7. Follows a clear shape: a short introduction, a body that teaches the \
concept step by step, and a closing "Key Takeaways" recap.

Write only the lesson itself in Markdown (use headings), with no meta-commentary \
about the task, no "Sure, here is..." preamble, and no mention of a rubric or \
grading."""


def build_generation_prompt(
    topic: str,
    *,
    feedback: str | None = None,
    memory_pitfalls: list[str] | None = None,
) -> str:
    """Build the user-turn prompt for one generation attempt.

    `feedback` carries the specific, per-checkpoint reasons the previous
    attempt failed (empty on the first attempt). `memory_pitfalls` carries
    standing guidance synthesized from failures across *past runs* (the
    self-evolving memory layer) -- see memory.py.
    """
    parts = [f"Topic for this lesson: {topic}"]

    if memory_pitfalls:
        pitfalls_block = "\n".join(f"- {p}" for p in memory_pitfalls)
        parts.append(
            "Lessons like this one have repeatedly failed review for the "
            "following reasons in the past. Proactively avoid these problems:\n"
            f"{pitfalls_block}"
        )

    if feedback:
        parts.append(
            "IMPORTANT: A previous draft of this exact lesson was rejected. "
            "Here is exactly what failed and why:\n"
            f"{feedback}\n"
            "Rewrite the lesson from scratch, fixing every issue listed above. "
            "Keep whatever worked, but do not simply patch the old draft -- make "
            "sure each fix is real and specific to the reason given, not a "
            "surface-level rewording."
        )

    return "\n\n".join(parts)


EVALUATOR_SYSTEM_PROMPT = f"""You are a strict but fair curriculum reviewer. You grade a beginner \
lesson against a fixed rubric of pass/fail checkpoints. You are not the person who \
wrote the lesson, and you do not give credit for good intentions.

{AUDIENCE_DESCRIPTION}

Rules:
- Judge strictly from the lesson text given to you. Do not reward length or \
confident tone by themselves.
- Every checkpoint is boolean: it either clearly passes or it clearly fails. \
There is no partial credit. If you are unsure whether a checkpoint is met, mark \
it as failed and explain what is missing.
- You must return a verdict for every single checkpoint id listed below -- do \
not skip any, and do not invent new ones.
- Each reason must cite something concrete and specific from the lesson text \
(quote or closely paraphrase it), not a generic statement.

Rubric checkpoints:
{rubric_as_prompt_block()}"""


def build_evaluation_prompt(topic: str, lesson_markdown: str) -> str:
    return (
        f"Topic the lesson is supposed to teach: {topic}\n\n"
        "Lesson to grade (Markdown):\n"
        "-----BEGIN LESSON-----\n"
        f"{lesson_markdown}\n"
        "-----END LESSON-----\n\n"
        "Return a verdict for every rubric checkpoint id."
    )


def build_regeneration_feedback(
    verdicts: list[CheckpointVerdict],
) -> str:
    """Turn failed checkpoint verdicts into the feedback block fed back to
    the generator on the next attempt."""
    from app.rubric import describe_checkpoint

    failed = [v for v in verdicts if not v.passed]
    if not failed:
        return ""
    lines = []
    for v in failed:
        lines.append(f"- {describe_checkpoint(v.checkpoint_id)}\n  Why it failed: {v.reason}")
    return "\n".join(lines)


# Sanity check at import time: every checkpoint referenced by RUBRIC exists
# in the rendered prompt block. Cheap, catches typos immediately.
assert all(c.id in rubric_as_prompt_block() for c in RUBRIC)
