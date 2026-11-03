"""Model configuration. Every model call goes through chat().

The endpoint is any OpenAI-compatible API. Defaults: Muse Spark Open (a Meta open-weight model) on Baseten;
set LLM_API_KEY. To use a Meta model on your own machine (e.g. Muse Glimmer), point LLM_BASE_URL and LLM_MODEL
at a local OpenAI-compatible server. Only Meta models are called at runtime.
"""
import os
import time
from openai import OpenAI

BASE_URL = os.getenv("LLM_BASE_URL", "https://inference.baseten.co/v1")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL_NAME = os.getenv("LLM_MODEL", "meta-models/muse-spark-open")
MAX_TOKENS = os.getenv("LLM_MAX_TOKENS")                # optional override; reasoning models spend tokens on thinking
REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT")    # optional, e.g. low / medium / high
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "300"))        # seconds
client = OpenAI(base_url=BASE_URL, api_key=API_KEY or "not-set", timeout=TIMEOUT, max_retries=1)


def is_configured():
    """True when an API key is set, or the endpoint is a local server (which needs none)."""
    return bool(API_KEY) or any(h in BASE_URL for h in ("localhost", "127.0.0.1"))


def clean_code(raw_output: str) -> str:
    lines = [l for l in raw_output.splitlines() if not l.strip().startswith("```")]
    return "\n".join(lines).strip()



CALLS = []   # one record per model call: purpose, model, seconds (None while running)
HOOK = None  # optional callback (the UI sets it to redraw the call list live)


def _create(kwargs):
    """Call the endpoint; if it rejects an optional parameter, drop/rename it and retry (reasoning models differ)."""
    kwargs = dict(kwargs)
    for _ in range(4):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            msg = str(e).lower()
            if "reasoning" in msg and kwargs.get("extra_body", {}).get("reasoning_effort"):
                kwargs["extra_body"] = {k: v for k, v in kwargs["extra_body"].items() if k != "reasoning_effort"}
            elif "temperature" in msg and "temperature" in kwargs:
                kwargs.pop("temperature")
            elif "max_tokens" in msg and "max_tokens" in kwargs:
                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            else:
                raise
    return client.chat.completions.create(**kwargs)


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
        return _create(kwargs)
    finally:
        rec["seconds"] = round(time.time() - t0, 1)
        if HOOK:
            HOOK()


def family(model=None):
    """'Muse' or 'Model' - used for labels in the UI."""
    return "Muse" if "muse" in (model or MODEL_NAME).lower() else "Model"
