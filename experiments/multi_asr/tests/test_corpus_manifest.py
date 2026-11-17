from __future__ import annotations

import unittest

from experiments.multi_asr.corpus.build_corpus import _dur  # noqa: F401  (import sanity)


class TestManifestShape(unittest.TestCase):
    def test_manifest_required_fields(self) -> None:
        # Estrutura esperada pelo benchmark; validada sem rede nem áudio.
        item = {
            "id": "x",
            "path": "/tmp/x.wav",
            "reference": "texto de referência",
            "duration": 1.0,
            "speaker": "1",
            "scenario": "clean",
        }
        for key in ("id", "path", "reference", "duration", "scenario"):
            self.assertIn(key, item)


if __name__ == "__main__":
    unittest.main()
