from __future__ import annotations

import unittest

from experiments.multi_asr.adapters.base import ASRAdapter, Segment, TranscriptionResult
from experiments.multi_asr.benchmark.run_benchmark import run_model


class FakeAdapter(ASRAdapter):
    name = "fake"

    def __init__(self) -> None:
        self.loaded = False
        self.unloaded = False

    def load(self, config):
        self.loaded = True

    def transcribe(self, audio_path, language="pt"):
        return TranscriptionResult(
            engine="fake",
            model_id="fake-1",
            language_configured=language,
            text="bom dia a todos",
            segments=[Segment(0.0, 1.0, "bom dia a todos")],
            audio_duration=1.0,
            processing_time=0.01,
            rtf=0.01,
        )

    def unload(self):
        self.unloaded = True

    def metadata(self):
        return {"engine": "fake"}


class TestContract(unittest.TestCase):
    def test_adapter_roundtrip(self) -> None:
        a = FakeAdapter()
        a.load({})
        self.assertTrue(a.loaded)
        res = a.transcribe("x.wav")
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.text, "bom dia a todos")
        self.assertEqual(a.metadata()["engine"], "fake")
        a.unload()
        self.assertTrue(a.unloaded)

    def test_runner_aggregates(self) -> None:
        import experiments.multi_asr.adapters as adapters_mod

        adapters_mod.ADAPTERS["fake"] = FakeAdapter
        manifest = [
            {"id": "c1", "scenario": "clean", "path": "x.wav", "reference": "bom dia a todos", "duration": 1.0}
        ]
        out = run_model("fake", {"type": "fake", "cpu_threads": 1}, manifest, "pt", 30, warmup=False)
        self.assertEqual(out["summary"]["clips_ok"], 1.0)
        self.assertAlmostEqual(out["summary"]["wer"], 0.0)


if __name__ == "__main__":
    unittest.main()
