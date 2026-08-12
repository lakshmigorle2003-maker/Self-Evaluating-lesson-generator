# Design Document — Self-Evaluating Lesson Content Generator

This document is the "why" behind the code: what the system does, how it is
put together, and the reasoning behind each structural choice. For "how do
I run it," see [README.md](README.md).

## 1. What the assignment is actually asking for

The brief is explicit that this isn't a prompt-writing exercise: *"building
and owning an agentic system that generates learning content and judges its
own quality — deciding whether that content is good enough to ship."* Two
things follow from that framing, and both shaped the architecture:

1. **The judge has to be a separate, structured step, not a vibe check.**
   If "good enough" is decided by the same call that wrote the lesson, or by
   a fuzzy "rate this 1–10," the system isn't really deciding anything — it's
   rationalizing. The rubric has to produce a verdict a machine can act on.
2. **The loop has to be a real control-flow object, not prose.** "Generate,
   evaluate, and regenerate until good enough" is a state machine with a
   cycle in it. That's what pushed the choice toward LangGraph over a plain
   LangChain chain (chains are naturally acyclic) or an n8n workflow (harder
   to unit-test the routing logic in isolation, and this needed to run
   fully offline in CI).

## 2. Architecture

```
                 ┌─────────────────────────────────────────────┐
                 │                 memory store                │
                 │   (checkpoint fail/pass counts, JSON file)   │
                 └───────────────┬───────────────┬─────────────┘
                                  │ read pitfalls  │ write after run
                                  ▼               │
   topic ──▶ ┌──────────┐   ┌──────────┐   ┌──────┴───────┐
             │ generate │──▶│ evaluate │──▶│ route         │
             └────▲─────┘   └──────────┘   │ (pass/fail/   │
                  │               ▲        │  retries left)│
                  │ feedback:     │        └───┬───────┬───┘
                  │ failed        │  regenerate │       │ retries exhausted
                  │ checkpoints   └─────────────┘       │ or pass
                  │              (loop back to generate)│
                  └──────────────────────────────────────┘
                                                          ▼
                                                     ┌──────────┐
                                                     │ finalize │  best passing attempt,
                                                     └────┬─────┘  or best-effort if none passed
                                                          ▼
                                                lesson.md + rejection_log.{md,json} + trace.json
```

This is implemented as a five-node LangGraph, split across three files by
responsibility — `app/generator.py` (writes a draft), `app/evaluator.py`
(grades a draft), `app/loop.py` (wires the two into the cycle and decides
when to stop):

`generate → evaluate → route_after_evaluate → {generate | finalize} → update_memory → END`

- **`generate`** (`app/generator.py`) calls the generator LLM with the topic,
  plus (from attempt 2 onward) the specific rubric checkpoints the previous
  draft failed, plus (every attempt) any standing "known pitfall" hints from
  the persistent memory store.
- **`evaluate`** (`app/evaluator.py`) calls a *separate* LLM, bound to a
  Pydantic schema via LangChain's `with_structured_output`, and gets back one
  verdict per rubric checkpoint — never free text that has to be parsed with
  a regex.
- **`route_after_evaluate`**, **`finalize`**, **`update_memory`**
  (`app/loop.py`) are plain Python, not LLM calls: pass → done; fail with
  retries left → loop back to `generate`; fail with no retries left → stop
  anyway. This is what guarantees the loop terminates (§6). `finalize` picks
  the artifact to ship: the passing attempt if one exists, otherwise the
  attempt with the fewest failed checkpoints, labeled honestly as not fully
  passing. `update_memory` records every checkpoint verdict from every
  attempt of this run into the persistent store, so future runs (on this
  topic or any other) start with sharper guidance — the self-evolving piece
  (§5).

Every node function is a pure function of `(state, injected LLM clients)` —
the generator and evaluator clients are passed into `build_graph(...)`
(`app/loop.py`) rather than constructed inside the nodes. That's what makes
the entire loop-and-routing logic testable with scripted fake LLMs and zero
network calls (`tests/test_loop.py`, 7 tests covering the pass-first-try
path, the fail-then-fix path, the exhausted-retries path, and the fail-safe
path for a judge that omits a checkpoint).

## 3. Stack choices

