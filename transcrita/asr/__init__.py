"""Contrato interno de motores ASR do Transcrita."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path

WHISPER_MODELS = [
    {"value": "tiny", "label": "tiny"},
    {"value": "base", "label": "base"},
    {"value": "small", "label": "small"},
    {"value": "medium", "label": "medium"},
    {"value": "large-v3", "label": "large-v3"},
    {"value": "large-v3-turbo", "label": "large-v3-turbo"},
]

PARAKEET_MODEL = {"value": "pt-br-int8", "label": "PT-BR INT8"}

DEFAULT_PARAKEET_PATH = "/var/lib/transcrita-poc/models/parakeet-ptbr-tagarela-int8"


def parakeet_enabled() -> bool:
    """Flag administrativa; desligada por padrão."""
    return os.environ.get("TRANSCRITA_ENABLE_PARAKEET", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def parakeet_weights_path() -> str:
    return os.environ.get("TRANSCRITA_PARAKEET_MODEL", DEFAULT_PARAKEET_PATH)


def parakeet_availability() -> tuple[bool, str]:
    """Disponibilidade real: dependência importável e pesos presentes."""
    if importlib.util.find_spec("onnx_asr") is None:
        return False, "dependência onnx-asr não instalada (extra [parakeet])"
    if importlib.util.find_spec("soundfile") is None:
        return False, "dependência soundfile não instalada (extra [parakeet])"
    path = Path(parakeet_weights_path())
    if not path.is_dir():
        return False, f"pesos não encontrados em {path}"
    if not (path / "encoder-model.int8.onnx").exists():
        return False, f"checkpoint INT8 incompleto em {path}"
    return True, ""


@dataclass
class EngineSpec:
    id: str
    name: str
    status: str
    models: list[dict] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    supports_timestamps: bool = False
    timestamp_scope: str = "none"
    limitations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        payload = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "experimental": self.status == "experimental",
            "models": self.models,
            "languages": self.languages,
            "supports_timestamps": self.supports_timestamps,
            "timestamp_scope": self.timestamp_scope,
            "limitations": self.limitations,
            "available": True,
            "unavailable_reason": "",
        }
        if self.id == "parakeet":
            enabled = parakeet_enabled()
            payload["enabled"] = enabled
            if not enabled:
                payload["available"] = False
                payload["unavailable_reason"] = (
                    "Parakeet desabilitado (TRANSCRITA_ENABLE_PARAKEET=false)"
                )
            else:
                ok, reason = parakeet_availability()
                payload["available"] = ok
                payload["unavailable_reason"] = reason
        else:
            payload["enabled"] = True
        return payload


ENGINES: dict[str, EngineSpec] = {
    "whisper": EngineSpec(
        id="whisper",
        name="Whisper",
        status="stable",
        models=WHISPER_MODELS,
        languages=["pt", "en", "es", "auto"],
        supports_timestamps=True,
        timestamp_scope="segment",
        limitations=["timestamps por segmento (não por palavra na interface)"],
    ),
    "parakeet": EngineSpec(
        id="parakeet",
        name="Parakeet PT-BR",
        status="experimental",
        models=[PARAKEET_MODEL],
        languages=["pt"],
        supports_timestamps=True,
        timestamp_scope="segment (VAD)",
        limitations=[
            "experimental; timestamps por segmento via VAD (sem nível de palavra)",
            "início tende a anteceder o onset em ~250 ms (padding de proteção)",
            "somente português",
        ],
    ),
}


def list_engines() -> list[dict]:
    return [ENGINES["whisper"].as_dict(), ENGINES["parakeet"].as_dict()]


def engine_metadata(engine_id: str, model: str) -> dict:
    spec = ENGINES[engine_id]
    return {
        "engine": engine_id,
        "engine_name": spec.name,
        "engine_status": spec.status,
        "experimental": spec.status == "experimental",
        "model": model,
        "model_label": next(
            (m["label"] for m in spec.models if m["value"] == model), model
        ),
        "supports_timestamps": spec.supports_timestamps,
        "timestamp_scope": spec.timestamp_scope,
        "limitations": spec.limitations,
    }
