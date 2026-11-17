"""Estratégia A: segmentação por VAD (Silero) + Parakeet por segmento."""

from __future__ import annotations

from typing import Any

import numpy as np

from .audio import load_mono16k


def merge_segments(segments: list[dict], max_gap_s: float = 0.35,
                   duration: float | None = None) -> list[dict]:
    """Funde segmentos separados por pausas curtas; nunca sobrepõe ou inverte."""
    merged: list[dict] = []
    for seg in segments:
        start, end = float(seg["start"]), float(seg["end"])
        if duration is not None:
            start, end = max(0.0, min(start, duration)), max(0.0, min(end, duration))
        if end <= start:
            continue
        if merged and start - merged[-1]["end"] <= max_gap_s:
            merged[-1]["end"] = max(merged[-1]["end"], end)
        else:
            merged.append({"start": start, "end": end})
    return merged


def detect_segments(audio: np.ndarray, threshold: float = 0.5,
                    min_silence_ms: int = 400, min_speech_ms: int = 250,
                    max_speech_s: float = 25.0, pad_ms: int = 100,
                    merge_gap_s: float = 0.0) -> list[dict]:
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    opts = VadOptions(
        threshold=threshold,
        min_speech_duration_ms=min_speech_ms,
        min_silence_duration_ms=min_silence_ms,
        max_speech_duration_s=max_speech_s,
        speech_pad_ms=pad_ms,
    )
    stamps = get_speech_timestamps(audio, opts, sampling_rate=16000)
    segs = [
        {"start": float(s["start"] / 16000), "end": float(s["end"] / 16000)} for s in stamps
    ]
    if merge_gap_s > 0:
        segs = merge_segments(segs, merge_gap_s)
    return segs


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