| Choice | Why |
|---|---|
| **LangGraph** for orchestration | The control flow is a cycle (generate ↔ evaluate) with a hard exit condition, not a pipeline. LangGraph models that directly as a graph with a conditional edge, keeps state typed (`state.py`), and lets each node be tested in isolation by injecting fakes — a bare `while` loop could do the same thing, but the explicit graph makes the state machine legible and makes the termination guarantee (§6) visible in the wiring itself rather than buried in loop logic. |
| **LangChain's `with_structured_output`** for the judge | Getting a hard pass/fail per checkpoint back as free text and regexing it out is exactly the kind of brittleness this task is designed to test for. Binding the evaluator model to a Pydantic schema (`EvaluationResult`) makes "the judge returned something we can't parse" essentially impossible, and gives every verdict a typed `reason` field the regeneration step can use directly as feedback. |
| **Gemini** as the model provider | Per the brief's instruction to build with the Gemini API. `langchain-google-genai`'s `ChatGoogleGenerativeAI` drops straight into LangGraph nodes and supports structured output the same way any other LangChain chat model does, so swapping providers later (e.g. to test a different judge model) is a one-line change in `llm.py`, not a rewrite. |
| **Two different models** (generator vs. evaluator) | See §4. |
| **A plain JSON file** for memory | See §5. |

## 4. Why the evaluator is a different model call than the generator

It would be simpler to have one model write the lesson and then, in the same
conversation, ask "does this pass?" That was deliberately avoided:

- **Self-grading bias.** A model asked to critique its own immediately-prior
  output tends to be lenient toward its own phrasing and blind to the exact
  gaps it just produced (it "knows what it meant"). A fresh call with only
  the rendered Markdown — no memory of writing it — has to judge the lesson
  as a first-time reader would, which is the audience that actually matters
  here.
- **Different jobs want different settings.** The generator runs at
  `temperature=0.7` so its examples and phrasing don't feel robotic; the
  evaluator runs at `temperature=0.0` because a rubric check should give the
  same verdict on the same input every time. Splitting the calls made that
  an obvious, independent choice instead of a compromise on one shared
  setting.
- **Cost/latency shape.** The default config points the evaluator at
  `gemini-2.5-flash` (older, cheaper) and the generator at `gemini-3.5-flash`
  (newer, stronger) — grading a 13-item checklist needs consistency and
  speed more than it needs the newest model, so the newer model's budget
  goes toward the harder job (writing something a beginner will actually
  understand). Both are overridable independently via `GENERATOR_MODEL` /
  `EVALUATOR_MODEL`, including pointing both at the same model if a grader
  wants to isolate this variable. (Originally this pointed the generator at
  `gemini-2.5-pro`; Google retired that model for new API keys mid-build —
  see §9 — so the split now happens within the flash tier instead of across
  pro/flash. The reasoning above still holds, just at a different price
  point.)

## 5. The rubric: hard pass/fail, no partial credit

The six dimensions in the brief map to 13 concrete, independently-answerable
checkpoints (`app/rubric.py`):

| Dimension | Checkpoints |
|---|---|
| accurate & grounded | **C1** no fabricated facts · **C2** no misleading overstatement of certainty |
| beginner-friendly language | **C3** assumes zero background · **C4** short sentences, common words |
| teaches by example | **C5** at least one concrete example/analogy · **C6** the example is fully walked through, not dropped in |
| clear, no unexplained jargon | **C7** every technical term defined at first use · **C8** no unnecessary jargon/acronyms introduced at all |
| covers the key points | **C9** answers *what* · **C10** answers *why* · **C11** answers *how* |
| coherent teaching flow | **C12** ideas build in order, nothing used before it's introduced · **C13** clear intro → body → recap shape |

Two rules make "no partial credit" actually hold, in code, not just in the
prompt text:

1. **The overall pass/fail is computed in Python, never trusted from the
   model.** `EvaluationResult` (`app/schemas.py`) intentionally has no
   `overall_pass` field — only a list of per-checkpoint verdicts. The graph
   computes `passed = all(v.passed for v in verdicts)` itself
   (`app/evaluator.py::evaluate_node`). An LLM asked to both grade 13 items
   *and* aggregate them is exactly the kind of place inconsistency creeps in
   ("12/13 passed, close enough — pass"); removing that judgment call from
   the model removes that failure mode entirely.
2. **A missing verdict is a failure, never a pass.** If the judge's response
   is missing a checkpoint (schema-valid but incomplete),
   `app/evaluator.py::_fill_missing_verdicts` inserts a synthetic
   `passed=False` verdict for it with an explicit reason.
   An unreviewed checkpoint defaulting to "pass" would be a silent hole in
   the one part of the system meant to be strict; defaulting to "fail" costs
   nothing but an extra regeneration and is covered by
   `test_missing_checkpoint_verdict_is_treated_as_failed_not_passed`.

