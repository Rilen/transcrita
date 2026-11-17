"""Contrato comum para motores ASR da PoC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Segment:
    """Segmento com timestamps quando o motor os fornece."""

    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    """Resultado normalizado de uma transcrição.

    Campos sem suporte no motor permanecem None/lista vazia e são
    explicitados em ``capabilities``.
    """

    engine: str
    model_id: str
    language_configured: str
    text: str
    audio_duration: float
    processing_time: float
    rtf: float
    status: str = "ok"                       # ok | error | timeout
    model_revision: str | None = None
    language_detected: str | None = None
    segments: list[Segment] = field(default_factory=list)
    peak_rss_mb: float = 0.0
    threads: int = 0
    params: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    capabilities: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["segments"] = [s.__dict__ for s in self.segments]
        return data


class ASRAdapter(ABC):
    """Contrato mínimo: carregar, transcrever, descarregar, metadados."""

    name: str = "base"

    @abstractmethod
    def load(self, config: dict[str, Any]) -> None:
        """Carrega o modelo conforme configuração."""

    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "pt") -> TranscriptionResult:
        """Transcreve um arquivo WAV/áudio e retorna resultado normalizado."""

    @abstractmethod
    def unload(self) -> None:
        """Libera o modelo e recursos associados."""

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Identificação do motor/modelo e capacidades."""
