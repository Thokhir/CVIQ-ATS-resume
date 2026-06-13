"""
llm.py — Optional offline LLM bridge for CVIQ Resume Maker Pro.

This is how most modern ATS resume tools work under the hood: a real language
model rewrites the resume/cover letter, with a deterministic rule-based engine
as a guaranteed fallback. Here the model runs *locally* via Ollama
(https://ollama.com) — so there are NO API keys, NO cloud calls, and user data
never leaves the machine. If Ollama is not installed/running, every function
degrades gracefully and the caller uses the built-in rule-based engine.

Zero hard dependencies: talks to Ollama's local HTTP API with the standard
library only (urllib). `pip install ollama` is NOT required.

Endpoints used (Ollama default http://localhost:11434):
  GET  /api/tags        → list installed models
  POST /api/generate    → text generation
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error

# Allow override via env var for remote/self-hosted Ollama on the LAN.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

# Preference order — first installed model wins. These are all small enough to
# run offline on a typical laptop and are the ones the UI advertises.
PREFERRED_MODELS = ["mistral", "llama3.1", "llama3.2:3b", "llama3.2", "phi3:mini", "phi3", "qwen2.5"]

_AVAIL_CACHE: dict = {"checked": 0.0, "available": False, "models": []}
_CACHE_TTL = 30.0  # seconds


def _get(url: str, timeout: float = 1.5):
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(url: str, payload: dict, timeout: float = 120.0):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _refresh_availability(force: bool = False) -> None:
    now = time.time()
    if not force and (now - _AVAIL_CACHE["checked"]) < _CACHE_TTL:
        return
    _AVAIL_CACHE["checked"] = now
    try:
        data = _get(f"{OLLAMA_HOST}/api/tags", timeout=1.5)
        models = [m.get("name", "") for m in data.get("models", [])]
        _AVAIL_CACHE["available"] = True
        _AVAIL_CACHE["models"] = models
    except Exception:
        _AVAIL_CACHE["available"] = False
        _AVAIL_CACHE["models"] = []


def ollama_available(force: bool = False) -> bool:
    """True if a local Ollama server is reachable and has at least one model."""
    _refresh_availability(force)
    return bool(_AVAIL_CACHE["available"] and _AVAIL_CACHE["models"])


def installed_models(force: bool = False) -> list[str]:
    _refresh_availability(force)
    return list(_AVAIL_CACHE["models"])


def pick_model(preferred: str | None = None) -> str | None:
    """Return the best available model name, honouring a preference if installed."""
    models = installed_models()
    if not models:
        return None

    def _match(want: str) -> str | None:
        want = (want or "").strip().lower()
        if not want:
            return None
        # exact, then prefix (so "mistral" matches "mistral:latest")
        for m in models:
            if m.lower() == want:
                return m
        for m in models:
            if m.lower().split(":")[0] == want.split(":")[0]:
                return m
        return None

    if preferred:
        hit = _match(preferred)
        if hit:
            return hit
    for cand in PREFERRED_MODELS:
        hit = _match(cand)
        if hit:
            return hit
    return models[0]


def generate(prompt: str, system: str | None = None, model: str | None = None,
             temperature: float = 0.2, timeout: float = 120.0) -> str | None:
    """
    Run a single-shot generation against the local model.
    Returns the generated text, or None on any failure (caller falls back).
    """
    if not ollama_available():
        return None
    use_model = pick_model(model)
    if not use_model:
        return None
    payload = {
        "model": use_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": float(temperature)},
    }
    if system:
        payload["system"] = system
    try:
        data = _post(f"{OLLAMA_HOST}/api/generate", payload, timeout=timeout)
        out = (data.get("response") or "").strip()
        return out or None
    except Exception:
        return None


def status_line() -> str:
    """Human-readable status for the UI."""
    if ollama_available():
        m = pick_model()
        return f"🟢 Local AI active — running `{m}` via Ollama (100% offline, no API key)."
    return ("🟡 Offline rule-based engine active. Install [Ollama](https://ollama.com) "
            "and run `ollama pull mistral` to enable on-device AI rewriting.")
