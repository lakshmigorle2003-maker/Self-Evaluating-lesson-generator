"""API route modules -- one per resource: health, rubric, lessons.

Each module owns its own `APIRouter` (endpoints + request/response models +
the logic behind them) and is registered onto the FastAPI app in
`app/api.py`. Handlers call straight into the existing domain modules
(`app.config`, `app.llm`, `app.loop`, `app.memory`, `app.output`,
`app.rubric`, `app.schemas`) -- the same building blocks `app/cli.py` uses
for the terminal entrypoint.
"""
