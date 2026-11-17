from __future__ import annotations

import unittest

from experiments.multi_asr.benchmark.metrics import aggregate, error_rates, normalize_text


class TestMetrics(unittest.TestCase):
    def test_normalize_keeps_accents(self) -> None:
        self.assertEqual(normalize_text("Ação,  João!  "), "ação joão")

    def test_wer_cer_perfect(self) -> None:
        rates = error_rates("bom dia a todos", "bom dia a todos")
        self.assertEqual(rates["wer"], 0.0)
        self.assertEqual(rates["cer"], 0.0)

    def test_wer_one_substitution(self) -> None:
        rates = error_rates("bom dia a todos", "bom dia a todo")
        self.assertGreater(rates["wer"], 0.0)
        self.assertLessEqual(rates["wer"], 0.5)

    def test_aggregate_weighted(self) -> None:
        rows = [
            {"status": "ok", "wer": 0.1, "cer": 0.05, "ref_words": 10, "audio_duration": 10, "processing_time": 2},
            {"status": "ok", "wer": 0.2, "cer": 0.10, "ref_words": 30, "audio_duration": 30, "processing_time": 3},
            {"status": "error", "wer": 1.0, "ref_words": 5},
        ]
        agg = aggregate(rows)
        self.assertAlmostEqual(agg["wer"], (0.1 * 10 + 0.2 * 30) / 40, places=6)
        self.assertAlmostEqual(agg["rtf"], 5 / 40, places=6)
        self.assertEqual(agg["clips_ok"], 2.0)


if __name__ == "__main__":
    unittest.main()
