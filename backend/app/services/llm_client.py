"""
LLM client with automatic provider fallback: Gemini -> Groq -> OpenRouter.

Every other file in the app calls ONLY `call_json(system_prompt, user_prompt,
model=None)` and has no idea which provider actually answered - that's the
point. If Gemini's quota is exhausted (or it times out, or is down), this
transparently retries the same prompt against Groq, then OpenRouter, before
giving up. No caller anywhere else needs to change.

Setup:
- Gemini: https://aistudio.google.com/apikey (GEMINI_API_KEY)
- Groq:   https://console.groq.com/keys      (GROQ_API_KEY)
- OpenRouter: https://openrouter.ai/keys     (OPENROUTER_API_KEY)
Leave a key blank in .env to skip that provider entirely (it won't be
attempted, so a missing key never counts as a "failure" in the chain).

Caveat worth knowing: this catches broad exceptions per provider, not just
quota/rate-limit errors specifically. That's deliberate - a timeout, a
transient 500, and a quota error should all trigger the same fallback
behavior. The tradeoff is that a *persistent* bug in how we call Gemini
(e.g. a bad prompt) will also silently fall through to Groq every time
instead of surfacing loudly. Check the logs (each failed attempt is logged
with the provider name and error) if answers start looking off rather than
just erroring.
"""
import json
import logging
from typing import Callable

from google import genai
from google.genai import types
from openai import OpenAI

from app.config import settings

logger = logging.getLogger("llm_client")

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_gemini_client = genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else None
_openai_compatible_clients: dict[str, OpenAI] = {}


def _get_openai_compatible_client(base_url: str, api_key: str) -> OpenAI:
    if base_url not in _openai_compatible_clients:
        _openai_compatible_clients[base_url] = OpenAI(api_key=api_key, base_url=base_url)
    return _openai_compatible_clients[base_url]


def _parse_json_or_raise(provider: str, content: str | None) -> dict:
    if not content:
        raise ValueError(f"{provider} returned an empty response")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"{provider} did not return valid JSON: {content[:500]}") from e


def _call_gemini(system_prompt: str, user_prompt: str, model: str | None) -> dict:
    if _gemini_client is None:
        raise RuntimeError("GEMINI_API_KEY not configured")
    response = _gemini_client.models.generate_content(
        model=model or settings.gemini_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return _parse_json_or_raise("gemini", response.text)


def _call_openai_compatible(provider: str, base_url: str, api_key: str, model: str,
                             system_prompt: str, user_prompt: str) -> dict:
    client = _get_openai_compatible_client(base_url, api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return _parse_json_or_raise(provider, response.choices[0].message.content)


def call_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
    """
    Tries Gemini, then Groq, then OpenRouter, in that order, returning the
    first successful JSON response. Raises the last error only if every
    configured provider failed (or none are configured at all).
    """
    attempts: list[tuple[str, Callable[[], dict]]] = [
        ("gemini", lambda: _call_gemini(system_prompt, user_prompt, model)),
    ]
    if settings.groq_api_key:
        attempts.append((
            "groq",
            lambda: _call_openai_compatible(
                "groq", GROQ_BASE_URL, settings.groq_api_key, settings.groq_model,
                system_prompt, user_prompt,
            ),
        ))
    if settings.openrouter_api_key:
        attempts.append((
            "openrouter",
            lambda: _call_openai_compatible(
                "openrouter", OPENROUTER_BASE_URL, settings.openrouter_api_key, settings.openrouter_model,
                system_prompt, user_prompt,
            ),
        ))

    last_error: Exception | None = None
    for provider_name, attempt in attempts:
        try:
            return attempt()
        except Exception as e:  # noqa: BLE001 - deliberately broad, see module docstring
            logger.warning("LLM provider '%s' failed, falling back: %s", provider_name, e)
            last_error = e
            continue

    raise RuntimeError(
        f"All configured LLM providers failed. Last error: {last_error}"
    ) from last_error
