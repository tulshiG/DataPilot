"""
LLM Engine — Ollama Client
============================
Manages the connection to a locally running Ollama server.

Ollama serves open-source LLMs (Mistral, Llama, Phi, etc.) via a local
HTTP API.  This client handles:
    • Health checking (is Ollama running?)
    • Model availability checking (is the model pulled?)
    • Chat completion with structured output
    • Timeout and error handling
    • Graceful degradation when Ollama is unavailable

Setup:
    1. Install Ollama: https://ollama.ai
    2. Pull a model: ``ollama pull mistral:7b-instruct``
    3. Start the server: ``ollama serve`` (runs on localhost:11434)
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Configuration — override via environment variables.
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))

# Module-level state
_client = None
_available: bool | None = None  # None = not checked yet


def _get_client():
    """Lazy-initialize the Ollama Python client."""
    global _client
    if _client is None:
        try:
            import ollama
            _client = ollama.Client(host=OLLAMA_HOST)
            logger.info(f"Ollama client initialized (host={OLLAMA_HOST})")
        except ImportError:
            logger.warning("'ollama' package not installed — LLM features disabled")
            _client = None
        except Exception as e:
            logger.warning(f"Failed to initialize Ollama client: {e}")
            _client = None
    return _client


def is_available() -> bool:
    """
    Check if Ollama is running and the configured model is available.
    Caches the result for the lifetime of the process (call ``reset()``
    to re-check).
    """
    global _available
    if _available is not None:
        return _available

    client = _get_client()
    if client is None:
        _available = False
        return False

    try:
        # Check if the server is running
        models = client.list()
        available_models = [m.model for m in models.get("models", models)] if isinstance(models, dict) else [m.model for m in models.models] if hasattr(models, 'models') else []

        # Check if our target model is pulled
        model_found = any(OLLAMA_MODEL in m for m in available_models)

        if model_found:
            logger.info(f"Ollama is available with model '{OLLAMA_MODEL}'")
            _available = True
        else:
            logger.warning(
                f"Ollama is running but model '{OLLAMA_MODEL}' not found. "
                f"Available models: {available_models}. "
                f"Run: ollama pull {OLLAMA_MODEL}"
            )
            _available = False
    except Exception as e:
        logger.warning(f"Ollama health check failed: {e}")
        _available = False

    return _available


def reset():
    """Reset the availability cache (e.g., after pulling a new model)."""
    global _available, _client
    _available = None
    _client = None


def chat(messages: list[dict], *, temperature: float = 0.1,
         format_json: bool = True) -> dict | None:
    """
    Send a chat completion request to Ollama.

    Parameters
    ----------
    messages : list[dict]
        OpenAI-style messages: [{"role": "system", "content": "..."}, ...]
    temperature : float
        Lower = more deterministic. 0.1 is good for structured extraction.
    format_json : bool
        If True, request JSON output format from the model.

    Returns
    -------
    dict or None
        Parsed JSON response from the LLM, or None if the call fails.
    """
    if not is_available():
        return None

    client = _get_client()
    if client is None:
        return None

    try:
        kwargs = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "options": {"temperature": temperature},
        }
        if format_json:
            kwargs["format"] = "json"

        response = client.chat(**kwargs)

        # Extract the content from the response
        content = None
        if isinstance(response, dict):
            content = response.get("message", {}).get("content", "")
        elif hasattr(response, "message"):
            content = response.message.content if hasattr(response.message, "content") else str(response.message)
        else:
            content = str(response)

        if not content:
            logger.warning("Ollama returned empty response")
            return None

        # Parse JSON from response
        if format_json:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
                if json_match:
                    return json.loads(json_match.group(1).strip())
                logger.warning(f"Could not parse JSON from LLM response: {content[:200]}...")
                return None
        else:
            return {"content": content}

    except Exception as e:
        logger.error(f"Ollama chat failed: {e}")
        return None


def generate_text(prompt: str, *, temperature: float = 0.3) -> str | None:
    """
    Simple text generation (non-chat, non-JSON).
    Useful for narrative summaries, descriptions, etc.
    """
    result = chat(
        [{"role": "user", "content": prompt}],
        temperature=temperature,
        format_json=False,
    )
    if result and "content" in result:
        return result["content"]
    return None
