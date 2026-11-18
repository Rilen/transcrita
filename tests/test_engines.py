"""Testes do contrato multimotor, feature flag e execução do Parakeet (sem pesos)."""

from __future__ import annotations

import io
import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import transcrita.web as web
from transcrita.core import Segment
from transcrita.web import app

DATASET = {"model": "base", "language": "pt", "device": "auto",
           "compute_type": "default", "beam_size": "5", "vad": "false"}


class FakeEngine:
    def __init__(self, segments=None, delay=0.0, error=None):
        self.segments = segments if segments is not None else [
            Segment(0.0, 1.0, "bom dia"), Segment(1.0, 2.0, "a todos")
        ]
        self.delay = delay
        self.error = error
        self.calls = 0

    def transcribe_file(self, path, **kwargs):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.segments


class EngineContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        web._parakeet_cache["key"] = None
        web._parakeet_cache["instance"] = None
        with web._transcriber_lock:
            web._transcriber_cache["key"] = None
            web._transcriber_cache["instance"] = None

    def _post(self, engine="whisper", path="/api/transcribe", fake=None, model=None):
        data = {**DATASET, "engine": engine}
        if model:
            data["model"] = model
        with patch.object(web, "_get_engine", return_value=fake or FakeEngine()):
            return self.client.post(
                path,
                files={"file": ("a.wav", io.BytesIO(b"fake"), "audio/wav")},
                data=data,
            )

    def test_engines_list_flag_off(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_PARAKEET": "false"}):
            data = self.client.get("/api/engines").json()["engines"]
        whisper = next(e for e in data if e["id"] == "whisper")
        parakeet = next(e for e in data if e["id"] == "parakeet")
        self.assertTrue(whisper["available"])
        self.assertEqual(whisper["status"], "stable")
        self.assertFalse(parakeet["available"])
        self.assertFalse(parakeet["enabled"])
        self.assertIn("TRANSCRITA_ENABLE_PARAKEET", parakeet["unavailable_reason"])
        self.assertTrue(parakeet["experimental"])

    def test_engines_list_flag_on_available(self) -> None:
        # Mock na origem (transcrita.asr) para não depender de pesos/dependência no runner.
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_PARAKEET": "true"}), \
             patch("transcrita.asr.parakeet_availability", return_value=(True, "")):
            data = self.client.get("/api/engines").json()["engines"]
        parakeet = next(e for e in data if e["id"] == "parakeet")
        self.assertTrue(parakeet["enabled"])
        self.assertTrue(parakeet["available"])
        self.assertEqual(parakeet["models"][0]["value"], "pt-br-int8")

    def test_reject_parakeet_when_disabled(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_PARAKEET": "false"}):
            resp = self._post("parakeet")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("desabilitado", resp.json()["detail"])

    def test_reject_unknown_engine(self) -> None:
        resp = self._post("outro")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("desconhecido", resp.json()["detail"])

    def test_reject_parakeet_wrong_model(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_PARAKEET": "true"}), \
             patch.object(web, "parakeet_availability", return_value=(True, "")):
            resp = self.client.post(
                "/api/transcribe",
                files={"file": ("a.wav", io.BytesIO(b"x"), "audio/wav")},
                data={**DATASET, "engine": "parakeet"},
            )
        self.assertEqual(resp.status_code, 400)

    def test_unavailable_parakeet_503(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_PARAKEET": "true"}), \
             patch.object(web, "parakeet_availability", return_value=(False, "pesos ausentes")):
            resp = self._post("parakeet")
        self.assertEqual(resp.status_code, 503)
        self.assertIn("pesos ausentes", resp.json()["detail"])

    def test_sync_reports_effective_engine(self) -> None:
        resp = self._post("whisper")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["engine"], "whisper")
        self.assertEqual(body["engine_status"], "stable")
        self.assertEqual(body["model"], "base")

    def test_sync_reports_parakeet_effective(self) -> None:
        with patch.dict(os.environ, {"TRANSCRITA_ENABLE_PARAKEET": "true"}), \
             patch.object(web, "parakeet_availability", return_value=(True, "")):
            resp = self._post("parakeet", model="pt-br-int8")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["engine"], "parakeet")
        self.assertTrue(body["experimental"])
        self.assertEqual(body["model"], "pt-br-int8")

    def test_stream_done_reports_engine(self) -> None:
        resp = self._post("whisper", path="/api/transcribe/stream")
        self.assertEqual(resp.status_code, 200)
        self.assertIn('"engine": "whisper"', resp.text)
        self.assertIn('"model": "base"', resp.text)

    def test_stream_error_includes_engine(self) -> None:
        fake = FakeEngine(error=RuntimeError("falha simulada"))
        resp = self._post("whisper", path="/api/transcribe/stream", fake=fake)
        self.assertIn("falha simulada", resp.text)
        self.assertIn('"engine": "whisper"', resp.text)

    def test_sync_load_failure_message(self) -> None:
        fake = FakeEngine(error=RuntimeError("modelo corrompido"))
        resp = self._post("whisper", fake=fake)
        self.assertEqual(resp.status_code, 500)
        self.assertIn("modelo corrompido", resp.json()["detail"])

    def test_srt_valid_in_sync_response(self) -> None:
        resp = self._post("whisper")
        srt = resp.json()["srt"]
        self.assertIn("00:00:00,000 --> 00:00:01,000", srt)
        self.assertIn("bom dia", srt)

    def test_concurrency_serialized_with_engine_param(self) -> None:
        """Duas requisições concorrentes serializam com um único mock (sem corrida de patch)."""
        fake = FakeEngine(delay=0.15)
        original = web._get_engine
        data = {**DATASET, "engine": "whisper"}
        start = time.perf_counter()
        results: list = []
        lock = threading.Lock()

        with patch.object(web, "_get_engine", return_value=fake):
            def call() -> None:
                resp = self.client.post(
                    "/api/transcribe",
                    files={"file": ("a.wav", io.BytesIO(b"fake"), "audio/wav")},
                    data=data,
                )
                with lock:
                    results.append(resp)

            threads = [threading.Thread(target=call) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        elapsed = time.perf_counter() - start
        self.assertEqual([r.status_code for r in results], [200, 200])
        self.assertGreaterEqual(elapsed, 0.28)
        # Restauração integral: nenhum mock pode permanecer no módulo.
        self.assertIs(web._get_engine, original)
        self.assertNotIsInstance(web._get_engine, MagicMock)

    def test_engine_cache_switches_single_model(self) -> None:
        with patch("transcrita.asr.parakeet.ParakeetEngine") as pk_cls, \
             patch("transcrita.web.Transcriber") as wh_cls, \
             patch("transcrita.web.parakeet_weights_path", return_value="/tmp/pk"):
            pk_inst = MagicMock()
            pk_cls.return_value = pk_inst
            wh_inst = MagicMock()
            wh_cls.return_value = wh_inst

            first = web._get_parakeet_engine("pt-br-int8")
            self.assertIs(first, pk_inst)
            self.assertEqual(web._parakeet_cache["key"], ("parakeet", "pt-br-int8"))

            second = web._get_transcriber("base", "cpu", "default")
            self.assertIs(second, wh_inst)
            pk_inst.unload.assert_called_once()
            self.assertIsNone(web._parakeet_cache["instance"])


class ParakeetUnitTests(unittest.TestCase):
    def _engine(self):
        from transcrita.asr.parakeet import ParakeetEngine

        eng = ParakeetEngine("/tmp/inexistente")
        eng._model = MagicMock()
        eng._model.recognize.side_effect = lambda chunk, **kw: "texto"
        return eng

    def test_segments_built_and_progress(self) -> None:
        eng = self._engine()
        eng._ensure_loaded = lambda: None
        eng._to_wav16k = lambda path, timeout: (path, False)
        eng._load_audio = lambda path: __import__("numpy").zeros(32000, dtype="float32")
        eng._vad_segments = lambda audio: [{"start": 0.0, "end": 0.5}, {"start": 1.0, "end": 1.5}]
        progress = []
        segs = eng.transcribe_file("x.wav", on_progress=progress.append)
        self.assertEqual(len(segs), 2)
        self.assertEqual([s.text for s in segs], ["texto", "texto"])
        self.assertEqual(progress[0]["progress"], 50)
        self.assertEqual(progress[-1]["progress"], 100)

    def test_cancellation_between_segments(self) -> None:
        eng = self._engine()
        eng._ensure_loaded = lambda: None
        eng._to_wav16k = lambda path, timeout: (path, False)
        eng._load_audio = lambda path: __import__("numpy").zeros(32000, dtype="float32")
        eng._vad_segments = lambda audio: [
            {"start": 0.0, "end": 0.5}, {"start": 1.0, "end": 1.5}, {"start": 2.0, "end": 2.5},
        ]
        cancel = threading.Event()
        segs = eng.transcribe_file("x.wav", cancel_event=cancel,
                                   on_progress=lambda _e: cancel.set())
        self.assertEqual(len(segs), 1)

    def test_temporary_wav_removed(self) -> None:
        import tempfile

        eng = self._engine()
        eng._ensure_loaded = lambda: None
        eng._vad_segments = lambda audio: []
        eng._load_audio = lambda path: __import__("numpy").zeros(16000, dtype="float32")
        tmpdir = tempfile.mkdtemp()
        tmp_wav = os.path.join(tmpdir, "conv.wav")
        open(tmp_wav, "wb").close()

        with patch("transcrita.asr.parakeet.Path.unlink") as unlink, \
             patch("tempfile.mkstemp", return_value=(os.open(tmp_wav, os.O_RDWR), tmp_wav)), \
             patch("transcrita.asr.parakeet.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stderr="")
            eng.transcribe_file("audio.mp4", ffmpeg_timeout=10)
            unlink.assert_called()


class ParakeetTokenTests(unittest.TestCase):
    """Tokens especiais do decoder ONNX não devem vazar para o texto final."""

    def test_clean_text_removes_special_tokens(self) -> None:
        from transcrita.asr.parakeet import _clean_text

        self.assertEqual(_clean_text("descortinou<unk>lhe"), "descortinoulhe")
        self.assertEqual(_clean_text("olá <|nospeech|> mundo"), "olá mundo")
        self.assertEqual(_clean_text("a<pad>b <|pnc|> c"), "ab c")
        self.assertEqual(_clean_text("texto <|emo:happy|> fim"), "texto fim")
        self.assertEqual(_clean_text("  espaços   múltiplos\n aqui  "), "espaços múltiplos aqui")

    def test_clean_text_preserves_legitimate_content(self) -> None:
        from transcrita.asr.parakeet import _clean_text

        self.assertEqual(_clean_text("eu <3 você"), "eu <3 você")
        self.assertEqual(_clean_text("tag <b>real</b> aqui"), "tag <b>real</b> aqui")
        self.assertEqual(_clean_text("Ação, coração! ção."), "Ação, coração! ção.")
        self.assertEqual(_clean_text(""), "")

    def test_transcribe_file_strips_tokens_from_segments(self) -> None:
        eng = ParakeetUnitTests()._engine()
        eng._model.recognize.side_effect = [
            "bom<unk> dia",
            "<|nospeech|>",
            "tchau <pad> agora",
        ]
        eng._ensure_loaded = lambda: None
        eng._to_wav16k = lambda path, timeout: (path, False)
        eng._load_audio = lambda path: __import__("numpy").zeros(48000, dtype="float32")
        eng._vad_segments = lambda audio: [
            {"start": 0.0, "end": 0.5}, {"start": 1.0, "end": 1.5}, {"start": 2.0, "end": 2.5},
        ]
        segs = eng.transcribe_file("x.wav")
        # Segmento que virou vazio após limpeza é descartado.
        self.assertEqual([s.text for s in segs], ["bom dia", "tchau agora"])


if __name__ == "__main__":
    unittest.main()
