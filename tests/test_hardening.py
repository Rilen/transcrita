"""Testes de endurecimento (TRANSCRITA-009): upload chunked, sanitização, timeout, checksum e UI."""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

import transcrita.web as web
from transcrita.core import Segment
from transcrita.web import UploadSizeLimitMiddleware, app

BOUNDARY = "----audit009"
DATASET = {"engine": "whisper", "model": "base", "language": "pt"}


def _multipart(payload: bytes, fields: dict[str, str] | None = None) -> bytes:
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


def _chunks(data: bytes, size: int = 256, fail_after: int | None = None):
    sent = 0
    for i in range(0, len(data), size):
        if fail_after is not None and sent >= fail_after:
            raise OSError("upload interrompido")
        yield data[i:i + size]
        sent += 1


class UploadLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_middleware_counts_without_content_length(self) -> None:
        consumed = []

        async def inner(scope, receive, send):
            while True:
                msg = await receive()
                consumed.append(msg)
                if not msg.get("more_body"):
                    break

        mw = UploadSizeLimitMiddleware(inner)
        scope = {"type": "http", "path": "/api/transcribe", "headers": []}
        parts = [
            {"type": "http.request", "body": b"x" * 700, "more_body": True},
            {"type": "http.request", "body": b"x" * 700, "more_body": False},
        ]

        async def receive():
            return parts.pop(0)

        async def send(_msg):
            return None

        with patch.object(web, "MAX_UPLOAD_SIZE", 1024):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(mw(scope, receive, send))
        self.assertEqual(ctx.exception.status_code, 413)
        self.assertEqual(len(consumed), 1)  # cortou no 2º chunk, sem buffer integral

    def test_http_chunked_over_limit_413(self) -> None:
        body = _multipart(b"x" * 4096, DATASET)
        with patch.object(web, "MAX_UPLOAD_SIZE", 1024):
            resp = self.client.post(
                "/api/transcribe",
                content=_chunks(body),
                headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}"},
            )
        self.assertEqual(resp.status_code, 413)

    def test_http_chunked_under_limit_ok(self) -> None:
        fake = MagicMock()
        fake.transcribe_file.return_value = [Segment(0.0, 1.0, "ok")]
        body = _multipart(b"x" * 2048, DATASET)
        with patch.object(web, "MAX_UPLOAD_SIZE", 1024 * 1024), \
             patch.object(web, "_get_engine", return_value=fake):
            resp = self.client.post(
                "/api/transcribe",
                content=_chunks(body),
                headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["text"], "ok")

    def test_interrupted_upload_does_not_break_server(self) -> None:
        body = _multipart(b"x" * 8192, DATASET)
        fake = MagicMock()
        fake.transcribe_file.return_value = [Segment(0.0, 1.0, "ok")]
        try:
            with patch.object(web, "_get_engine", return_value=fake):
                self.client.post(
                    "/api/transcribe",
                    content=_chunks(body, fail_after=1),
                    headers={"content-type": f"multipart/form-data; boundary={BOUNDARY}"},
                )
        except Exception:
            pass
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        with patch.object(web, "_get_engine", return_value=fake):
            ok = self.client.post(
                "/api/transcribe",
                files={"file": ("a.wav", io.BytesIO(b"x"), "audio/wav")},
                data=DATASET,
            )
        self.assertEqual(ok.status_code, 200)


class SanitizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_sanitize_error_unit(self) -> None:
        msg = web._sanitize_error(OSError("/secret/weights/encoder.onnx falhou"))
        self.assertIn("[caminho]", msg)
        self.assertNotIn("/secret", msg)

    def test_sync_error_no_absolute_path(self) -> None:
        fake = MagicMock()
        fake.transcribe_file.side_effect = OSError("/secret/weights/encoder.onnx")
        with patch.object(web, "_get_engine", return_value=fake):
            resp = self.client.post(
                "/api/transcribe",
                files={"file": ("a.wav", io.BytesIO(b"x"), "audio/wav")},
                data=DATASET,
            )
        self.assertEqual(resp.status_code, 500)
        detail = resp.json()["detail"]
        self.assertIn("[caminho]", detail)
        self.assertNotIn("/secret", detail)

    def test_stream_error_no_absolute_path(self) -> None:
        fake = MagicMock()
        fake.transcribe_file.side_effect = OSError("/secret/weights/encoder.onnx")
        with patch.object(web, "_get_engine", return_value=fake):
            resp = self.client.post(
                "/api/transcribe/stream",
                files={"file": ("a.wav", io.BytesIO(b"x"), "audio/wav")},
                data=DATASET,
            )
        self.assertIn("[caminho]", resp.text)
        self.assertNotIn("/secret", resp.text)

    def test_engines_reason_no_absolute_path(self) -> None:
        with patch.dict(os.environ, {
            "TRANSCRITA_ENABLE_PARAKEET": "true",
            "TRANSCRITA_PARAKEET_MODEL": "/caminho/inexistente/pesos",
        }):
            data = self.client.get("/api/engines").json()["engines"]
        pk = next(e for e in data if e["id"] == "parakeet")
        self.assertFalse(pk["available"])
        self.assertNotIn("/caminho", pk["unavailable_reason"])
        self.assertNotIn("/", pk["unavailable_reason"])


class ParakeetHardeningTests(unittest.TestCase):
    def test_ffmpeg_timeout_cleans_temp(self) -> None:
        from transcrita.asr.parakeet import ParakeetEngine

        eng = ParakeetEngine("/tmp/inexistente")
        tmpdir = tempfile.mkdtemp()
        tmp = os.path.join(tmpdir, "conv.wav")
        open(tmp, "wb").close()
        fd = os.open(tmp, os.O_RDWR)
        try:
            with patch("tempfile.mkstemp", return_value=(fd, tmp)), \
                 patch("transcrita.asr.parakeet.subprocess.run",
                       side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)):
                with self.assertRaises(RuntimeError) as ctx:
                    eng._to_wav16k("audio.mp4", 1)
        finally:
            try:
                os.close(fd)
            except OSError:
                pass
        self.assertFalse(os.path.exists(tmp), "arquivo temporário deveria ser removido")
        self.assertNotIn(tmp, str(ctx.exception))

    def _weights_dir(self, payload: bytes) -> str:
        d = tempfile.mkdtemp()
        Path(d, "encoder-model.int8.onnx").write_bytes(payload)
        return d

    def test_checksum_mismatch_blocks(self) -> None:
        from transcrita.asr import parakeet_availability

        d = self._weights_dir(b"pesos")
        with patch.dict(os.environ, {
            "TRANSCRITA_ENABLE_PARAKEET": "true",
            "TRANSCRITA_PARAKEET_MODEL": d,
            "TRANSCRITA_PARAKEET_SHA256": "0" * 64,
        }), patch("importlib.util.find_spec", return_value=object()):
            ok, reason = parakeet_availability()
        self.assertFalse(ok)
        self.assertIn("checksum", reason)
        self.assertNotIn(d, reason)

    def test_checksum_match_allows(self) -> None:
        from transcrita.asr import parakeet_availability

        payload = b"pesos"
        d = self._weights_dir(payload)
        digest = hashlib.sha256(payload).hexdigest()
        with patch.dict(os.environ, {
            "TRANSCRITA_ENABLE_PARAKEET": "true",
            "TRANSCRITA_PARAKEET_MODEL": d,
            "TRANSCRITA_PARAKEET_SHA256": digest,
        }), patch("importlib.util.find_spec", return_value=object()):
            ok, reason = parakeet_availability()
        self.assertTrue(ok, reason)


class UiContractTests(unittest.TestCase):
    def test_ui_hides_parakeet_specific_controls(self) -> None:
        html = Path("transcrita/static/index.html").read_text(encoding="utf-8")
        self.assertIn('aria-live="polite"', html)
        self.assertIn("appendDecodingParams", html)
        self.assertIn("VAD interno fixo", html)
        self.assertIn("beamInput.disabled = isParakeet", html)
        self.assertIn("vadBox.disabled = isParakeet", html)
        # Whiper preserva os controles
        self.assertIn("beam_size", html)
        self.assertIn("vad", html)


if __name__ == "__main__":
    unittest.main()
