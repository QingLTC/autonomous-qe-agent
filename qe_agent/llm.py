"""Model configuration: any OpenAI-compatible endpoint (defaults to a local Ollama server)."""
import os
import time
from openai import OpenAI

BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("LLM_API_KEY", "ollama")
MODEL_NAME = os.getenv("LLM_MODEL", "llama3.2:3b")
MAX_TOKENS = os.getenv("LLM_MAX_TOKENS")                # optional override; reasoning models spend tokens on thinking
REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT")    # optional, e.g. low / medium / high
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
    if MAX_TOKENS:
        kwargs["max_tokens"] = int(MAX_TOKENS)
    if REASONING_EFFORT:
        kwargs["extra_body"] = {**kwargs.get("extra_body", {}), "reasoning_effort": REASONING_EFFORT}
    try:
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:  # some endpoints reject reasoning_effort: retry once without it
            if REASONING_EFFORT and "reasoning" in str(e).lower():
                kwargs["extra_body"].pop("reasoning_effort", None)
                return client.chat.completions.create(**kwargs)
            raise
    finally:
        rec["seconds"] = round(time.time() - t0, 1)
        if HOOK:
            HOOK()


def family(model=None):
    """'Llama', 'Muse' or 'Model' - used for labels in the UI."""
    m = (model or MODEL_NAME).lower()
    return "Muse" if "muse" in m else "Llama" if "llama" in m else "Model"
