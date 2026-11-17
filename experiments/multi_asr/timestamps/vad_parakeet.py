"""Estratégia A: segmentação por VAD (Silero) + Parakeet por segmento."""

from __future__ import annotations

from typing import Any

import numpy as np

from .audio import load_mono16k


def detect_segments(audio: np.ndarray, threshold: float = 0.5,
                    min_silence_ms: int = 400, min_speech_ms: int = 250,
                    max_speech_s: float = 25.0, pad_ms: int = 100) -> list[dict]:
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    opts = VadOptions(
        threshold=threshold,
        min_speech_duration_ms=min_speech_ms,
        min_silence_duration_ms=min_silence_ms,
        max_speech_duration_s=max_speech_s,
        speech_pad_ms=pad_ms,
    )
    stamps = get_speech_timestamps(audio, opts, sampling_rate=16000)
    return [
        {"start": float(s["start"] / 16000), "end": float(s["end"] / 16000)} for s in stamps
    ]


def transcribe_segmented(model: Any, audio: np.ndarray, segments: list[dict],
                         language: str = "pt") -> list[dict]:
    out: list[dict] = []
    for seg in segments:
        s = max(0, int(seg["start"] * 16000))
        e = min(len(audio), int(seg["end"] * 16000))
        if e - s < 1600:  # <100 ms: ignora ruído residual
            continue
        text = model.recognize(audio[s:e], sample_rate=16000, language=language,
                               channel=None)
        text = (text or "").strip()
        if not text:
            continue
        out.append({"start": seg["start"], "end": seg["end"], "text": text})
    return out
