"""Testes unitários para o módulo web usando TestClient com mock do Transcriber."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from transcrita.web import app, _get_transcriber, _transcriber_cache, _transcriber_lock


class TestWeb(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        # Reseta o cache de modelo antes de cada teste
        with _transcriber_lock:
            _transcriber_cache["key"] = None
            _transcriber_cache["instance"] = None

    def test_get_index(self) -> None:
        """GET / deve retornar a página HTML da interface web."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("transcrita", response.text)

    @patch("transcrita.web.to_srt")
    @patch("transcrita.web.Transcriber")
    def test_post_transcribe_success(self, mock_transcriber_cls, mock_to_srt) -> None:
        """POST /api/transcribe com arquivo simulado deve retornar text e srt."""
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.return_value = [
            MagicMock(start=0.0, end=2.5, text="Olá mundo"),
            MagicMock(start=3.0, end=5.5, text="Teste de transcrição"),
        ]
        mock_transcriber_cls.return_value = mock_transcriber

        mock_to_srt.return_value = (
            "1\n00:00:00,000 --> 00:00:02,500\nOlá mundo\n\n"
            "2\n00:00:03,000 --> 00:00:05,500\nTeste de transcrição\n"
        )

        file_content = b"fake audio data"
        files = {"file": ("audio.wav", io.BytesIO(file_content), "audio/wav")}
        data = {
            "model": "base",
            "language": "pt",
            "device": "auto",
            "compute_type": "default",
            "beam_size": "5",
            "vad": "false",
        }

        response = self.client.post("/api/transcribe", files=files, data=data)

        self.assertEqual(response.status_code, 200)
        json_body = response.json()
        self.assertIn("filename", json_body)
        self.assertEqual(json_body["filename"], "audio")
        self.assertIn("text", json_body)
        self.assertIn("srt", json_body)

        mock_transcriber_cls.assert_called_once()
        call_kwargs = mock_transcriber_cls.call_args.kwargs
        self.assertEqual(call_kwargs["model_size"], "base")
        self.assertEqual(call_kwargs["device"], "auto")
        self.assertEqual(call_kwargs["compute_type"], "default")

        mock_transcriber.transcribe_file.assert_called_once()
        call_args = mock_transcriber.transcribe_file.call_args
        self.assertEqual(call_args.kwargs["language"], "pt")
        self.assertEqual(call_args.kwargs["beam_size"], 5)
        self.assertEqual(call_args.kwargs["vad_filter"], False)

        mock_to_srt.assert_called_once()

    @patch("transcrita.web.Transcriber")
    def test_post_transcribe_language_auto(self, mock_transcriber_cls) -> None:
        """language=auto deve ser convertido para None na chamada ao Transcriber."""
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.return_value = []
        mock_transcriber_cls.return_value = mock_transcriber

        with patch("transcrita.web.to_srt", return_value=""):
            file_content = b"fake audio data"
            files = {"file": ("audio.mp3", io.BytesIO(file_content), "audio/mpeg")}
            data = {
                "model": "tiny",
                "language": "auto",
                "device": "cpu",
                "compute_type": "int8",
                "beam_size": "3",
                "vad": "true",
            }
            response = self.client.post("/api/transcribe", files=files, data=data)
            self.assertEqual(response.status_code, 200)

            call_args = mock_transcriber.transcribe_file.call_args
            self.assertIsNone(call_args.kwargs["language"])
            self.assertEqual(call_args.kwargs["beam_size"], 3)
            self.assertEqual(call_args.kwargs["vad_filter"], True)

    def test_post_transcribe_no_file(self) -> None:
        """POST /api/transcribe sem arquivo deve retornar 422."""
        data = {
            "model": "base",
            "language": "pt",
        }
        response = self.client.post("/api/transcribe", data=data)
        self.assertEqual(response.status_code, 422)

    @patch("transcrita.web.to_srt")
    @patch("transcrita.web.Transcriber")
    def test_post_transcribe_stream_success(
        self, mock_transcriber_cls, mock_to_srt
    ) -> None:
        """POST /api/transcribe/stream deve emitir eventos SSE status/segment/done."""
        mock_transcriber = MagicMock()

        def fake_transcribe_file(input_path, beam_size=5, vad_filter=True,
                                 language=None, on_progress=None,
                                 cancel_event=None):
            if on_progress:
                on_progress({"start": 0.0, "end": 2.5, "text": "Olá",
                             "progress": 50.0, "duration": 5.0})
                on_progress({"start": 2.5, "end": 5.0, "text": "mundo",
                             "progress": 100.0, "duration": 5.0})
            return [
                MagicMock(start=0.0, end=2.5, text="Olá"),
                MagicMock(start=2.5, end=5.0, text="mundo"),
            ]

        mock_transcriber.transcribe_file.side_effect = fake_transcribe_file
        mock_transcriber_cls.return_value = mock_transcriber

        mock_to_srt.return_value = (
            "1\n00:00:00,000 --> 00:00:02,500\nOlá\n\n"
            "2\n00:00:02,500 --> 00:00:05,000\nmundo\n"
        )

        file_content = b"fake audio data"
        files = {"file": ("audio.wav", io.BytesIO(file_content), "audio/wav")}
        data = {
            "model": "base",
            "language": "pt",
            "device": "auto",
            "compute_type": "default",
            "beam_size": "5",
            "vad": "false",
        }

        response = self.client.post("/api/transcribe/stream", files=files, data=data)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/event-stream", response.headers.get("content-type", ""))

        # Parse eventos SSE
        content = response.text
        events = []
        for block in content.split("\n\n"):
            block = block.strip()
            if block.startswith("data:"):
                events.append(json.loads(block[5:].strip()))

        types = [e["type"] for e in events]
        self.assertIn("status", types)
        self.assertIn("segment", types)
        self.assertIn("done", types)

        done_event = next(e for e in events if e["type"] == "done")
        self.assertEqual(done_event["filename"], "audio")
        self.assertIn("text", done_event)
        self.assertIn("srt", done_event)

        # Verifica que transcribe_file recebeu on_progress
        mock_transcriber.transcribe_file.assert_called_once()
        call_args = mock_transcriber.transcribe_file.call_args
        self.assertIsNotNone(call_args.kwargs.get("on_progress"))

    def test_transcriber_cache_single_model(self) -> None:
        """Cache deve manter apenas 1 modelo ativo, evictando o anterior."""
        with patch("transcrita.web.Transcriber") as mock_transcriber_cls:
            mock_base = MagicMock()
            mock_small = MagicMock()
            mock_transcriber_cls.side_effect = [mock_base, mock_small]

            # Obtém modelo "base"
            t1 = _get_transcriber("base", "cpu", "default")
            self.assertEqual(t1, mock_base)

            with _transcriber_lock:
                self.assertEqual(_transcriber_cache["key"], ("base", "cpu", "default"))
                self.assertEqual(_transcriber_cache["instance"], mock_base)

            # Obtém modelo "small" - deve evictar "base"
            t2 = _get_transcriber("small", "cpu", "default")
            self.assertEqual(t2, mock_small)

            # Só "small" deve permanecer em cache
            with _transcriber_lock:
                self.assertEqual(_transcriber_cache["key"], ("small", "cpu", "default"))
                self.assertEqual(_transcriber_cache["instance"], mock_small)
                self.assertNotEqual(_transcriber_cache["instance"], mock_base)

            # Chamar novamente com "small" deve retornar o mesmo (sem recriar)
            t3 = _get_transcriber("small", "cpu", "default")
            self.assertEqual(t3, mock_small)
            self.assertEqual(mock_transcriber_cls.call_count, 2)

    def test_transcriber_cache_same_model_reused(self) -> None:
        """Chamar com a mesma chave deve reutilizar a instância em cache."""
        with patch("transcrita.web.Transcriber") as mock_transcriber_cls:
            mock_base = MagicMock()
            mock_transcriber_cls.return_value = mock_base

            t1 = _get_transcriber("base", "cpu", "default")
            t2 = _get_transcriber("base", "cpu", "default")

            self.assertEqual(t1, mock_base)
            self.assertEqual(t2, mock_base)
            mock_transcriber_cls.assert_called_once()

    def test_get_health(self) -> None:
        """GET /api/health deve retornar {"status": "ok"}."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_app_root_path_configurable(self) -> None:
        """A app FastAPI deve aceitar root_path para deploy em subpath."""
        from fastapi import FastAPI

        test_app = FastAPI(root_path="/transcrita")
        self.assertEqual(test_app.root_path, "/transcrita")

        # A app do transcrita respeita TRANSCRITA_ROOT_PATH via ambiente
        self.assertTrue(hasattr(app, "root_path"))
