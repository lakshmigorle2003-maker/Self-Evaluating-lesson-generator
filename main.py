#!/usr/bin/env python3
"""Thin entrypoint: `python main.py --topic "..."`. See README.md for setup
and usage.

Run `python main.py serve` to start the FastAPI app (app/api.py) on port 3000
instead of the CLI.
"""

import sys

from app.cli import main

PORT = 3000

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        import uvicorn

        uvicorn.run("app.api:app", host="0.0.0.0", port=PORT)
    else:
        main()
