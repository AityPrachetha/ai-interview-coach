"""
Phase 3 — speech-to-text via Groq's hosted Whisper API.

Previously this ran faster-whisper locally, loading a Whisper model
in-process. That's exactly the kind of memory pressure that causes silent
OOM crashes on a resource-constrained deployment host - loading a
transcription model AND mediapipe's vision models in the same low-RAM
container is a lot to ask. Sending the raw audio bytes to Groq's hosted
whisper-large-v3-turbo instead means this process never has to hold a
speech model in memory at all - transcription happens entirely on Groq's
side, over the same network call pattern already used for the LLM
fallback chain (this app already depends on GROQ_API_KEY for that).

Groq's transcription endpoint is OpenAI-Whisper-API-compatible, so this
reuses the `openai` SDK already in requirements.txt, just pointed at
Groq's base_url.
"""
import io

from openai import OpenAI

from app.config import settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"

_groq_client: OpenAI | None = None


def _get_groq_client() -> OpenAI:
    global _groq_client
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured - speech-to-text now runs via Groq's "
            "hosted Whisper API (see app/services/speech_to_text.py), so a Groq "
            "key is required even if you're not using Groq as an LLM fallback."
        )
    if _groq_client is None:
        _groq_client = OpenAI(api_key=settings.groq_api_key, base_url=GROQ_BASE_URL)
    return _groq_client


def _segment_to_dict(segment) -> dict:
    """Groq's response segments may come back as SDK objects or plain dicts
    depending on version - handle either without assuming one shape."""
    if isinstance(segment, dict):
        return {"start": segment.get("start", 0.0), "end": segment.get("end", 0.0), "text": (segment.get("text") or "").strip()}
    return {"start": getattr(segment, "start", 0.0), "end": getattr(segment, "end", 0.0), "text": (getattr(segment, "text", "") or "").strip()}


def transcribe_audio(audio_bytes: bytes, filename: str = "answer.webm") -> dict:
    """
    Transcribes recorded audio (raw bytes, e.g. a browser MediaRecorder
    .webm blob) via Groq's hosted Whisper API. Returns:
      {
        "text": full transcript (str),
        "duration": total audio duration in seconds (float),
        "segments": [{"start": float, "end": float, "text": str}, ...]
      }

    Same return shape as the old local-Whisper version, so voice_analysis.py
    (pace/filler/confidence heuristics, which need segment timings) needs no
    changes at all.
    """
    client = _get_groq_client()
    response = client.audio.transcriptions.create(
        model=GROQ_WHISPER_MODEL,
        file=(filename, io.BytesIO(audio_bytes)),
        response_format="verbose_json",
    )

    text = (getattr(response, "text", "") or "").strip()
    duration = getattr(response, "duration", None) or 0.0
    raw_segments = getattr(response, "segments", None) or []
    segments = [_segment_to_dict(seg) for seg in raw_segments]

    if not duration and segments:
        duration = segments[-1]["end"]

    return {"text": text, "duration": duration, "segments": segments}
