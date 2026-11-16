"""Lógica de transcrição de áudio e vídeo com faster-whisper."""

from __future__ import annotations

import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from faster_whisper import WhisperModel


@dataclass(frozen=True)
class Segment:
    """Um segmento transcrito com intervalo de tempo e texto."""
    start: float
    end: float
    text: str


class Transcriber:
    """Encapsula a carga do modelo Whisper e a transcrição de arquivos."""

    AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac"}
    VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v"}

    def __init__(
        self,
        model_size: str = "base",
        language: str = "pt",
        device: str = "auto",
        compute_type: str = "auto",
        cpu_threads: int | None = None,
    ) -> None:
        self.model_size = model_size
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self._model: WhisperModel | None = None

    @property
    def model(self) -> WhisperModel:
        if self._model is None:
            kwargs: dict = {
                "device": self.device,
                "compute_type": self.compute_type,
            }
            if self.cpu_threads is not None:
                kwargs["cpu_threads"] = self.cpu_threads
            self._model = WhisperModel(self.model_size, **kwargs)
        return self._model

    def extract_audio(self, input_path: str) -> str:
        """Extrai áudio de um arquivo de áudio/vídeo usando ffmpeg.

        Retorna o caminho de um arquivo WAV temporário mono a 16 kHz,
        adequado para o Whisper.
        """
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {input_path}")

        fd, output_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        command = [
            "ffmpeg",
            "-y",
            "-i",
            input_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            output_path,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            os.unlink(output_path)
            raise RuntimeError(
                f"ffmpeg falhou ao extrair áudio de {input_path}: {result.stderr}"
            )
        return output_path

    @staticmethod
    def load_wav_audio(wav_path: str) -> np.ndarray:
        """Lê um arquivo WAV mono 16-bit e retorna array float32 normalizado."""
        with wave.open(wav_path, "rb") as wav:
            n_channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            frame_rate = wav.getframerate()
            n_frames = wav.getnframes()
            raw = wav.readframes(n_frames)

        if sample_width == 2:
            data = np.frombuffer(raw, dtype="<i2").astype(np.float32)
        elif sample_width == 4:
            data = np.frombuffer(raw, dtype="<i4").astype(np.float32)
        elif sample_width == 1:
            data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) * 256
        else:
            raise ValueError(f"Sample width não suportada: {sample_width}")

        if n_channels > 1:
            data = data.reshape(-1, n_channels).mean(axis=1)

        data /= np.iinfo(np.int32).max if sample_width == 4 else 32768.0
        return data

    def _is_video(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in self.VIDEO_EXTENSIONS

    def _needs_conversion(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() not in {".wav"}

    def transcribe_file(
        self,
        input_path: str,
        beam_size: int = 5,
        vad_filter: bool = True,
        language: str | None = None,
        on_progress: Callable[[dict], None] | None = None,
    ) -> list[Segment]:
        """Transcreve um arquivo de áudio ou vídeo.

        Arquivos de vídeo e formatos de áudio não-WAV são convertidos para
        WAV via ffmpeg. O array de áudio é lido com o módulo ``wave`` da
        biblioteca padrão e passado diretamente ao modelo, evitando a
        dependência do ``av`` (PyAV).

        Se ``language`` for fornecido, sobrescreve o idioma da instância
        apenas para esta chamada (útil para reutilizar o Transcriber em cache).

        Se ``on_progress`` for fornecido, é chamado a cada segmento produzido
        pelo faster-whisper com um dicionário contendo ``start``, ``end``,
        ``text``, ``progress`` (0-100) e ``duration``.
        """
        audio_path = input_path
        temp_audio: str | None = None
        resolve_language = language if language is not None else self.language

        try:
            if self._needs_conversion(input_path):
                temp_audio = self.extract_audio(input_path)
                audio_path = temp_audio

            audio_array = self.load_wav_audio(audio_path)

            segments_generator, info = self.model.transcribe(
                audio_array,
                language=resolve_language,
                beam_size=beam_size,
                vad_filter=vad_filter,
            )

            duration = float(getattr(info, "duration", 0) or 0)
            results: list[Segment] = []

            for seg in segments_generator:
                segment = Segment(
                    start=float(seg.start),
                    end=float(seg.end),
                    text=seg.text,
                )
                results.append(segment)

                if on_progress is not None:
                    progress = 0.0
                    if duration > 0:
                        progress = min(
                            100.0, round((segment.end / duration) * 100, 1)
                        )
                    on_progress(
                        {
                            "start": segment.start,
                            "end": segment.end,
                            "text": segment.text,
                            "progress": progress,
                            "duration": duration,
                        }
                    )

            return results
        finally:
            if temp_audio is not None and os.path.exists(temp_audio):
                os.unlink(temp_audio)

    def transcribe_to_text(self, input_path: str, **kwargs) -> str:
        """Retorna a transcrição como texto contínuo."""
        segments = self.transcribe_file(input_path, **kwargs)
        return " ".join(seg.text.strip() for seg in segments if seg.text.strip())

    def transcribe_to_segments(
        self,
        input_path: str,
        **kwargs,
    ) -> list[Segment]:
        """Retorna a lista de segmentos transcritos."""
        return self.transcribe_file(input_path, **kwargs)
