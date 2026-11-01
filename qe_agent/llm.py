"""Model configuration: any OpenAI-compatible endpoint (defaults to a local Ollama server)."""
import os
from openai import OpenAI

BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("LLM_API_KEY", "ollama")
MODEL_NAME = os.getenv("LLM_MODEL", "llama3.2:3b")
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))  # seconds; the library default (10 min x 3 attempts) can freeze a run
client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=TIMEOUT, max_retries=1)

def clean_code(raw_output: str) -> str:
    lines = [l for l in raw_output.splitlines() if not l.strip().startswith("```")]
    return "\n".join(lines).strip()