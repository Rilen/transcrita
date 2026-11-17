"""Adaptador para faster-whisper / CTranslate2 (CPU)."""

from __future__ import annotations

import os
import time
from typing import Any

import numpy as np
import soundfile as sf

from .base import ASRAdapter, Segment, TranscriptionResult


class FasterWhisperAdapter(ASRAdapter):
    """Whisper via CTranslate2 (int8, CPU)."""

    name = "faster_whisper"

    def __init__(self) -> None:
        self._model = None
        self._config: dict[str, Any] = {}

    def load(self, config: dict[str, Any]) -> None:
        from faster_whisper import WhisperModel

        self._config = dict(config)
        threads = int(config.get("cpu_threads", 12))
        self._model = WhisperModel(
            config["model_size"],
            device="cpu",
            compute_type=str(config.get("compute_type", "int8")),
            cpu_threads=threads,
            download_root=os.environ.get("HF_HOME_POC") or None,
        )

    def transcribe(self, audio_path: str, language: str = "pt") -> TranscriptionResult:
        if self._model is None:
            raise RuntimeError("modelo não carregado")
        audio, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        if sample_rate != 16000:
            target = int(round(len(audio) * 16000 / sample_rate))
            audio = np.interp(
                np.linspace(0, len(audio), target, endpoint=False),
                np.arange(len(audio)),
                audio,
            ).astype(np.float32)
            sample_rate = 16000

        start = time.perf_counter()
        segments_iter, info = self._model.transcribe(
            audio,
            language=language,
            beam_size=int(self._config.get("beam_size", 5)),
            vad_filter=bool(self._config.get("vad_filter", False)),
            word_timestamps=False,
        )
        segments = [
            Segment(start=float(s.start), end=float(s.end), text=(s.text or "").strip())
            for s in segments_iter
        ]
        elapsed = time.perf_counter() - start
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        if duration <= 0 and sample_rate:
            duration = len(audio) / float(sample_rate)
        text = " ".join(s.text for s in segments if s.text)
        return TranscriptionResult(
            engine="faster-whisper",
            model_id=str(self._config.get("model_size")),
            model_revision=str(self._config.get("revision", "")) or None,
            language_configured=language,
            language_detected=getattr(info, "language", None),
            text=text,
            segments=segments,
            audio_duration=duration,
            processing_time=elapsed,
            rtf=(elapsed / duration) if duration > 0 else 0.0,
            threads=int(self._config.get("cpu_threads", 12)),
            params={
                "beam_size": int(self._config.get("beam_size", 5)),
                "vad_filter": bool(self._config.get("vad_filter", False)),
                "compute_type": str(self._config.get("compute_type", "int8")),
            },
            capabilities={
                "segments": True,
                "word_timestamps": False,
                "vad": True,
                "diarization": False,
            },
        )

    def unload(self) -> None:
        import gc

        self._model = None
        gc.collect()

    def metadata(self) -> dict[str, Any]:
        return {
            "engine": "faster-whisper",
            "runtime": "ctranslate2",
            "model_id": str(self._config.get("model_size")),
            "config": dict(self._config),
        }
