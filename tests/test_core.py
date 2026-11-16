"""Testes unitários para o módulo core."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from transcrita.core import Transcriber


def _write_wav(path: str, seconds: float = 1.0, sample_rate: int = 16000) -> None:
    n_frames = int(sample_rate * seconds)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        for _ in range(n_frames):
            w.writeframes(struct.pack("<h", 0))


import wave  # noqa: E402


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
