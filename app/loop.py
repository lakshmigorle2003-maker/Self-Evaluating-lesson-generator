
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from app.evaluator import EvaluatorLLM, build_evaluate_node
from app.generator import GeneratorLLM, build_generate_node
from app.memory import MemoryStore
from app.state import LessonState


def route_after_evaluate(state: LessonState) -> Literal["generate", "finalize"]:
    if state["current_passed"]:
        return "finalize"
    total_allowed_attempts = 1 + state["max_retries"]
    if state["attempt_number"] < total_allowed_attempts:
        return "generate"
    return "finalize"


def finalize_node(state: LessonState) -> dict:
    attempts_log = state["attempts_log"]

    passing = [a for a in attempts_log if a.passed]
    if passing:
        chosen = passing[-1]
    else:
        chosen = min(attempts_log, key=lambda a: len(a.failed_checkpoint_ids))

    return {
        "final_lesson": chosen.lesson_markdown,
        "final_attempt_number": chosen.attempt_number,
        "final_passed": chosen.passed,
    }


def build_update_memory_node(memory_store: MemoryStore | None):
    def update_memory_node(state: LessonState) -> dict:
        if memory_store is not None:
            memory_store.record_run(
                topic=state["topic"],
                attempts=state["attempts_log"],
                final_passed=state["final_passed"],
            )
        return {}

    return update_memory_node


def build_graph(
    generator_llm: GeneratorLLM,
    evaluator_llm: EvaluatorLLM,
    *,
    memory_store: MemoryStore | None = None,
):
    """Compile the LangGraph state machine. Pure wiring -- no I/O happens
    until `.invoke()` is called on the result."""
    graph = StateGraph(LessonState)

    graph.add_node("generate", build_generate_node(generator_llm))
    graph.add_node("evaluate", build_evaluate_node(evaluator_llm))
    graph.add_node("finalize", finalize_node)
    graph.add_node("update_memory", build_update_memory_node(memory_store))

    graph.set_entry_point("generate")
    graph.add_edge("generate", "evaluate")
    graph.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {"generate": "generate", "finalize": "finalize"},
    )
    graph.add_edge("finalize", "update_memory")
    graph.add_edge("update_memory", END)

    return graph.compile()
