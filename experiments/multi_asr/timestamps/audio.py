"""Carregamento de áudio mono 16 kHz para VAD/ASR."""

from __future__ import annotations

import numpy as np
import soundfile as sf


def load_mono16k(path: str) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if getattr(audio, "ndim", 1) > 1:
        audio = audio.mean(axis=1)
    if sr != 16000:
        target = int(round(len(audio) * 16000 / sr))
        audio = np.interp(
            np.linspace(0, len(audio), target, endpoint=False),
            np.arange(len(audio)),
            audio,
        ).astype(np.float32)
        sr = 16000
    return audio, sr
