"""How to talk to a language model. Not what to say to it — see prompts.py.

Two backends behind one function, chosen by config.LLM_BACKEND:

    ollama  — local, free, needs ~6GB RAM for llama3.1:8b. Your laptop.
    gemini  — hosted, has a free tier, needs no RAM. A cheap server.

The split exists because of a real constraint: Ollama plus sentence-transformers
(which drags in torch) will not fit on a small VPS. Deploying means either
paying for a big machine or moving generation off-box. Keeping every model call
behind `generate()` makes that a config change instead of a rewrite.
"""

import requests

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_BACKEND,
    LLM_TIMEOUT_SECONDS,
    OLLAMA_MODEL,
    OLLAMA_URL,
)


class LLMError(RuntimeError):
    """Generation failed. Not recoverable here — the caller decides."""


def generate(prompt):
    """Send a prompt, return the model's text. Raises LLMError on failure.

    No fallback string, ever. Returning "Summary unavailable" would put a
    sentence into the summaries table that looks exactly like a real summary to
    everything downstream — the cache would serve it forever and nothing would
    ever notice. Failing loudly costs one visible error; a fake success costs
    silent corruption you find weeks later.
    """
    if LLM_BACKEND == "ollama":
        return _ollama(prompt)
    if LLM_BACKEND == "gemini":
        return _gemini(prompt)
    raise LLMError(f"Unknown LLM_BACKEND: {LLM_BACKEND!r}. Use 'ollama' or 'gemini'.")


def _ollama(prompt):
    """Local Ollama. stream=False so one response arrives complete.

    The timeout is not optional. Without one, requests waits forever — a model
    that hangs takes a web worker with it, and enough of those take the site
    down. Every network call in this project has a timeout for the same reason.
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise LLMError(f"Ollama call failed: {exc}") from exc

    text = response.json().get("response", "").strip()
    if not text:
        raise LLMError("Ollama returned an empty response")
    return text


def _gemini(prompt):
    """Hosted Gemini over plain HTTP — no SDK, one less dependency to install
    on a server and one less thing to break on a version bump."""
    if not GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not set")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": GEMINI_API_KEY},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise LLMError(f"Gemini call failed: {exc}") from exc

    payload = response.json()
    try:
        return payload["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as exc:
        # A 200 with an unexpected body usually means the prompt was blocked by
        # a safety filter. Say so instead of raising a bare KeyError.
        raise LLMError(f"Unexpected Gemini response shape: {payload}") from exc
