"""Adaptador ONNX Runtime para Parakeet TDT (CPU), via pacote onnx-asr."""

from __future__ import annotations

import time
from typing import Any

from .base import ASRAdapter, TranscriptionResult


class ParakeetOnnxAdapter(ASRAdapter):
    """Parakeet TDT 0.6B v3 (pt-BR TAGARELA, ONNX INT8) em CPU."""

    name = "parakeet_onnx"

    def __init__(self) -> None:
        self._model = None
        self._config: dict[str, Any] = {}

    def load(self, config: dict[str, Any]) -> None:
        import onnx_asr

        self._config = dict(config)
        local_path = config.get("local_path")
        if not local_path:
            from huggingface_hub import snapshot_download

            local_path = snapshot_download(
                str(config["repo_id"]),
                local_dir=str(config.get("local_dir") or ""),
            ) if config.get("local_dir") else snapshot_download(str(config["repo_id"]))
            self._config["local_path"] = local_path
        kwargs: dict[str, Any] = {"path": str(local_path)}
        if config.get("quantization"):
            kwargs["quantization"] = str(config["quantization"])
        self._model = onnx_asr.load_model(
            str(config.get("family", "nemo-conformer-tdt")),
            **kwargs,
        )

    def transcribe(self, audio_path: str, language: str = "pt") -> TranscriptionResult:
        if self._model is None:
            raise RuntimeError("modelo não carregado")
        start = time.perf_counter()
        text = self._model.recognize(audio_path, language=language)
        elapsed = time.perf_counter() - start
        return TranscriptionResult(
            engine="onnx-asr/parakeet-tdt",
            model_id=str(self._config["repo_id"]),
            model_revision=str(self._config.get("revision", "")) or None,
            language_configured=language,
            language_detected=None,
            text=(text or "").strip(),
            segments=[],
            audio_duration=0.0,
            processing_time=elapsed,
            rtf=0.0,
            threads=int(self._config.get("cpu_threads", 12)),
            params={"family": str(self._config.get("family", "nemo-conformer-tdt"))},
            capabilities={
                "segments": False,
                "word_timestamps": False,
                "vad": False,
                "diarization": False,
            },
        )

    def unload(self) -> None:
        import gc

        self._model = None
        gc.collect()

    def metadata(self) -> dict[str, Any]:
        return {
            "engine": "onnx-asr",
            "model_id": str(self._config.get("repo_id")),
            "runtime": "onnxruntime",
            "config": dict(self._config),
        }