## 6. The regenerate loop and why it's guaranteed to terminate

`MAX_RETRIES` (default 2) bounds the loop to **1 initial generation + up to
2 regenerations = 3 total attempts**. `route_after_evaluate` is the only
place that decides whether to loop, and it is plain arithmetic on
`state["attempt_number"]` vs. `1 + state["max_retries"]` — there is no path
through the graph that can generate a 4th attempt. `finalize` always runs
after the last evaluation regardless of outcome, so the graph always
reaches `END` and always produces a lesson file. `test_terminates_and_ships_best_effort_after_exhausting_retries`
exercises the "never passes" path directly: three failing attempts, exactly
three generator calls, and the run still finishes and picks the attempt
with the fewest failed checkpoints (not just the last one) as the honest
best effort — logged plainly as not passing, never silently presented as if
it cleared the bar.

On regeneration, the feedback given to the generator is built directly from
the failed verdicts' `reason` fields (`prompts.build_regeneration_feedback`)
— the specific checkpoint description plus the judge's specific complaint,
not "try again" or a re-statement of the whole rubric. The generation prompt
also explicitly instructs the model not to reword around the problem but to
fix it for real; this is a prompt-level ask, not something the code can
enforce, and is a known limitation — see §8.

## 7. Memory & self-evolution

Two related but distinct requirements from the brief:

> MEMORY: persists across runs; learns from feedback + logs
> SELF-EVOLVING: learn from repeated failures to sharpen prompts/rubrics

Both are implemented as one mechanism (`app/memory.py`), kept
deliberately simple:

- `memory/memory_store.json` accumulates, **across every run of the whole
  system** (not scoped to one topic — jargon and beginner-friendliness
  pitfalls generalize across topics), a fail/pass count and the most recent
  distinct failure reasons for every rubric checkpoint.
- Before each generation, checkpoints whose historical fail count is at or
  above `MEMORY_FAILURE_THRESHOLD` (default 2) are surfaced as standing
  "known pitfall" hints, ranked by fail count and capped at
  `MEMORY_MAX_PITFALLS` (default 5), and injected into *every* generation
  prompt for *every* topic from then on — including the very first attempt,
  before any evaluation has happened on the current run.
- After the run, every verdict from every attempt updates the store, so the
  system's standing guidance sharpens run over run without any manual
  tuning of the prompt or rubric text.

**Why this is a deterministic aggregator and not a second "reflection" LLM
call**, stated plainly rather than left implicit: a fancier version would
periodically ask an LLM to read the last N rejection logs and propose a
rubric or prompt diff. That was left out on purpose. This system's failure
modes are already fully enumerated by the 13 checkpoints — the thing that
needs to improve run over run is *compliance* with them, not *discovery* of
new ones — so a cheap, deterministic counter gets the same practical benefit
(the generator gets warned about its own recurring blind spots) without an
extra network call, extra cost, extra latency, or an extra place for the
system to behave non-reproducibly. It's also trivially unit-testable
(`tests/test_memory.py`) with no mocking required, which a "call an LLM to
rewrite the prompt" step would not be. If the rubric itself needed to grow
over time (a genuinely new category of failure the checkpoints don't cover
yet), that's the natural next extension point, and the aggregator's
`recent_fail_reasons` per checkpoint is exactly the raw material an LLM
"propose a new checkpoint" step would consume — the plumbing for that
already exists, only the synthesis step is missing.

A corrupted or missing memory file never blocks a run — `MemoryStore._load_raw`
falls back to an empty store rather than raising (`tests/test_memory.py::test_corrupt_memory_file_does_not_crash`),
and `--no-memory` disables the whole layer for a clean-slate run.

## 8. Output: the passing lesson + a rejection log

Every run writes to a timestamped folder under `runs/` (git-ignored scratch
space) and mirrors the same four files into `examples/<topic-slug>/`
(tracked in the repo — this is the actual deliverable):

- **`lesson.md`** — the final lesson: the passing attempt, or the best-effort
  attempt if none passed, with that fact stated plainly in the rejection log.
