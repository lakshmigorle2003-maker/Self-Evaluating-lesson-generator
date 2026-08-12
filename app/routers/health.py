"""GET /api/health -- lets the frontend show which models are configured
and whether an API key is present, without exposing the key itself."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(prefix="/api", tags=["health"])


class HealthOut(BaseModel):
    status: str
    generator_model: str
    evaluator_model: str
    memory_enabled: bool
    max_retries: int
    api_key_configured: bool


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    settings = get_settings()
    return HealthOut(
        status="ok",
        generator_model=settings.generator_model,
        evaluator_model=settings.evaluator_model,
        memory_enabled=settings.memory_enabled,
        max_retries=settings.max_retries,
        api_key_configured=bool(settings.google_api_key),
    )
