"""
Thin wrapper around the Gemini API (Google AI Studio / Gemini Developer API)
so the rest of the app never touches the SDK directly. Centralizing this
makes it trivial to swap models, add retries, or switch providers again later.

Uses the current `google-genai` SDK (NOT the deprecated `google-generativeai`
package). Free tier: no credit card required, get a key at
https://aistudio.google.com/apikey
"""
import json

from google import genai
from google.genai import types

from app.config import settings

_client = genai.Client(api_key=settings.gemini_api_key)


def call_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
    """
    Calls Gemini and forces a JSON response via response_mime_type.
    Raises ValueError if the model doesn't return valid JSON
    (should be rare with response_mime_type=application/json, but we guard anyway).
    """
    response = _client.models.generate_content(
        model=model or settings.gemini_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    content = response.text
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {content[:500]}") from e
