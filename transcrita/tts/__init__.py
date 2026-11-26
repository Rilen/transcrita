"""Contrato e especificações do motor TTS (Piper) para o Transcrita."""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("transcrita.tts")

DEFAULT_MODELS_DIR = "/var/lib/transcrita/models/piper/pt_BR"
DEFAULT_PIPER_BIN = "/opt/transcrita/.venv-piper/bin/piper"
DEFAULT_MAX_CHARS = 10000
DEFAULT_TIMEOUT = 60.0


def tts_enabled() -> bool:
    """Feature flag administrativa para ativação do TTS. Desabilitada por padrão."""
    return os.environ.get("TRANSCRITA_ENABLE_TTS", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }


def max_tts_chars() -> int:
    try:
        val = int(os.environ.get("TRANSCRITA_TTS_MAX_CHARS", str(DEFAULT_MAX_CHARS)))
        return val if val > 0 else DEFAULT_MAX_CHARS
    except ValueError:
        return DEFAULT_MAX_CHARS


def tts_timeout() -> float:
    try:
        val = float(os.environ.get("TRANSCRITA_TTS_TIMEOUT", str(DEFAULT_TIMEOUT)))
        return val if val > 0 else DEFAULT_TIMEOUT
    except ValueError:
        return DEFAULT_TIMEOUT


def piper_models_dir() -> Path:
    env_dir = os.environ.get("TRANSCRITA_PIPER_MODELS_DIR", "").strip()
    return Path(env_dir) if env_dir else Path(DEFAULT_MODELS_DIR)


def piper_binary_path() -> str | None:
    env_bin = os.environ.get("TRANSCRITA_PIPER_BIN", "").strip()
    if env_bin and Path(env_bin).is_file() and os.access(env_bin, os.X_OK):
        return env_bin
    default_p = Path(DEFAULT_PIPER_BIN)
    if default_p.is_file() and os.access(default_p, os.X_OK):
        return str(default_p)
    system_piper = shutil.which("piper")
    if system_piper:
        return system_piper
    return None


@dataclass(frozen=True)
class VoiceSpec:
    id: str
    name: str
    language: str
    quality: str
    sample_rate: int
    is_default: bool
    license_type: str
    dataset_url: str


AUTHORIZED_VOICES: dict[str, VoiceSpec] = {
    "pt_BR-faber-medium": VoiceSpec(
        id="pt_BR-faber-medium",
        name="Faber (Médio, pt-BR)",
        language="pt-BR",
        quality="medium",
        sample_rate=22050,
        is_default=True,
        license_type="CC0",
        dataset_url="https://github.com/OHF-Voice/voice-datasets",
    ),
    "pt_BR-edresson-low": VoiceSpec(
        id="pt_BR-edresson-low",
        name="Edresson (Baixo, pt-BR)",
        language="pt-BR",
        quality="low",
        sample_rate=16000,
        is_default=False,
        license_type="CC BY 4.0",
        dataset_url="https://github.com/Edresson/TTS-Portuguese-Corpus",
    ),
}

DEFAULT_VOICE_ID = "pt_BR-faber-medium"


def get_voice_spec(voice_id: str) -> VoiceSpec | None:
    return AUTHORIZED_VOICES.get(voice_id)


def voice_availability(voice_id: str) -> tuple[bool, str]:
    if voice_id not in AUTHORIZED_VOICES:
        return False, f"Voz '{voice_id}' não autorizada pela governança pt-BR"

    bin_path = piper_binary_path()
    if not bin_path:
        return False, "Binário do motor Piper não encontrado no servidor"

    base_dir = piper_models_dir()
    onnx_file = base_dir / f"{voice_id}.onnx"
    json_file = base_dir / f"{voice_id}.onnx.json"

    if not onnx_file.is_file():
        return False, f"Arquivo de modelo .onnx da voz {voice_id} não encontrado"
    if not json_file.is_file():
        return False, f"Arquivo de configuração .onnx.json da voz {voice_id} não encontrado"

    return True, ""


def list_voices_payload() -> list[dict[str, Any]]:
    voices_list = []
    for v_id, spec in AUTHORIZED_VOICES.items():
        avail, reason = voice_availability(v_id)
        voices_list.append({
            "id": spec.id,
            "name": spec.name,
            "language": spec.language,
            "quality": spec.quality,
            "sample_rate": spec.sample_rate,
            "default": spec.is_default,
            "available": avail,
            "unavailable_reason": reason,
            "license": spec.license_type,
        })
    return voices_list
