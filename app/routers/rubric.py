"""GET /api/rubric -- exposes the 13 hard pass/fail checkpoints from
app/rubric.py so the frontend can render a rubric reference without
duplicating the checkpoint text."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.rubric import RUBRIC

router = APIRouter(prefix="/api/rubric", tags=["rubric"])


class RubricCheckpointOut(BaseModel):
    id: str
    dimension: str
    question: str


class RubricOut(BaseModel):
    checkpoints: list[RubricCheckpointOut]


@router.get("", response_model=RubricOut)
def get_rubric() -> RubricOut:
    checkpoints = [
        RubricCheckpointOut(id=c.id, dimension=c.dimension.value, question=c.question)
        for c in RUBRIC
    ]
    return RubricOut(checkpoints=checkpoints)