- **`rejection_log.md`** — human-readable: for every attempt, which
  checkpoints failed and why (quoting the judge's specific reason), which
  passed, and exactly what feedback was fed into the next attempt. This is
  the artifact the brief asks for by name: *"what failed, why, and what you
  changed on retry."*
- **`rejection_log.json`** — the same information, structured, for anything
  that wants to consume it programmatically (a dashboard, a CI gate, a
  second pass of analysis).
- **`trace.json`** — the full lesson text of *every* attempt plus its full
  evaluation, for debugging and for the video walkthrough.

`examples/introduction-to-rag/` is the committed artifact for this
submission's required topic.

## 9. Known limitations and what I'd do with more time

Being direct about the gaps rather than papering over them:

- **Gemini API surface shifted mid-build.** Two things broke against a live
  API key while producing the submission run and were fixed in the code,
  not worked around at the call site: `gemini-2.5-pro` returns a hard `404`
  for new API keys ("no longer available to new users"), so the generator
  default moved to `gemini-3.5-flash` (§3); and the 3.x model family returns
  `AIMessage.content` as a list of content blocks (with an opaque thought
  signature) instead of a plain string, which `generate_node` assumed —
  `llm.extract_text()` normalizes both shapes, covered by
  `tests/test_llm_retry.py`. Neither was caught by the original test suite
  because `tests/fakes.py` only scripted plain strings — this is why the
  submission run's actual API traffic surfaced both, not `pytest`.
- **"Accurate & grounded" (C1/C2) relies on the judge model's own
  knowledge**, not a real grounding step. For a fast-moving, jargon-heavy
  topic like RAG this is a reasonable approximation but not a guarantee — a
  hardened version would give the evaluator a web-search or retrieval tool
  (Gemini supports function calling the same way any LangChain chat model
  does) so C1/C2 are checked against fetched sources instead of parametric
  memory, and would say so explicitly in the rejection log's reasons.
- **Single-judge variance.** One evaluator call, even at `temperature=0`,
  can still be inconsistent between runs on a borderline lesson. An ensemble
  (e.g. 3 judge calls, majority vote per checkpoint) would trade cost and
  latency for more stable verdicts — straightforward to add as an alternate
  `evaluate` node without touching the rest of the graph.
- **No human-in-the-loop gate.** The brief asks for a system that decides on
  its own whether content is good enough to ship, which is what this builds
  — but a production version would still want an optional pause-for-review
  node before `finalize` for content going out under an org's name, not
  because the automated judge is untrustworthy but because it's cheap
  insurance for anything published externally.
- **The regeneration prompt asks the model not to reword around a failure,
  but can't enforce it in code.** A stricter version could diff the new
  draft against the old one and specifically check whether the sentence
  containing a previously-flagged problem actually changed, as an extra
  automated checkpoint.
- **Rubric is fixed, not per-topic.** A topic with heavier math (e.g.
  "gradient descent") might warrant an extra checkpoint ("no LaTeX/notation
  without a plain-language walk-through") that a topic like RAG doesn't
  need. The memory layer's `recent_fail_reasons` is exactly the signal a
  future "propose a topic-specific checkpoint" step would use (see §7).

## 10. Project layout

```
self-evaluating-lesson-generator/
├── main.py                     # `python main.py --topic "..."` (no install/path hacks needed)
├── app/
│   ├── config.py                # env-driven settings, one source of truth
│   ├── rubric.py                 # the 13 checkpoints (§6)
│   ├── schemas.py                 # Pydantic contracts (EvaluationResult, LessonAttempt, ...)
│   ├── prompts.py                  # pure functions: (topic, feedback, pitfalls) -> prompt string
│   ├── llm.py                       # Gemini client factories + retry wrapper + content normalizer
│   ├── memory.py                     # persistent, self-evolving pitfall tracker (§7)
│   ├── state.py                       # LangGraph TypedDict state
│   ├── generator.py                    # the generate node: writes one draft (§2)
│   ├── evaluator.py                     # the evaluate node: grades one draft against the rubric (§2)
│   ├── loop.py                           # wires generate+evaluate into the cycle, routing, finalize (§2)
│   ├── output.py                       # lesson.md / rejection_log / trace.json writers (§8)
│   └── cli.py                          # argument parsing + run summary
├── tests/                        # 30 tests, all offline (fake LLMs, no API key needed)
├── docs/
│   ├── OVERVIEW.md                # short, plain-language explanation of the whole system
│   └── code/*.md                   # one short explanation per file in app/
├── memory/memory_store.json      # created on first run; git-ignored
├── runs/<timestamp>__<slug>/     # every run's full output; git-ignored scratch space
└── examples/<slug>/              # curated, committed deliverable output
```

`app/` sits directly next to `main.py` (no `src/` layer, no packaging config)
— `generator.py` / `evaluator.py` / `loop.py` map 1:1 onto "write a draft" /
"grade a draft" / "run the cycle and decide when to stop," which is the
actual shape of the state machine in §2, rather than one `graph.py` holding
all three responsibilities.
