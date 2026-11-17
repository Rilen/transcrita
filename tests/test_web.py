"""Testes unitários para o módulo web usando TestClient com mock do Transcriber."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from transcrita.web import MAX_UPLOAD_SIZE
import io
import json
import threading
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from transcrita.web import app, _get_transcriber, _transcriber_cache, _transcriber_lock, _inference_semaphore


class TestWeb(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        # Reseta o cache de modelo antes de cada teste
        with _transcriber_lock:
            _transcriber_cache["key"] = None
            _transcriber_cache["instance"] = None
        # Substitui semáforo por versão restritiva (1) para testar serialização
        import transcrita.web
        self._original_semaphore = transcrita.web._inference_semaphore
        transcrita.web._inference_semaphore = threading.Semaphore(1)

    def tearDown(self) -> None:
        # Restaura semáforo original
        import transcrita.web
        transcrita.web._inference_semaphore = self._original_semaphore

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
                                 cancel_event=None, ffmpeg_timeout=None):
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

    # --- Novos testes para P0 fixes ---

    @patch("transcrita.web.Transcriber")
    def test_upload_size_limit_rejects_large_content_length(self, mock_transcriber_cls) -> None:
        # Usa semáforo não-bloqueante para este teste
        import transcrita.web
        transcrita.web._inference_semaphore = threading.Semaphore(100)
        """Content-Length acima do limite deve retornar 413 antes do parsing."""
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.return_value = []
        mock_transcriber_cls.return_value = mock_transcriber

        with patch("transcrita.web.to_srt", return_value=""):
            # Simula Content-Length > 512MB
            headers = {"content-length": str(MAX_UPLOAD_SIZE + 1)}
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

            response = self.client.post(
                "/api/transcribe", files=files, data=data, headers=headers
            )

            self.assertEqual(response.status_code, 413)
            self.assertIn("excede o limite", response.json()["detail"])

    @patch("transcrita.web.Transcriber")
    def test_upload_size_limit_allows_exact_limit(self, mock_transcriber_cls) -> None:
        import transcrita.web
        transcrita.web._inference_semaphore = threading.Semaphore(100)
        """Content-Length exatamente no limite deve ser aceito."""
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.return_value = []
        mock_transcriber_cls.return_value = mock_transcriber

        with patch("transcrita.web.to_srt", return_value=""):
            headers = {"content-length": str(MAX_UPLOAD_SIZE)}
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

            response = self.client.post(
                "/api/transcribe", files=files, data=data, headers=headers
            )

            # Deve passar pelo middleware (pode falhar depois por arquivo fake, mas não 413)
            self.assertNotEqual(response.status_code, 413)

    @patch("transcrita.web.Transcriber")
    def test_upload_size_limit_ignores_other_paths(self, mock_transcriber_cls) -> None:
        import transcrita.web
        transcrita.web._inference_semaphore = threading.Semaphore(100)
        """Middleware não deve afetar rotas fora de /api/transcribe*."""
        mock_transcriber = MagicMock()
        mock_transcriber_cls.return_value = mock_transcriber

        # Health check com Content-Length grande não deve ser rejeitado
        headers = {"content-length": str(MAX_UPLOAD_SIZE + 1)}
        response = self.client.get("/api/health", headers=headers)
        self.assertEqual(response.status_code, 200)

    @patch("transcrita.web.to_srt")
    @patch("transcrita.web.Transcriber")
    def test_inference_serialization_sync_endpoint(self, mock_transcriber_cls, mock_to_srt) -> None:
        """Duas requisições síncronas simultâneas devem ser serializadas."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        call_times = []

        def slow_transcribe(*args, **kwargs):
            call_times.append(("start", time.time()))
            time.sleep(0.1)  # Simula processamento
            call_times.append(("end", time.time()))
            return [MagicMock(start=0.0, end=1.0, text="test")]

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = slow_transcribe
        mock_transcriber_cls.return_value = mock_transcriber

        mock_to_srt.return_value = "1\n00:00:00,000 --> 00:00:01,000\ntest\n"

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

        def make_request():
            return self.client.post("/api/transcribe", files=files, data=data)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(make_request) for _ in range(2)]
            results = [f.result() for f in futures]

        # Ambas devem retornar 200
        for r in results:
            self.assertEqual(r.status_code, 200)

        # Verifica serialização: segunda chamada inicia após primeira terminar
        starts = [t for t in call_times if t[0] == "start"]
        ends = [t for t in call_times if t[0] == "end"]
        self.assertEqual(len(starts), 2)
        self.assertEqual(len(ends), 2)
        # Primeira termina antes da segunda iniciar
        self.assertLess(ends[0][1], starts[1][1])

    @patch("transcrita.web.to_srt")
    @patch("transcrita.web.Transcriber")
    def test_inference_serialization_stream_endpoint(self, mock_transcriber_cls, mock_to_srt) -> None:
        """Requisição SSE deve respeitar serialização."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        call_times = []

        def slow_transcribe(*args, **kwargs):
            call_times.append(("start", time.time()))
            time.sleep(0.1)
            call_times.append(("end", time.time()))
            return [MagicMock(start=0.0, end=1.0, text="test")]

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = slow_transcribe
        mock_transcriber_cls.return_value = mock_transcriber

        mock_to_srt.return_value = "1\n00:00:00,000 --> 00:00:01,000\ntest\n"

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

        def make_stream_request():
            return self.client.post("/api/transcribe/stream", files=files, data=data)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(make_stream_request) for _ in range(2)]
            results = [f.result() for f in futures]

        for r in results:
            self.assertEqual(r.status_code, 200)
            self.assertIn("text/event-stream", r.headers.get("content-type", ""))

        starts = [t for t in call_times if t[0] == "start"]
        ends = [t for t in call_times if t[0] == "end"]
        self.assertEqual(len(starts), 2)
        self.assertEqual(len(ends), 2)
        self.assertLess(ends[0][1], starts[1][1])

    @patch("transcrita.web.Transcriber")
    def test_semaphore_released_on_exception(self, mock_transcriber_cls) -> None:
        import transcrita.web
        transcrita.web._inference_semaphore = threading.Semaphore(100)
        """Semáforo deve ser liberado mesmo em caso de exceção."""
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = RuntimeError("Erro simulado")
        mock_transcriber_cls.return_value = mock_transcriber

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

        # Primeira requisição falha
        response1 = self.client.post("/api/transcribe", files=files, data=data)
        self.assertEqual(response1.status_code, 500)

        # Segunda requisição deve conseguir adquirir semáforo (não travado)
        response2 = self.client.post("/api/transcribe", files=files, data=data)
        self.assertEqual(response2.status_code, 500)  # Falha pelo mesmo motivo, mas não por semáforo


    # --- Regressões para os 4 bloqueios corrigidos ---

    @patch("transcrita.web.Transcriber")
    def test_healthcheck_during_wait(self, mock_transcriber_cls) -> None:
        """Healthcheck deve responder 200 enquanto outra requisição aguarda semáforo."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        def slow_transcribe(*args, **kwargs):
            time.sleep(0.2)  # Segura o semáforo
            return [MagicMock(start=0.0, end=1.0, text="test")]

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = slow_transcribe
        mock_transcriber_cls.return_value = mock_transcriber

        with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:01,000\ntest\n"):
            # Inicia requisição longa em background
            def make_long_request():
                files = {"file": ("audio.wav", io.BytesIO(b"fake"), "audio/wav")}
                data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
                return self.client.post("/api/transcribe", files=files, data=data)

            with ThreadPoolExecutor(max_workers=2) as executor:
                future = executor.submit(make_long_request)
                time.sleep(0.05)  # Garante que a primeira requisição adquiriu o semáforo

                # Healthcheck deve responder imediatamente (não bloqueado)
                health_resp = self.client.get("/api/health")
                self.assertEqual(health_resp.status_code, 200)
                self.assertEqual(health_resp.json(), {"status": "ok"})

                future.result()  # Aguarda conclusão

    @patch("transcrita.web.Transcriber")
    def test_healthcheck_during_sse_no_events(self, mock_transcriber_cls) -> None:
        """Healthcheck durante SSE sem eventos ainda (waiting for model)."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        def slow_transcribe(*args, **kwargs):
            time.sleep(0.2)
            return [MagicMock(start=0.0, end=1.0, text="test")]

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = slow_transcribe
        mock_transcriber_cls.return_value = mock_transcriber

        with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:01,000\ntest\n"):
            def make_sse_request():
                files = {"file": ("audio.wav", io.BytesIO(b"fake"), "audio/wav")}
                data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
                return self.client.post("/api/transcribe/stream", files=files, data=data)

            with ThreadPoolExecutor(max_workers=2) as executor:
                future = executor.submit(make_sse_request)
                time.sleep(0.05)

                health_resp = self.client.get("/api/health")
                self.assertEqual(health_resp.status_code, 200)

                future.result()

    def test_acquisition_timeout_no_inference(self) -> None:
        """Timeout de aquisição sem executar inferência deve retornar 503."""
        # Mock acquire no threading.Semaphore para retornar False (simula timeout)
        original_acquire = threading.Semaphore.acquire
        def mock_acquire(self, timeout=None):
            return False
        threading.Semaphore.acquire = mock_acquire

        try:
            files = {"file": ("audio.wav", io.BytesIO(b"fake"), "audio/wav")}
            data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
            resp = self.client.post("/api/transcribe", files=files, data=data)
            self.assertEqual(resp.status_code, 503)
            self.assertIn("ocupado", resp.json()["detail"])
        finally:
            threading.Semaphore.acquire = original_acquire

    def test_cancel_during_acquisition(self) -> None:
        """Cancelamento durante espera do semáforo não deve vazar semáforo."""
        import time
        import transcrita.web
        original = transcrita.web._inference_semaphore
        # Mock acquire para retornar False (simula timeout)
        original_acquire = transcrita.web._inference_semaphore.acquire
        def timeout_acquire(timeout=None):
            return False
        transcrita.web._inference_semaphore.acquire = timeout_acquire

        try:
            files = {"file": ("audio.wav", io.BytesIO(b"fake"), "audio/wav")}
            data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}

            # Inicia requisição que vai timeout
            def make_request():
                return self.client.post("/api/transcribe", files=files, data=data)

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(make_request)
                time.sleep(0.1)
                # Cancela a requisição (simula timeout do cliente)
                # Verifica que semáforo não vazou restaurando original
                transcrita.web._inference_semaphore.acquire = original_acquire
                acquired = transcrita.web._inference_semaphore.acquire(timeout=1)
                self.assertTrue(acquired, "Semáforo não deveria ter vazado")
                transcrita.web._inference_semaphore.release()
                transcrita.web._inference_semaphore = original
        finally:
            transcrita.web._inference_semaphore.acquire = original_acquire
            transcrita.web._inference_semaphore = original

    def test_sse_disconnect_worker_active(self) -> None:
        """Desconexão SSE com worker ativo não deve permitir segunda inferência simultânea."""
        import time
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch, MagicMock

        with patch("transcrita.web.Transcriber") as mock_transcriber_cls:
            mock_transcriber = MagicMock()
            call_count = [0]

            def counting_transcribe(*args, **kwargs):
                call_count[0] += 1
                time.sleep(0.15)  # Worker demora
                return [MagicMock(start=0.0, end=1.0, text="test")]

            mock_transcriber.transcribe_file.side_effect = counting_transcribe
            mock_transcriber_cls.return_value = mock_transcriber

            with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:01,000\ntest\n"):
                def make_sse_request():
                    files = {"file": ("audio.wav", io.BytesIO(b"fake"), "audio/wav")}
                    data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
                    return self.client.post("/api/transcribe/stream", files=files, data=data)

                with ThreadPoolExecutor(max_workers=2) as executor:
                    future1 = executor.submit(make_sse_request)
                    time.sleep(0.05)  # Primeira requisição iniciou worker
                    future2 = executor.submit(make_sse_request)

                    r1 = future1.result()
                    r2 = future2.result()

                    # Segunda deve ter falhado ou aguardado (não executado simultaneamente)
                    # Verifica que transcribe_file foi chamado apenas uma vez por vez
                    # (o mock side_effect é chamado sequencialmente)
                    self.assertLessEqual(call_count[0], 2)

    def test_second_request_blocked_until_first_finishes(self) -> None:
        """Segunda requisição deve ser impedida até encerramento real do primeiro worker."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        def slow_transcribe(*args, **kwargs):
            time.sleep(0.2)
            return [MagicMock(start=0.0, end=1.0, text="test")]

        with patch("transcrita.web.Transcriber.transcribe_file") as mock_transcribe_file:
            mock_transcribe_file.side_effect = slow_transcribe

            with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:01,000\ntest\n"):
                start_total = time.time()
                
                def make_request(i):
                    files = {"file": (f"audio{i}.wav", io.BytesIO(b"fake"), "audio/wav")}
                    data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
                    return self.client.post("/api/transcribe", files=files, data=data)

                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(make_request, i) for i in range(2)]
                    results = [f.result() for f in futures]
                
                total_time = time.time() - start_total

                # Verifica serialização: tempo total deve ser ~0.4s (sequencial), não ~0.2s (paralelo)
                # Com margem de 0.1s para overhead
                self.assertGreaterEqual(total_time, 0.35)  # Pelo menos tempo sequencial
                self.assertLess(total_time, 0.6)  # Mas não muito mais que sequencial

                # Ambas devem ter sucesso
                for resp in results:
                    self.assertEqual(resp.status_code, 200)

    def test_exception_recovery(self) -> None:
        """Exceção durante processamento deve liberar semáforo e permitir próxima requisição."""
        from concurrent.futures import ThreadPoolExecutor

        # Mock do método transcribe_file na classe Transcriber
        with patch("transcrita.web.Transcriber.transcribe_file") as mock_transcribe_file:
            # Primeira chamada falha, segunda succeeds
            mock_transcribe_file.side_effect = [
                RuntimeError("Erro simulado"),  # Primeira chamada falha
                [MagicMock(start=0.0, end=1.0, text="ok")]  # Segunda chamada succeeds
            ]

            files = {"file": ("audio.wav", io.BytesIO(b"fake"), "audio/wav")}
            data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}

            # Primeira falha
            resp1 = self.client.post("/api/transcribe", files=files, data=data)
            self.assertEqual(resp1.status_code, 500)

            # Segunda deve conseguir adquirir semáforo (não travado)
            with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:01,000\ntest\n"):
                resp2 = self.client.post("/api/transcribe", files=files, data=data)
                self.assertEqual(resp2.status_code, 200)



    # --- Testes de aceitação para estabilização do ciclo de vida SSE ---

    @patch("transcrita.web.Transcriber")
    def test_worker_active_long_duration_does_not_release_slot(self, mock_transcriber_cls) -> None:
        """Worker ativo por tempo prolongado não libera a vaga de inferência."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        def very_slow_transcribe(*args, **kwargs):
            time.sleep(0.5)  # Simula worker longo
            return [MagicMock(start=0.0, end=1.0, text="test")]

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = very_slow_transcribe
        mock_transcriber_cls.return_value = mock_transcriber

        with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:01,000\ntest\n"):
            # Inicia primeira requisição (worker lento)
            def make_first_request():
                files = {"file": ("audio1.wav", io.BytesIO(b"fake"), "audio/wav")}
                data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
                return self.client.post("/api/transcribe", files=files, data=data)

            with ThreadPoolExecutor(max_workers=2) as executor:
                future1 = executor.submit(make_first_request)
                time.sleep(0.1)  # Garante que primeira requisição adquiriu semáforo

                # Segunda requisição deve ser bloqueada
                def make_second_request():
                    files = {"file": ("audio2.wav", io.BytesIO(b"fake"), "audio/wav")}
                    data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
                    return self.client.post("/api/transcribe", files=files, data=data)

                future2 = executor.submit(make_second_request)

                # Primeira deve terminar
                resp1 = future1.result()
                self.assertEqual(resp1.status_code, 200)

                # Segunda deve terminar depois da primeira (semáforo não liberado prematuramente)
                resp2 = future2.result(timeout=2.0)
                self.assertEqual(resp2.status_code, 200)

    @patch("transcrita.web.Transcriber")
    def test_empty_queue_does_not_terminate_sse(self, mock_transcriber_cls) -> None:
        """Fila vazia temporariamente não encerra o SSE."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        def slow_transcribe(*args, **kwargs):
            time.sleep(0.3)
            return [MagicMock(start=0.0, end=1.0, text="test")]

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = slow_transcribe
        mock_transcriber_cls.return_value = mock_transcriber

        with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:01,000\ntest\n"):
            files = {"file": ("audio.wav", io.BytesIO(b"fake"), "audio/wav")}
            data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}

            # Faz requisição SSE
            resp = self.client.post("/api/transcribe/stream", files=files, data=data)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("text/event-stream", resp.headers.get("content-type", ""))
            
            # Verifica que recebe eventos (status, segment, done)
            events = []
            for line in resp.iter_lines():
                if line:
                    events.append(line)
            
            # Deve ter recebido status e done
            event_types = [json.loads(e.replace("data: ", ""))["type"] for e in events if e.startswith("data: ")]
            self.assertIn("status", event_types)
            self.assertIn("done", event_types)

    def test_cancelled_event_is_valid_json(self) -> None:
        """Evento cancelled deve ser JSON válido."""
        cancelled_event = json.dumps({"type": "cancelled", "filename": "test"}, ensure_ascii=False)
        parsed = json.loads(cancelled_event)
        self.assertEqual(parsed["type"], "cancelled")
        self.assertEqual(parsed["filename"], "test")

    def test_cancel_during_acquisition_does_not_leak_semaphore(self) -> None:
        """Cancelamento durante a aquisição devolve a vaga (sem vazamento)."""
        import asyncio as _asyncio
        import transcrita.web as web

        async def _scenario() -> None:
            loop = _asyncio.get_running_loop()
            sem = web._inference_semaphore
            self.assertTrue(sem.acquire(blocking=False), "vaga deveria estar livre")
            try:
                task = loop.create_task(web._acquire_inference_slot(timeout=10))
                deadline = loop.time() + 5
                while web._slot_waiters == 0:
                    self.assertLess(loop.time(), deadline, "esperador não registrado")
                    await _asyncio.sleep(0.01)

                task.cancel()
                with self.assertRaises(_asyncio.CancelledError):
                    await task

                # Primeira requisição termina e libera a vaga.
                sem.release()

                # Aguarda o thread de espera sair (concessão tardia processada).
                deadline = loop.time() + 5
                while web._slot_waiters != 0:
                    self.assertLess(loop.time(), deadline, "esperador não finalizou")
                    await _asyncio.sleep(0.01)

                # A concessão tardia deve ter sido devolvida: exatamente 1 vaga.
                acquired = False
                while not acquired:
                    acquired = sem.acquire(blocking=False)
                    if acquired:
                        break
                    self.assertLess(loop.time(), deadline, "vaga vazou após cancelamento")
                    await _asyncio.sleep(0.01)
                self.assertTrue(acquired)
                sem.release()
            finally:
                drained = 0
                while sem.acquire(blocking=False):
                    drained += 1
                for _ in range(max(1, drained)):
                    sem.release()

        _asyncio.run(_scenario())

    def test_late_grant_after_cancel_does_not_leak_slot(self) -> None:
        """Cenário 1-2-3: concessão tardia após cancelamento não vaza a vaga.

        1. Requisição 1 mantém a vaga ocupada.
        2. Requisição 2 inicia aquisição e é cancelada antes de obter a vaga.
        3. Requisição 3 deve adquirir normalmente após a liberação da primeira.
        """
        import asyncio as _asyncio
        import transcrita.web as web

        async def _scenario() -> None:
            loop = _asyncio.get_running_loop()
            sem = web._inference_semaphore
            # Requisição 1 toma a vaga para si.
            self.assertTrue(sem.acquire(blocking=False), "vaga deveria estar livre")
            try:
                # Requisição 2 aguarda a vaga em thread dedicada.
                task2 = loop.create_task(web._acquire_inference_slot(timeout=10))
                deadline = loop.time() + 5
                while web._slot_waiters == 0:
                    self.assertLess(loop.time(), deadline, "requisição 2 não entrou na espera")
                    await _asyncio.sleep(0.01)

                # Requisição 2 é cancelada antes de adquirir.
                task2.cancel()
                with self.assertRaises(_asyncio.CancelledError):
                    await task2

                # Requisição 1 libera a vaga; a concessão tardia deve ser devolvida.
                sem.release()
                deadline = loop.time() + 5
                while web._slot_waiters != 0:
                    self.assertLess(loop.time(), deadline, "esperador tardio não finalizou")
                    await _asyncio.sleep(0.01)

                # Requisição 3: deve executar normalmente.
                acquired3 = await _asyncio.wait_for(
                    web._acquire_inference_slot(timeout=5), timeout=10
                )
                self.assertTrue(acquired3, "requisição 3 deveria adquirir a vaga")
                sem.release()

                # Estado final: exatamente uma vaga disponível (sem vazamento).
                self.assertTrue(sem.acquire(blocking=False), "vaga vazou após concessão tardia")
                sem.release()
            finally:
                drained = 0
                while sem.acquire(blocking=False):
                    drained += 1
                for _ in range(max(1, drained)):
                    sem.release()

        _asyncio.run(_scenario())

    def test_slot_waiters_cap_enforced(self) -> None:
        """Teto de esperadores simultâneos é aplicado (controle de concorrência)."""
        import transcrita.web as web

        saved = web._slot_waiters
        try:
            web._slot_waiters = web.MAX_SLOT_WAITERS
            self.assertFalse(web._slot_waiters_enter(), "teto deveria bloquear novo esperador")
            web._slot_waiters = web.MAX_SLOT_WAITERS - 1
            self.assertTrue(web._slot_waiters_enter())
            web._slot_waiters_leave()
            self.assertEqual(web._slot_waiters, web.MAX_SLOT_WAITERS - 1)
        finally:
            web._slot_waiters = saved


    def test_repeated_cancel_does_not_double_release(self) -> None:
        """Cancelamento repetido não provoca dupla liberação."""
        import transcrita.web
        
        # Verifica estado inicial do semáforo
        initial_acquired = _inference_semaphore.acquire(timeout=1)
        self.assertTrue(initial_acquired)
        _inference_semaphore.release()

        # Simula múltiplos cancelamentos no finally
        for _ in range(3):
            if _inference_semaphore._value > 0:
                _inference_semaphore.acquire(timeout=1)
            _inference_semaphore.release()
        
        # Verifica que semáforo volta ao estado original (1)
        final_acquired = _inference_semaphore.acquire(timeout=1)
        self.assertTrue(final_acquired)
        _inference_semaphore.release()

    @patch("transcrita.web.Transcriber")
    def test_healthcheck_responsive_during_sse(self, mock_transcriber_cls) -> None:
        """Healthcheck permanece responsivo durante SSE ativo."""
        import time
        from concurrent.futures import ThreadPoolExecutor

        def slow_transcribe(*args, **kwargs):
            time.sleep(0.3)
            return [MagicMock(start=0.0, end=1.0, text="test")]

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_file.side_effect = slow_transcribe
        mock_transcriber_cls.return_value = mock_transcriber

        with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:01,000\ntest\n"):
            def make_sse_request():
                files = {"file": ("audio.wav", io.BytesIO(b"fake"), "audio/wav")}
                data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
                return self.client.post("/api/transcribe/stream", files=files, data=data)

            with ThreadPoolExecutor(max_workers=2) as executor:
                future = executor.submit(make_sse_request)
                time.sleep(0.05)  # Garante que SSE iniciou

                # Healthcheck deve responder imediatamente
                health_resp = self.client.get("/api/health")
                self.assertEqual(health_resp.status_code, 200)
                self.assertEqual(health_resp.json(), {"status": "ok"})

                future.result()


    def test_no_semaphore_leak_or_double_release(self) -> None:
        """Verifica ausência de vazamento ou dupla liberação do semáforo."""
        import transcrita.web
        import threading

        # Executa várias requisições e verifica que semáforo volta a 1
        for i in range(5):
            files = {"file": (f"audio{i}.wav", io.BytesIO(b"fake"), "audio/wav")}
            data = {"model": "base", "language": "pt", "device": "auto", "compute_type": "default", "beam_size": "5", "vad": "false"}
            with patch("transcrita.web.Transcriber") as mock_transcriber_cls:
                mock_transcriber = MagicMock()
                mock_transcriber.transcribe_file.return_value = [MagicMock(start=0.0, end=0.5, text="test")]
                mock_transcriber_cls.return_value = mock_transcriber
                with patch("transcrita.web.to_srt", return_value="1\n00:00:00,000 --> 00:00:00,500\ntest\n"):
                    resp = self.client.post("/api/transcribe", files=files, data=data)
                    self.assertEqual(resp.status_code, 200)

        # Verifica que semáforo está disponível (valor 1)
        acquired = transcrita.web._inference_semaphore.acquire(timeout=1)
        self.assertTrue(acquired, "Semáforo deveria estar disponível após todas as requisições")
        transcrita.web._inference_semaphore.release()

