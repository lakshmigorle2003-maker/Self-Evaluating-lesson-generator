# Self-Evaluating Lesson Content Generator

An agentic system that writes a beginner lesson on a topic, grades it against
a hard pass/fail rubric enforced in code, and regenerates on failure —
deciding on its own whether the lesson is good enough to ship.

Built with **LangGraph** (generate → evaluate → regenerate loop) and the
**Gemini API** (via `langchain-google-genai`).

```
topic ──▶ generate ──▶ evaluate ──▶ pass? ──yes──▶ finalize ──▶ lesson.md
             ▲                        │                          + rejection_log.md
             └────── no, retries left ┘                           + trace.json
```

📖 **Docs:** [Overview](docs/OVERVIEW.md) · [Design rationale](DESIGN.md) · [Per-file walkthroughs](docs/code/)

---

## Requirements

- Python 3.10+
- A free Gemini API key — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

## Setup

```bash
git clone <this-repo>
cd self-evaluating-lesson-generator

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your key into GOOGLE_API_KEY=
```

## Usage

### CLI

```bash
python main.py --topic "Introduction to RAG"
```

| Flag | Purpose |
|---|---|
| `--max-retries N` | Override the retry budget |
| `--generator-model` / `--evaluator-model` | Override the configured models |
| `--no-memory` | Disable the persistent pitfall memory for this run |
| `--no-example` | Only write to `runs/`, skip the `examples/` mirror |

Full list: `python main.py --help`.

Exit code: `0` = passed the full rubric, `2` = shipped best-effort after
exhausting retries, `1` = configuration or run error.

### Web UI

```bash
python main.py serve      # FastAPI + React app on http://localhost:3000
```

The React source lives in `frontend-react/`; run `npm run build` there after
UI changes so FastAPI picks up the new build.

## Output

Every run is written to `runs/<timestamp>__<topic-slug>/` and mirrored into
`examples/<topic-slug>/` (the latter is meant to be committed):

| File | Contents |
|---|---|
| `lesson.md` | The final lesson — the passing draft, or the best-effort draft if none passed |
| `rejection_log.md` | Human-readable: what failed on each attempt, why, and what fed into the next attempt |
| `rejection_log.json` | The same, structured |
| `trace.json` | Full text + full evaluation of every attempt |

The CLI also prints a live summary as it runs:

```
╭──────────────── lesson-forge ────────────────╮
│ Topic: Introduction to RAG                   │
│ Generator model: gemini-3.5-flash            │
│ Evaluator model: gemini-2.5-flash            │
│ Max retries: 2 (up to 3 total attempts)      │
│ Memory: enabled, 1 known pitfall(s) injected │
╰──────────────────────────────────────────────╯
    Attempt-by-attempt rubric outcome
┏━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Attempt ┃ Passed? ┃ Failed checkpoints ┃
┡━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ 1       │ no      │ C7                 │
│ 2       │ yes     │ -                  │
└─────────┴─────────┴────────────────────┘
```

## How "good enough" is decided

The lesson is graded against **13 hard pass/fail checkpoints** across six
dimensions: accurate & grounded, beginner-friendly language, teaches by
example, no unexplained jargon, covers the key points, coherent teaching
flow. There's no partial credit — one failed checkpoint fails the whole
lesson, and pass/fail is computed in code from the judge's per-checkpoint
verdicts, never trusted as a single yes/no from the model.

- Full rubric: [`app/rubric.py`](app/rubric.py)
- Full rationale: [DESIGN.md](DESIGN.md)

On a failed checkpoint, the judge's specific reason is fed back into the
next generation attempt (2 retries by default, so the loop always
terminates). A small persistent memory (`memory/memory_store.json`) tracks
which checkpoints fail repeatedly across *all* past runs and warns the
generator about those recurring pitfalls before it writes a first draft.

## Tests

Runs fully offline — no API key, no network calls — against scripted fake
LLM clients (`tests/fakes.py`):

```bash
pytest -v
```

30 tests covering: first-attempt pass; fail-then-pass-on-retry with correct
feedback threading; exhausting retries and still terminating with the
least-bad attempt; a judge that omits a checkpoint counted as a **fail**,
never a silent pass; memory pitfalls injected into prompts; a corrupted
memory file never crashing a run.

## Project layout

See [DESIGN.md §10](DESIGN.md#10-project-layout) for the annotated tree.

## Submission

| Deliverable | Where |
|---|---|
| GitHub repo + setup/run instructions | This README, [DESIGN.md](DESIGN.md), [docs/](docs/) |
| Final lesson content | [`examples/introduction-to-rag/lesson.md`](examples/introduction-to-rag/lesson.md) — *(add Google Doc / Notion link here)* |
| Loom video (15–20 min) | *(add recorded link here)* — script: [docs/VIDEO_SCRIPT.md](docs/VIDEO_SCRIPT.md) |
