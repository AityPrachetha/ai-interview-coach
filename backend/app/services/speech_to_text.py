"""
Phase 3 — speech-to-text via faster-whisper.

faster-whisper (CTranslate2-based) is used instead of openai-whisper because
it's noticeably faster on CPU and doesn't pull in a full PyTorch install —
a meaningful difference if this ever runs on a small server instance.

The model is loaded once as a module-level singleton so repeated requests
don't pay the model-load cost per call. Model weights download from
Hugging Face on first use and are cached locally afterward — the very
first transcription call will be slow (and needs internet access); every
call after that is fast and fully offline.
"""
import os
from faster_whisper import WhisperModel

# "base" is a solid default for short interview answers on CPU: much faster
# than "small"/"medium" with only a modest accuracy trade-off. Bump via env
# var if you have GPU/CPU headroom and want higher accuracy.
_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # int8 = fast on CPU
_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(_MODEL_SIZE, device=_DEVICE, compute_type=_COMPUTE_TYPE)
    return _model


def transcribe_audio(file_path: str) -> dict:
    """
    Transcribes an audio file on disk and returns:
      {
        "text": full transcript (str),
        "duration": total audio duration in seconds (float),
        "segments": [{"start": float, "end": float, "text": str}, ...]
      }

    vad_filter=True trims silence/non-speech at the edges and between
    segments, which matters for the pace/pause calculations in
    voice_analysis.py — without it, long silent stretches (e.g. dead air
    before the candidate starts talking) would skew both.
    """
    model = _get_model()
    segments_iter, info = model.transcribe(file_path, beam_size=5, vad_filter=False)

    segments = []
    text_parts = []
    for seg in segments_iter:
        seg_text = seg.text.strip()
        segments.append({"start": seg.start, "end": seg.end, "text": seg_text})
        if seg_text:
            text_parts.append(seg_text)

    duration = 0.0
    if info is not None and getattr(info, "duration", None):
        duration = info.duration
    elif segments:
        duration = segments[-1]["end"]

    return {
        "text": " ".join(text_parts).strip(),
        "duration": duration,
        "segments": segments,
    }
