"""Implementação do motor Piper TTS para síntese local em português (pt-BR)."""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import time
from pathlib import Path

from transcrita.tts import (
    AUTHORIZED_VOICES,
    DEFAULT_VOICE_ID,
    max_tts_chars,
    piper_binary_path,
    piper_models_dir,
    tts_timeout,
    voice_availability,
)

logger = logging.getLogger("transcrita.tts")

_PATH_RE = re.compile(r"(/[\w.-]+)+")


def _sanitize_log_message(msg: str) -> str:
    """Remove caminhos absolutos e sanitiza mensagens de erro."""
    cleaned = _PATH_RE.sub("[caminho]", msg.replace("\n", " ").strip())
    return cleaned[:300]


class PiperTTSError(Exception):
    """Erro interno durante o processamento do Piper TTS."""
    pass


class PiperTTS:
    """Executor do motor Piper TTS via subprocesso isolado."""

    def __init__(self, models_dir: Path | None = None, bin_path: str | None = None):
        self._models_dir = models_dir or piper_models_dir()
        self._bin_path = bin_path or piper_binary_path()

    def synthesize(
        self,
        text: str,
        voice: str = DEFAULT_VOICE_ID,
        speed: float = 1.0,
        timeout: float | None = None,
    ) -> bytes:
        """Sintetiza texto UTF-8 em áudio WAV PCM via Piper.

        Parâmetros:
            text: Texto em português a ser sintetizado (máx. configurável via TRANSCRITA_TTS_MAX_CHARS).
            voice: Identificador da voz autorizada pt-BR.
            speed: Velocidade de fala (0.5 a 2.0).
            timeout: Tempo limite em segundos para a síntese.

        Retorna:
            Bytes do arquivo WAV gerado.
        """
        # Validação do texto
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Texto não fornecido para síntese")

        clean_text = text.strip()
        max_limit = max_tts_chars()
        if len(clean_text) > max_limit:
            raise ValueError(f"Texto excede o limite máximo permitido de {max_limit} caracteres")

        # Validação da voz contra allowlist estrita
        if voice not in AUTHORIZED_VOICES:
            raise ValueError(f"Voz '{voice}' não autorizada. Apenas vozes pt-BR da allowlist são permitidas.")

        # Validação da velocidade
        try:
            speed_val = float(speed)
        except (TypeError, ValueError):
            raise ValueError("Velocidade inválida. Deve ser um número entre 0.5 e 2.0.")

        if not (0.5 <= speed_val <= 2.0):
            raise ValueError("Velocidade fora dos limites permitidos (0.5 a 2.0).")

        # Conversão de velocidade para length-scale do Piper
        # length_scale inversamente proporcional à velocidade
        length_scale = round(1.0 / speed_val, 3)

        # Checagem de disponibilidade física
        avail, reason = voice_availability(voice)
        if not avail:
            raise RuntimeError(f"Voz {voice} indisponível: {reason}")

        bin_path = piper_binary_path()
        if not bin_path:
            raise RuntimeError("Binário do Piper não localizado no sistema")

        models_dir = piper_models_dir()
        model_file = models_dir / f"{voice}.onnx"
        config_file = models_dir / f"{voice}.onnx.json"

        effective_timeout = timeout if (timeout is not None and timeout > 0) else tts_timeout()

        cmd = [
            bin_path,
            "-m", str(model_file),
            "-c", str(config_file),
            "--length-scale", str(length_scale),
        ]

        start_time = time.perf_counter()

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_wav = Path(tmp_dir) / "synth_output.wav"
            cmd.extend(["-f", str(out_wav)])

            try:
                proc = subprocess.run(
                    cmd,
                    input=clean_text.encode("utf-8"),
                    capture_output=True,
                    timeout=effective_timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                logger.error(
                    "tts_timeout",
                    extra={"voice": voice, "chars": len(clean_text), "timeout": effective_timeout},
                )
                raise TimeoutError(f"Tempo limite de {effective_timeout}s excedido na síntese")
            except Exception as e:
                logger.error("tts_subprocess_failed", extra={"erro": _sanitize_log_message(str(e))})
                raise PiperTTSError(f"Falha ao executar sintetizador: {_sanitize_log_message(str(e))}")

            if proc.returncode != 0:
                err_stderr = proc.stderr.decode("utf-8", errors="replace")
                sanitized_err = _sanitize_log_message(err_stderr)
                logger.error("tts_piper_error", extra={"code": proc.returncode, "err": sanitized_err})
                raise PiperTTSError(f"Falha no processamento Piper (código {proc.returncode}): {sanitized_err}")

            if not out_wav.is_file() or out_wav.stat().st_size <= 44:
                logger.error("tts_empty_output", extra={"voice": voice, "chars": len(clean_text)})
                raise PiperTTSError("Áudio gerado é inválido ou vazio")

            wav_bytes = out_wav.read_bytes()

        elapsed = time.perf_counter() - start_time
        logger.info(
            "tts_sintese_concluida",
            extra={
                "voice": voice,
                "chars": len(clean_text),
                "speed": speed_val,
                "bytes": len(wav_bytes),
                "elapsed_sec": round(elapsed, 3),
            },
        )

        return wav_bytes
