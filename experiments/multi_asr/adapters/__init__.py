"""Adaptadores ASR sob contrato comum."""

from .base import ASRAdapter, Segment, TranscriptionResult
from .faster_whisper_adapter import FasterWhisperAdapter
from .parakeet_onnx_adapter import ParakeetOnnxAdapter

ADAPTERS = {
    "faster_whisper": FasterWhisperAdapter,
    "parakeet_onnx": ParakeetOnnxAdapter,
}

__all__ = ["ASRAdapter", "Segment", "TranscriptionResult", "ADAPTERS"]
