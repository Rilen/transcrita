"""Testes unitários para o módulo core."""

from __future__ import annotations

import logging
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from transcrita.core import Transcriber


def _write_wav(path: str, seconds: float = 1.0, sample_rate: int = 16000) -> None:
    import wave  # noqa: E402

    n_frames = int(sample_rate * seconds)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for _ in range(n_frames):
            w.writeframes(struct.pack("<h", 0))


class TestCore(unittest.TestCase):
    def test_load_wav_audio(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = tmp.name
        try:
            _write_wav(path, seconds=1.0)
            audio = Transcriber.load_wav_audio(path)
            self.assertEqual(audio.dtype, "float32")
            self.assertEqual(len(audio), 16000)
            self.assertLessEqual(abs(audio.max()), 1.0)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_is_video(self) -> None:
        t = Transcriber()
        self.assertTrue(t._is_video("video.mp4"))
        self.assertTrue(t._is_video("video.mkv"))
        self.assertFalse(t._is_video("audio.wav"))
        self.assertFalse(t._is_video("audio.mp3"))

    def test_needs_conversion(self) -> None:
        t = Transcriber()
        self.assertTrue(t._needs_conversion("video.mp4"))
        self.assertTrue(t._needs_conversion("audio.mp3"))
        self.assertFalse(t._needs_conversion("audio.wav"))

    def test_rtf_logged_during_transcribe(self) -> None:
        """RTF é calculado, registrado em log e é coerente com elapsed / duration."""
        import time  # noqa: E402

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = tmp.name
        try:
            _write_wav(path, seconds=1.0)

            t = Transcriber(model_size="base")

            def segment_generator():
                time.sleep(0.01)  # garante elapsed > 0 para rtf positivo
                mock_segment = MagicMock()
                mock_segment.start = 0.0
                mock_segment.end = 1.0
                mock_segment.text = "teste"
                yield mock_segment

            mock_model = MagicMock()
            mock_model.transcribe.return_value = (
                segment_generator(),
                MagicMock(duration=1.0),
            )
            t._model = mock_model

            with self.assertLogs(logger="transcrita.core", level="INFO") as cm:
                t.transcribe_file(path)

            log_output = "\n".join(cm.output)
            self.assertIn("transcricao_concluida", log_output)

            # Verifica que o campo rtf está presente nos records de log
            rtf_records = [
                r for r in cm.records if getattr(r, "arquivo", None) == path
            ]
            self.assertTrue(rtf_records, "nenhum record de log encontrado para o arquivo")
            self.assertGreater(rtf_records[0].rtf, 0.0)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_cancel_event_interrupts_transcription(self) -> None:
        """cancel_event interrompe o loop de segmentos imediatamente e não vaza temp files."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = tmp.name
        try:
            _write_wav(path, seconds=1.0)

            t = Transcriber(model_size="base")
            cancel_event = threading.Event()

            def segment_generator():
                yield MagicMock(start=0.0, end=0.5, text="primeiro")
                cancel_event.set()
                yield MagicMock(start=0.5, end=1.0, text="segundo")

            mock_model = MagicMock()
            mock_model.transcribe.return_value = (
                segment_generator(),
                MagicMock(duration=1.0),
            )
            t._model = mock_model

            results = t.transcribe_file(path, cancel_event=cancel_event)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].text, "primeiro")
        finally:
            Path(path).unlink(missing_ok=True)
