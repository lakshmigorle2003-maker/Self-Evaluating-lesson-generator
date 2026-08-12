

from __future__ import annotations

import time
from typing import TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

from app.config import Settings

T = TypeVar("T", bound=BaseModel)


def _require_api_key(settings: Settings) -> None:
    if not settings.google_api_key:
        raise RuntimeError(
            "No Gemini API key found. Set GOOGLE_API_KEY (or GEMINI_API_KEY) in "
            "your environment or in a .env file at the project root. "
            "Get a free key at https://aistudio.google.com/apikey"
        )


def build_generator_llm(settings: Settings) -> ChatGoogleGenerativeAI:
    """Plain text-generation model used to write the lesson."""
    _require_api_key(settings)
    return ChatGoogleGenerativeAI(
        model=settings.generator_model,
        google_api_key=settings.google_api_key,
        temperature=settings.generation_temperature,
    )


def build_evaluator_llm(settings: Settings, schema: type[T]):
  
    _require_api_key(settings)
    base = ChatGoogleGenerativeAI(
        model=settings.evaluator_model,
        google_api_key=settings.google_api_key,
        temperature=settings.evaluation_temperature,
    )
    return base.with_structured_output(schema)


def extract_text(response: object) -> str:
   
    content = response.content if hasattr(response, "content") else response
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content)


def invoke_with_retry(runnable, prompt_input, *, attempts: int = 3, base_delay: float = 1.5):
    
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return runnable.invoke(prompt_input)
        except Exception as exc: 
            last_exc = exc
            if attempt == attempts:
                break
            time.sleep(base_delay * attempt)
    assert last_exc is not None
    raise last_exc
