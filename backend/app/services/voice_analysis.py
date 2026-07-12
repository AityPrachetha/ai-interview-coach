"""
Phase 3 — derives speaking-pace, filler-word, and confidence signals from
the Whisper transcript + segment timings alone (no separate audio-DSP
library like librosa needed for this first pass).

This is a deliberate scope choice: true prosodic confidence (pitch
variance, energy/volume, voice tremor) would need actual waveform analysis
and is a reasonable Phase 4 enhancement once the webcam/mic pipeline is
already wired up. What's here — pace, pauses, filler-word ratio — is a
solid, cheap-to-compute first signal that doesn't require any new heavy
dependency.
"""
import re

FILLER_WORDS = [
    "um", "umm", "uh", "uhh", "erm", "hmm",
    "like", "you know", "sort of", "kind of", "basically",
    "actually", "literally", "i mean",
]

_FILLER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in FILLER_WORDS) + r")\b",
    re.IGNORECASE,
)

# Comfortable conversational interview pace. Outside this range in either
# direction (rushed/mumbling vs. dragging) dings the confidence heuristic.
IDEAL_WPM_RANGE = (120, 160)


def analyze_voice(text: str, segments: list[dict], duration: float) -> dict:
    word_count = len(text.split())
    duration_minutes = max(duration / 60.0, 1e-6)
    speaking_pace_wpm = round(word_count / duration_minutes, 1) if duration > 0 else 0.0

    filler_word_count = len(_FILLER_PATTERN.findall(text))
    filler_ratio = filler_word_count / max(word_count, 1)

    # Pause ratio: silence gaps between consecutive Whisper segments, as a
    # fraction of total duration. High pause ratio can signal hesitation
    # (though some pausing is normal and even good — this is a soft signal).
    pause_seconds = 0.0
    for prev, curr in zip(segments, segments[1:]):
        gap = curr["start"] - prev["end"]
        if gap > 0:
            pause_seconds += gap
    pause_ratio = (pause_seconds / duration) if duration > 0 else 0.0

    confidence = 100.0
    lo, hi = IDEAL_WPM_RANGE
    if speaking_pace_wpm < lo:
        confidence -= min((lo - speaking_pace_wpm) * 0.6, 35)
    elif speaking_pace_wpm > hi:
        confidence -= min((speaking_pace_wpm - hi) * 0.5, 35)

    confidence -= min(filler_ratio * 200, 30)  # e.g. 15% filler ratio -> -30
    confidence -= min(pause_ratio * 100, 20)   # e.g. 20% silence -> -20
    confidence = max(0.0, min(100.0, round(confidence, 1)))

    return {
        "speaking_pace_wpm": speaking_pace_wpm,
        "filler_word_count": filler_word_count,
        "voice_confidence_score": confidence,
        # Not persisted as a DB column — useful for debugging/tuning the heuristic.
        "pause_ratio": round(pause_ratio, 3),
    }
