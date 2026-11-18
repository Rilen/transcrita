"""Regressões TRANSCRITA-013: limite de upload com root_path e ciclo SSE."""

from __future__ import annotations

import asyncio
import io
import json
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

import transcrita.web as web
from transcrita.core import Segment
from transcrita.web import UploadSizeLimitMiddleware, app

BOUNDARY = "----t013"


def _multipart(payload: bytes = b"", fields: dict | None = None) -> bytes:
    parts = []
    for k, v in (fields or {}).items():
        parts.append(f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="a.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
    )
    parts.append(payload)
    parts.append(f"\r\n--{BOUNDARY}--\r\n".encode())
    return b"".join(parts)


class FakeSlowEngine:
    """Motor fake que verifica cooperativamente o cancel_event."""

    def __init__(self, step_s: float = 0.02, steps: int = 25) -> None:
        self.step_s = step_s
        self.steps = steps
        self.cancelled = False
        self.finished = threading.Event()

    def transcribe_file(self, path, on_progress=None, cancel_event=None, **kw):
        try:
            for i in range(self.steps):
                if cancel_event is not None and cancel_event.is_set():
                    self.cancelled = True
                    return []
                if on_progress is not None:
                    on_progress({"index": i, "start": i * 0.1, "end": (i + 1) * 0.1,
                                 "text": f"p{i}", "progress": int((i + 1) * 100 / self.steps)})
                time.sleep(self.step_s)
            return [Segment(0.0, 1.0, "ok")]
        finally:
            self.finished.set()


class UploadRootPathTests(unittest.TestCase):
    def _middleware(self, root_path: str = ""):
        async def inner(scope, receive, send):
            # Consome o corpo para exercitar o contador do middleware.
            while True:
                message = await receive()
                if message.get("type") != "http.request" or not message.get("more_body"):
                    break
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        return UploadSizeLimitMiddleware(inner, root_path=root_path)

    def _call(self, mw, path, root_scope="", cl=None, body=b"", chunks=None):
        headers = [(b"content-type", b"multipart/form-data; boundary=x")]
        if cl is not None:
            headers.append((b"content-length", str(cl).encode()))
        scope = {"type": "http", "path": path, "root_path": root_scope, "headers": headers,
                 "method": "POST"}
        queue = list(chunks) if chunks is not None else [
            {"type": "http.request", "body": body, "more_body": False}
        ]
        sent = []

        async def receive():
            if queue:
                return queue.pop(0)
            return {"type": "http.disconnect"}

        async def send(msg):
            sent.append(msg)

        with patch.object(web, "MAX_UPLOAD_SIZE", 1024):
            try:
                asyncio.run(mw(scope, receive, send))
                exc = None
            except Exception as e:  # noqa: BLE001
                exc = e
        return sent, exc

    def test_route_path_normalization(self) -> None:
        cases = [
            ("/api/transcribe", "", "", "/api/transcribe"),
            ("/transcrita/api/transcribe", "/transcrita", "", "/api/transcribe"),
            ("/transcrita/api/transcribe", "", "/transcrita", "/api/transcribe"),
            ("/api/transcribe", "", "/transcrita", "/api/transcribe"),
            ("/outra/api/transcribe", "", "", "/outra/api/transcribe"),
        ]
        for path, scope_root, cfg_root, expected in cases:
            mw = self._middleware(cfg_root)
            scope = {"type": "http", "path": path, "root_path": scope_root}
            self.assertEqual(mw._route_path(scope), expected, (path, scope_root, cfg_root))

    def test_content_length_over_limit_with_root_path(self) -> None:
        for root_scope, cfg_root in (("/transcrita", ""), ("", "/transcrita")):
            sent, exc = self._call(self._middleware(cfg_root), "/transcrita/api/transcribe",
                                   root_scope=root_scope, cl=2048)
            self.assertIsNone(exc)
            self.assertEqual(sent[0]["status"], 413)

    def test_under_limit_with_root_path(self) -> None:
        sent, exc = self._call(self._middleware("/transcrita"), "/transcrita/api/transcribe",
                               root_scope="/transcrita", cl=100, body=b"x" * 100)
        self.assertIsNone(exc)
        self.assertEqual(sent[0]["status"], 200)

    def test_chunked_over_limit_with_root_path(self) -> None:
        chunks = [{"type": "http.request", "body": b"x" * 700, "more_body": True},
                  {"type": "http.request", "body": b"x" * 700, "more_body": False}]
        sent, exc = self._call(self._middleware("/transcrita"), "/transcrita/api/transcribe",
                               root_scope="/transcrita", chunks=chunks)
        self.assertIsInstance(exc, Exception)
        self.assertEqual(getattr(exc, "status_code", None), 413)

    def test_unrelated_route_untouched(self) -> None:
        sent, exc = self._call(self._middleware("/transcrita"), "/transcrita/api/health",
                               root_scope="/transcrita", cl=2048)
        self.assertIsNone(exc)
        self.assertEqual(sent[0]["status"], 200)

    def test_asgi_integration_root_path(self) -> None:
        sub = FastAPI(root_path="/transcrita")
        sub.add_middleware(UploadSizeLimitMiddleware, root_path="/transcrita")

        @sub.post("/api/transcribe")
        async def recv(request: Request):
            await request.body()
            return JSONResponse({"ok": True})

        def call(body: bytes, cl: int | None):
            headers = [(b"content-type", b"multipart/form-data; boundary=x")]
            if cl is not None:
                headers.append((b"content-length", str(cl).encode()))
            scope = {"type": "http", "method": "POST", "path": "/transcrita/api/transcribe",
                     "root_path": "/transcrita", "headers": headers, "query_string": b"",
                     "scheme": "http", "server": ("test", 80), "client": ("127.0.0.1", 1)}
            sent = []
            queue = [{"type": "http.request", "body": body, "more_body": False}]

            async def receive():
                return queue.pop(0) if queue else {"type": "http.disconnect"}

            async def send(m):
                sent.append(m)

            with patch.object(web, "MAX_UPLOAD_SIZE", 1024):
                asyncio.run(sub(scope, receive, send))
            return sent

        ok = call(b"x" * 100, 100)
        self.assertEqual(ok[0]["status"], 200)
        big = call(b"", 2048)
        self.assertEqual(big[0]["status"], 413)


class SseLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        web._inference_semaphore = threading.Semaphore(1)
        with web._transcriber_lock:
            web._transcriber_cache["key"] = None
            web._transcriber_cache["instance"] = None
        web._parakeet_cache["key"] = None
        web._parakeet_cache["instance"] = None

    def _run(self, spec_version: str, disconnect_after_first_chunk: bool):
        engine = FakeSlowEngine()
        body = _multipart(b"fake", {"engine": "whisper", "model": "base", "language": "pt"})
        headers = [(b"content-type", f"multipart/form-data; boundary={BOUNDARY}".encode()),
                   (b"content-length", str(len(body)).encode())]
        scope = {"type": "http", "method": "POST", "path": "/api/transcribe/stream",
                 "root_path": "", "headers": headers, "query_string": b"", "scheme": "http",
                 "server": ("test", 80), "client": ("127.0.0.1", 1),
                 "asgi": {"version": "3.0", "spec_version": spec_version}}
        sent = []
        signal = asyncio.Event()
        body_sent = False

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            if disconnect_after_first_chunk:
                await signal.wait()
                return {"type": "http.disconnect"}
            await asyncio.Event().wait()  # nunca resolve; será cancelado ao final

        async def send(message):
            sent.append(message)
            if (disconnect_after_first_chunk and message["type"] == "http.response.body"
                    and message.get("body")):
                signal.set()

        async def main():
            with patch.object(web, "_get_engine", return_value=engine):
                await asyncio.wait_for(app(scope, receive, send), timeout=15)

        with self.assertLogs("transcrita.web", level="INFO") as cm:
            asyncio.run(main())

        # Semáforo liberado (worker terminou) — espera limitada
        deadline = time.time() + 5
        while time.time() < deadline and not engine.finished.is_set():
            time.sleep(0.02)
        acquired = web._inference_semaphore.acquire(blocking=False)
        if acquired:
            web._inference_semaphore.release()
        return engine, sent, cm.records, acquired

    def test_normal_completion_logs_once(self) -> None:
        engine, sent, records, acquired = self._run("2.3", False)
        names = [r.getMessage() for r in records]
        self.assertIn("sse_iniciado", names)
        self.assertIn("sse_concluido", names)
        self.assertNotIn("sse_cancelado", names)
        self.assertTrue(engine.finished.wait(2))
        self.assertFalse(engine.cancelled)
        self.assertTrue(acquired)

    def test_disconnect_asgi_23_cancels_and_logs(self) -> None:
        engine, sent, records, acquired = self._run("2.3", True)
        names = [r.getMessage() for r in records]
        self.assertIn("sse_cancelado", names)
        self.assertNotIn("sse_concluido", names)
        cancel = [r for r in records if r.getMessage() == "sse_cancelado"][0]
        self.assertIn(cancel.motivo, ("tarefa_cancelada", "cliente_desconectado"))
        self.assertTrue(engine.finished.wait(2))
        self.assertTrue(engine.cancelled)
        self.assertTrue(acquired)

    def test_disconnect_asgi_24_cancels_and_logs(self) -> None:
        engine, sent, records, acquired = self._run("2.4", True)
        names = [r.getMessage() for r in records]
        self.assertIn("sse_cancelado", names)
        self.assertNotIn("sse_concluido", names)
        self.assertTrue(engine.finished.wait(2))
        self.assertTrue(engine.cancelled)
        self.assertTrue(acquired)

    def test_logs_have_no_filename_or_text(self) -> None:
        _, _, records, _ = self._run("2.3", False)
        for r in records:
            blob = r.getMessage() + json.dumps(getattr(r, "erro", ""), ensure_ascii=False)
            self.assertNotIn("a.wav", blob)
            self.assertNotIn("fake", blob)
            self.assertFalse(hasattr(r, "arquivo"))


if __name__ == "__main__":
    unittest.main()
