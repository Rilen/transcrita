"""Motor Parakeet PT-BR INT8 (ONNX) com segmentação VAD experimental.

Configuração VAD herdada da missão 006 (baseline experimental):
threshold 0.30, padding 250 ms, silêncio mínimo 550 ms, fala mínima 150 ms
e fusão de pausas <= 350 ms. Não usar MMS_FA (licença NC) neste caminho.
"""

from __future__ import annotations

import gc
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

import numpy as np
import soundfile as sf

from transcrita.core import FFMPEG_TIMEOUT, Segment

VAD_CONFIG = {
    "threshold": 0.30,
    "min_silence_ms": 550,
    "min_speech_ms": 150,
    "pad_ms": 250,
    "max_speech_s": 25.0,
    "merge_gap_s": 0.35,
}


class ParakeetEngine:
    """Encapsula o ONNX INT8 do Parakeet com timestamps por segmento (VAD)."""

    engine_id = "parakeet"
    model_id = "pt-br-int8"
    name = "Parakeet PT-BR"

    def __init__(self, weights_path: str, language: str = "pt") -> None:
        self.weights_path = str(weights_path)
        self.language = language
        self._model = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ load
    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            import onnx_asr

            try:
                self._model = onnx_asr.load_model(
                    "nemo-conformer-tdt", path=self.weights_path, quantization="int8"
                )
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"falha ao carregar Parakeet: {exc}") from exc

    def unload(self) -> None:
        with self._lock:
            self._model = None
        gc.collect()

    # --------------------------------------------------------------- helpers
    def _to_wav16k(self, input_path: str, timeout: int) -> tuple[str, bool]:
        if Path(input_path).suffix.lower() == ".wav":
            return input_path, False
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        result = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", input_path, "-vn",
             "-ac", "1", "-ar", "16000", tmp],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            Path(tmp).unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg falhou ao preparar áudio: {result.stderr[:300]}")
        return tmp, True

    @staticmethod
    def _load_audio(path: str) -> np.ndarray:
        audio, sr = sf.read(path, dtype="float32", always_2d=False)
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        if sr != 16000:
            target = int(round(len(audio) * 16000 / sr))
            audio = np.interp(
                np.linspace(0, len(audio), target, endpoint=False),
                np.arange(len(audio)), audio,
            ).astype(np.float32)
        return np.asarray(audio, dtype=np.float32)

    def _vad_segments(self, audio: np.ndarray) -> list[dict]:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        opts = VadOptions(
            threshold=VAD_CONFIG["threshold"],
            min_silence_duration_ms=VAD_CONFIG["min_silence_ms"],
            min_speech_duration_ms=VAD_CONFIG["min_speech_ms"],
            speech_pad_ms=VAD_CONFIG["pad_ms"],
            max_speech_duration_s=VAD_CONFIG["max_speech_s"],
        )
        stamps = get_speech_timestamps(audio, opts, sampling_rate=16000)
        segs = [
            {"start": s["start"] / 16000, "end": s["end"] / 16000} for s in stamps
        ]
        merged: list[dict] = []
        for seg in segs:
            if merged and seg["start"] - merged[-1]["end"] <= VAD_CONFIG["merge_gap_s"]:
                merged[-1]["end"] = max(merged[-1]["end"], seg["end"])
            else:
                merged.append(dict(seg))
        return merged

    # ------------------------------------------------------------- interface
    def transcribe_file(
        self,
        input_path: str,
        beam_size: int = 5,
        vad_filter: bool = True,
        language: str | None = None,
        on_progress: Callable[[dict], None] | None = None,
        cancel_event: "threading.Event | None" = None,
        ffmpeg_timeout: int | None = None,
    ) -> list[Segment]:
        self._ensure_loaded()
        timeout = int(ffmpeg_timeout or FFMPEG_TIMEOUT)
        prepared, temporary = self._to_wav16k(input_path, timeout)
        try:
            audio = self._load_audio(prepared)
        finally:
            if temporary:
                Path(prepared).unlink(missing_ok=True)

        segments = self._vad_segments(audio)
        out: list[Segment] = []
        lang = language or self.language
        for idx, seg in enumerate(segments):
            if cancel_event is not None and cancel_event.is_set():
                break
            start_i = max(0, int(seg["start"] * 16000))
            end_i = min(len(audio), int(seg["end"] * 16000))
            if end_i - start_i < 1600:  # <100 ms: ruído residual
                continue
            text = (self._model.recognize(
                audio[start_i:end_i], sample_rate=16000, language=lang, channel=None
            ) or "").strip()
            if not text:
                continue
            out.append(Segment(start=seg["start"], end=seg["end"], text=text))
            if on_progress is not None:
                duration = len(audio) / 16000 if len(audio) else 0.0
                progress = int(round((idx + 1) * 100 / max(len(segments), 1)))
                on_progress({
                    "index": len(out) - 1,
                    "progress": progress,
                    "duration": duration,
                    "start": round(seg["start"], 3),
                    "end": round(seg["end"], 3),
                    "text": text,
                })
        return out
