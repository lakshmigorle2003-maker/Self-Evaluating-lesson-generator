

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Dimension(str, Enum):
    ACCURATE_GROUNDED = "accurate_grounded"
    BEGINNER_FRIENDLY_LANGUAGE = "beginner_friendly_language"
    TEACHES_BY_EXAMPLE = "teaches_by_example"
    NO_UNEXPLAINED_JARGON = "clear_no_unexplained_jargon"
    COVERS_KEY_POINTS = "covers_key_points"
    COHERENT_TEACHING_FLOW = "coherent_teaching_flow"


@dataclass(frozen=True)
class Checkpoint:
    id: str
    dimension: Dimension
    # Phrased so that "yes" / "true" means PASS.
    question: str


RUBRIC: tuple[Checkpoint, ...] = (
    # --- accurate & grounded ---------------------------------------------
    Checkpoint(
        id="C1",
        dimension=Dimension.ACCURATE_GROUNDED,
        question=(
            "Every factual or technical claim in the lesson is correct. "
            "There are no fabricated statistics, invented tool/product names, "
            "or claims that contradict well-established knowledge about the topic."
        ),
    ),
    Checkpoint(
        id="C2",
        dimension=Dimension.ACCURATE_GROUNDED,
        question=(
            "The lesson does not overstate certainty or oversimplify to the point "
            "of being misleading (e.g. it does not claim something always works, "
            "is the only way to do something, or is universally agreed upon when "
            "that is not true)."
        ),
    ),
    # --- beginner-friendly language ---------------------------------------
    Checkpoint(
        id="C3",
        dimension=Dimension.BEGINNER_FRIENDLY_LANGUAGE,
        question=(
            "The lesson assumes zero prior background in the topic or in adjacent "
            "technical fields. It never says something like 'as you know' or "
            "'obviously' about a concept it has not itself explained."
        ),
    ),
    Checkpoint(
        id="C4",
        dimension=Dimension.BEGINNER_FRIENDLY_LANGUAGE,
        question=(
            "Sentences are short and use common, everyday English words. A reader "
            "who is a 12th-grade graduate with a limited English vocabulary and a "
            "non-English-medium education would be able to follow the wording "
            "without needing a dictionary. There is no idiomatic, overly academic, "
            "or unnecessarily complex phrasing."
        ),
    ),
    # --- teaches by example -------------------------------------------------
    Checkpoint(
        id="C5",
        dimension=Dimension.TEACHES_BY_EXAMPLE,
        question=(
            "The lesson contains at least one concrete, worked example or "
            "everyday-life analogy that illustrates the core mechanism of the "
            "topic -- not just an abstract description of what the topic is."
        ),
    ),
    Checkpoint(
        id="C6",
        dimension=Dimension.TEACHES_BY_EXAMPLE,
        question=(
            "The example or analogy is fully walked through in plain language "
            "(what happens step by step), not just mentioned in passing."
        ),
    ),
    # --- clear, no unexplained jargon ---------------------------------------
    Checkpoint(
        id="C7",
        dimension=Dimension.NO_UNEXPLAINED_JARGON,
        question=(
            "Every technical term or acronym used in the lesson (for example "
            "words like model, embedding, vector, retrieval, corpus, index, LLM, "
            "token, prompt) is explicitly defined in plain language the first "
            "time it is used."
        ),
    ),
    Checkpoint(
        id="C8",
        dimension=Dimension.NO_UNEXPLAINED_JARGON,
        question=(
            "The lesson does not introduce jargon, acronyms, or tool/library names "
            "that are not necessary to teach the core concept. Anything mentioned "
            "only in passing without being required for understanding is avoided."
        ),
    ),
    # --- covers the key points -----------------------------------------------
    Checkpoint(
        id="C9",
        dimension=Dimension.COVERS_KEY_POINTS,
        question="The lesson clearly and explicitly answers: what is this topic?",
    ),
    Checkpoint(
        id="C10",
        dimension=Dimension.COVERS_KEY_POINTS,
        question=(
            "The lesson clearly and explicitly answers: why does this topic "
            "matter / what problem does it solve / when would someone use it?"
        ),
    ),
    Checkpoint(
        id="C11",
        dimension=Dimension.COVERS_KEY_POINTS,
        question=(
            "The lesson clearly and explicitly answers: how does this topic work, "
            "described as a sequence of understandable steps or components?"
        ),
    ),
    # --- coherent teaching flow -----------------------------------------------
    Checkpoint(
        id="C12",
        dimension=Dimension.COHERENT_TEACHING_FLOW,
        question=(
            "Ideas are introduced in an order a total beginner could follow start "
            "to finish, with each new idea building on something already "
            "explained -- no concept is used before it is introduced."
        ),
    ),
    Checkpoint(
        id="C13",
        dimension=Dimension.COHERENT_TEACHING_FLOW,
        question=(
            "The lesson has a clear shape: a short introduction that frames the "
            "topic, a body that teaches it, and a closing recap or 'key "
            "takeaways' section a reader could use to check they understood."
        ),
    ),
)

RUBRIC_BY_ID: dict[str, Checkpoint] = {c.id: c for c in RUBRIC}
RUBRIC_IDS: frozenset[str] = frozenset(RUBRIC_BY_ID)


def rubric_as_prompt_block() -> str:
    """Render the rubric as a numbered list for the evaluator prompt."""
    lines = []
    current_dimension: Dimension | None = None
    for checkpoint in RUBRIC:
        if checkpoint.dimension != current_dimension:
            current_dimension = checkpoint.dimension
            lines.append(f"\n{current_dimension.value.replace('_', ' ').upper()}")
        lines.append(f"- [{checkpoint.id}] {checkpoint.question}")
    return "\n".join(lines).strip()


def describe_checkpoint(checkpoint_id: str) -> str:
    checkpoint = RUBRIC_BY_ID.get(checkpoint_id)
    if checkpoint is None:
        return checkpoint_id
    return f"[{checkpoint.id}] ({checkpoint.dimension.value}) {checkpoint.question}"
