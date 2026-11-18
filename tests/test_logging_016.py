"""TRANSCRITA-016A: logging operacional e eventos terminais SSE."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import threading
import time
import unittest
from unittest.mock import patch

import transcrita  # noqa: F401  (import configura o logger do pacote)
import transcrita.web as web
from transcrita.core import Segment
from transcrita.web import app

BOUNDARY = "----t016a"


def _multipart(payload: bytes = b"", fields: dict | None = None) -> bytes:
    parts = []
    for k, v in (fields or {}).items():
        parts.append(
            f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        )
    parts.append(
        f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="a.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
    )
    parts.append(payload)
    parts.append(f"\r\n--{BOUNDARY}--\r\n".encode())
    return b"".join(parts)


class OkEngine:
    def transcribe_file(self, path, on_progress=None, cancel_event=None, **kw):
        if on_progress is not None:
            on_progress({"index": 0, "start": 0.0, "end": 1.0, "text": "ok", "progress": 100})
        return [Segment(0.0, 1.0, "ok")]


class FailEngine:
    def transcribe_file(self, path, **kw):
        raise RuntimeError("falha simulada")


class SlowEngine:
    def __init__(self) -> None:
        self.finished = threading.Event()
        self.cancelled = False

    def transcribe_file(self, path, on_progress=None, cancel_event=None, **kw):
        try:
            for _ in range(50):
                if cancel_event is not None and cancel_event.is_set():
                    self.cancelled = True
                    return []
                time.sleep(0.02)
            return [Segment(0.0, 1.0, "ok")]
        finally:
            self.finished.set()


class PackageLoggingConfigTests(unittest.TestCase):
    def test_transcrita_logger_configured_at_info(self) -> None:
        pkg = logging.getLogger("transcrita")
        self.assertTrue(pkg.handlers, "logger 'transcrita' sem handler configurado")
        self.assertLessEqual(pkg.getEffectiveLevel(), logging.INFO)
        self.assertFalse(pkg.propagate, "propagate deve ser False para evitar duplicatas")

    def test_child_loggers_inherit_configuration(self) -> None:
        for name in ("transcrita.web", "transcrita.core", "transcrita.asr"):
            child = logging.getLogger(name)
            self.assertLessEqual(child.getEffectiveLevel(), logging.INFO, name)

    def test_info_record_reaches_package_handler(self) -> None:
        """Um record INFO emitido por transcrita.web chega ao handler do pacote."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        pkg = logging.getLogger("transcrita")
        pkg.addHandler(handler)
        try:
            logging.getLogger("transcrita.web").info("evento_teste_016")
        finally:
            pkg.removeHandler(handler)
        self.assertIn("INFO transcrita.web: evento_teste_016", stream.getvalue())

    def test_no_duplicate_handlers(self) -> None:
        # pytest anexa seus próprios handlers de captura ao logger; o que
        # importa é que a configuração do pacote contribui exatamente um
        # StreamHandler próprio (sem duplicação em reimport/execução dupla).
        pkg = logging.getLogger("transcrita")
        ours = [h for h in pkg.handlers if type(h) is logging.StreamHandler]
        self.assertEqual(len(ours), 1)


class SseTerminalEventTests(unittest.TestCase):
    """Eventos terminais SSE alcançam o logger mesmo com engine real substituído."""

    def setUp(self) -> None:
        web._inference_semaphore = threading.Semaphore(1)
        with web._transcriber_lock:
            web._transcriber_cache["key"] = None
            web._transcriber_cache["instance"] = None
        web._parakeet_cache["key"] = None
        web._parakeet_cache["instance"] = None

    def _run_sse(self, engine, disconnect: bool):
        body = _multipart(b"fake", {"engine": "whisper", "model": "base", "language": "pt"})
        headers = [
            (b"content-type", f"multipart/form-data; boundary={BOUNDARY}".encode()),
            (b"content-length", str(len(body)).encode()),
        ]
        scope = {
            "type": "http", "method": "POST", "path": "/api/transcribe/stream",
            "root_path": "", "headers": headers, "query_string": b"",
            "scheme": "http", "server": ("test", 80), "client": ("127.0.0.1", 1),
        }
        body_sent = False
        signal = asyncio.Event()
        never = asyncio.Event()

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            if disconnect:
                await signal.wait()
                return {"type": "http.disconnect"}
            await never.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            # Desconexão só após o primeiro chunk SSE, como um cliente real.
            if disconnect and message.get("type") == "http.response.body" and message.get("body"):
                signal.set()

        async def main():
            with patch.object(web, "_get_engine", return_value=engine):
                await asyncio.wait_for(app(scope, receive, send), timeout=15)

        with self.assertLogs("transcrita.web", level="INFO") as cm:
            asyncio.run(main())
        return [r.getMessage() for r in cm.records]

    def test_sse_concluido_emitted(self) -> None:
        names = self._run_sse(OkEngine(), disconnect=False)
        self.assertIn("sse_iniciado", names)
        self.assertIn("sse_concluido", names)
        self.assertNotIn("sse_falha", names)
        self.assertNotIn("sse_cancelado", names)

    def test_sse_cancelado_emitted_on_disconnect(self) -> None:
        engine = SlowEngine()
        names = self._run_sse(engine, disconnect=True)
        self.assertIn("sse_cancelado", names)
        self.assertNotIn("sse_concluido", names)
        self.assertTrue(engine.finished.wait(3))

    def test_sse_falha_emitted_on_engine_error(self) -> None:
        names = self._run_sse(FailEngine(), disconnect=False)
        self.assertIn("sse_falha", names)
        self.assertNotIn("sse_concluido", names)

    def test_terminal_events_have_no_sensitive_data(self) -> None:
        """Eventos terminais não carregam nome de arquivo, texto ou caminhos."""
        names = self._run_sse(FailEngine(), disconnect=False)
        for name in names:
            if name.startswith("sse_"):
                self.assertNotIn("a.wav", name)
                self.assertNotIn("fake", name)
                self.assertNotIn("/", name)


if __name__ == "__main__":
    unittest.main()
