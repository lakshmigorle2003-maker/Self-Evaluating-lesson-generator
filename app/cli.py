
from __future__ import annotations

import argparse
import dataclasses
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.config import get_settings
from app.loop import build_graph
from app.llm import build_evaluator_llm, build_generator_llm
from app.memory import MemoryStore
from app.output import write_run_artifacts
from app.schemas import EvaluationResult

console = Console()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lesson-forge",
        description=(
            "Generate a beginner lesson, grade it against a hard pass/fail rubric, "
            "and regenerate on failure until it passes or retries run out."
        ),
    )
    parser.add_argument(
        "--topic",
        default="RAG (Retrieval-Augmented Generation)",
        help="The topic to teach, assuming the learner starts from zero.",
    )
    parser.add_argument("--max-retries", type=int, default=None, help="Override MAX_RETRIES from config.")
    parser.add_argument("--generator-model", default=None, help="Override GENERATOR_MODEL from config.")
    parser.add_argument("--evaluator-model", default=None, help="Override EVALUATOR_MODEL from config.")
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable the persistent cross-run memory (no pitfall injection, no run recorded).",
    )
    parser.add_argument(
        "--no-example",
        action="store_true",
        help="Do not mirror the output into examples/<topic-slug>/ (only write to runs/).",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the rich summary output.")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()

    overrides = {}
    if args.max_retries is not None:
        overrides["max_retries"] = args.max_retries
    if args.generator_model:
        overrides["generator_model"] = args.generator_model
    if args.evaluator_model:
        overrides["evaluator_model"] = args.evaluator_model
    if args.no_memory:
        overrides["memory_enabled"] = False
    if overrides:
        settings = dataclasses.replace(settings, **overrides)

    try:
        generator_llm = build_generator_llm(settings)
        evaluator_llm = build_evaluator_llm(settings, EvaluationResult)
    except RuntimeError as exc:
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        return 1

    memory_store = MemoryStore(settings.memory_path) if settings.memory_enabled else None

    memory_pitfalls: list[str] = []
    if memory_store is not None:
        memory_pitfalls = memory_store.get_pitfalls_for_generation(
            threshold=settings.memory_failure_threshold,
            max_pitfalls=settings.memory_max_pitfalls,
        )

    if not args.quiet:
        console.print(
            Panel.fit(
                f"[bold]Topic:[/bold] {args.topic}\n"
                f"[bold]Generator model:[/bold] {settings.generator_model}\n"
                f"[bold]Evaluator model:[/bold] {settings.evaluator_model}\n"
                f"[bold]Max retries:[/bold] {settings.max_retries} "
                f"(up to {settings.max_retries + 1} total attempts)\n"
                f"[bold]Memory:[/bold] {'enabled, ' + str(len(memory_pitfalls)) + ' known pitfall(s) injected' if memory_store else 'disabled'}",
                title="lesson-forge",
            )
        )

    graph = build_graph(generator_llm, evaluator_llm, memory_store=memory_store)

    initial_state = {
        "topic": args.topic,
        "max_retries": settings.max_retries,
        "memory_pitfalls": memory_pitfalls,
        "attempt_number": 0,
        "attempts_log": [],
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]Run failed:[/bold red] {exc}")
        return 1

    run_dir = write_run_artifacts(
        output_dir=settings.output_dir,
        examples_dir=settings.examples_dir,
        topic=args.topic,
        final_lesson=final_state["final_lesson"],
        final_passed=final_state["final_passed"],
        final_attempt_number=final_state["final_attempt_number"],
        attempts_log=final_state["attempts_log"],
        generator_model=settings.generator_model,
        evaluator_model=settings.evaluator_model,
        save_as_example=not args.no_example,
    )

    if not args.quiet:
        _print_summary(final_state, run_dir)

    return 0 if final_state["final_passed"] else 2


def _print_summary(final_state: dict, run_dir) -> None:
    status = "[bold green]PASSED[/bold green]" if final_state["final_passed"] else "[bold yellow]DID NOT PASS (best effort shipped)[/bold yellow]"
    console.print(
        Panel.fit(
            f"Result: {status}\n"
            f"Attempts used: {len(final_state['attempts_log'])}\n"
            f"Final attempt: #{final_state['final_attempt_number']}\n"
            f"Artifacts written to: {run_dir}",
            title="Run complete",
        )
    )

    table = Table(title="Attempt-by-attempt rubric outcome")
    table.add_column("Attempt")
    table.add_column("Passed?")
    table.add_column("Failed checkpoints")
    for attempt in final_state["attempts_log"]:
        table.add_row(
            str(attempt.attempt_number),
            "yes" if attempt.passed else "no",
            ", ".join(attempt.failed_checkpoint_ids) if attempt.failed_checkpoint_ids else "-",
        )
    console.print(table)


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
