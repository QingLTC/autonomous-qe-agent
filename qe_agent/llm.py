"""Model configuration: OpenAI-compatible endpoint supporting Meta Model API (Muse Spark) and local fallback engines."""
import os
import time
from openai import OpenAI

BASE_URL = os.getenv("LLM_BASE_URL", "https://api.meta.com/v1")
API_KEY = os.getenv("META_MODEL_API_KEY", os.getenv("LLM_API_KEY", "ollama"))
MODEL_NAME = os.getenv("LLM_MODEL", "muse-spark")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))  # seconds; the library default (10 min x 3 attempts) can freeze a run

client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=TIMEOUT, max_retries=1)


def clean_code(raw_output: str) -> str:
    lines = [l for l in raw_output.splitlines() if not l.strip().startswith("```")]
    return "\n".join(lines).strip()


CALLS = []   # one record per model call: purpose, model, seconds (None while running)
HOOK = None  # optional callback (the UI sets it to redraw the call list live)


def chat(purpose, **kwargs):
    """All model calls go through here so the UI can show where and how the model is used."""
    rec = {"purpose": purpose, "model": kwargs.get("model", MODEL_NAME), "seconds": None}
    CALLS.append(rec)
    if HOOK:
        HOOK()
    t0 = time.time()
    try:
        if "model" not in kwargs:
            kwargs["model"] = MODEL_NAME
        return client.chat.completions.create(**kwargs)
    finally:
        rec["seconds"] = round(time.time() - t0, 1)
        if HOOK:
            HOOK()
