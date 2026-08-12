#!/usr/bin/env python3
"""Thin entrypoint for the web UI: `python server.py`. Serves the API and
the static frontend on http://localhost:8000. See README.md.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=False)
