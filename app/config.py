

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=False)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    google_api_key: str | None = field(default_factory=lambda: os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"))
    generator_model: str = field(default_factory=lambda: _env_str("GENERATOR_MODEL", "gemini-3.5-flash"))
    evaluator_model: str = field(default_factory=lambda: _env_str("EVALUATOR_MODEL", "gemini-2.5-flash"))
    generation_temperature: float = field(default_factory=lambda: _env_float("GENERATION_TEMPERATURE", 0.7))
    evaluation_temperature: float = field(default_factory=lambda: _env_float("EVALUATION_TEMPERATURE", 0.0))

    max_retries: int = field(default_factory=lambda: _env_int("MAX_RETRIES", 2))

    memory_path: Path = field(
        default_factory=lambda: PROJECT_ROOT / _env_str("MEMORY_PATH", "memory/memory_store.json")
    )
    memory_failure_threshold: int = field(default_factory=lambda: _env_int("MEMORY_FAILURE_THRESHOLD", 2))
    memory_max_pitfalls: int = field(default_factory=lambda: _env_int("MEMORY_MAX_PITFALLS", 5))
    memory_enabled: bool = field(default_factory=lambda: _env_bool("MEMORY_ENABLED", True))

    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / _env_str("OUTPUT_DIR", "runs"))
    examples_dir: Path = field(default_factory=lambda: PROJECT_ROOT / _env_str("EXAMPLES_DIR", "examples"))


def get_settings() -> Settings:
    """Fresh Settings each call so tests can monkeypatch env vars freely."""
    return Settings()
