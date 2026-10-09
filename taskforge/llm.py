"""OpenAI client (official SDK, structured outputs). Returns None when no key is set or the API fails."""
from __future__ import annotations

import os
import time
from typing import TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()
T = TypeVar("T", bound=BaseModel)
DEFAULT_MODEL = "gpt-4.1-nano"
last_error: str | None = None
calls = 0  # API calls made by this process, for the eval's cost column
tokens = {"input": 0, "output": 0}


def available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def model_name() -> str:
    return os.getenv("OPENAI_MODEL") or DEFAULT_MODEL


def structured(prompt: str, schema: type[T], retries: int = 3) -> T | None:
    global last_error, calls
    if not available():
        return None
    from openai import OpenAI
    client = OpenAI(base_url=os.getenv("OPENAI_BASE_URL") or None)
    for i in range(retries):
        try:
            r = client.chat.completions.parse(model=model_name(), messages=[{"role": "user", "content": prompt}],
                                              response_format=schema)
            calls += 1
            if r.usage:
                tokens["input"] += r.usage.prompt_tokens
                tokens["output"] += r.usage.completion_tokens
            if r.choices[0].message.parsed is not None:
                return r.choices[0].message.parsed
            last_error = f"no parsed output: {r.choices[0].message.refusal or r.choices[0].finish_reason}"
        except Exception as e:  # rate limit / transient
            last_error = f"{type(e).__name__}: {str(e)[:300]}"
            time.sleep(2 ** i)
    return None
