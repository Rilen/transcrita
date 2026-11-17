from __future__ import annotations

import unittest

from experiments.multi_asr.benchmark.metrics import (
    error_breakdown,
    numeric_accuracy,
    numeric_tokens,
    rare_token_recall,
)


class TestErrorAnalysis(unittest.TestCase):
    def test_breakdown_counts(self) -> None:
        out = error_breakdown("a b c d", "a x c")
        self.assertEqual(out["hits"], 2.0)
        self.assertEqual(out["substitutions"], 1.0)
        self.assertEqual(out["deletions"], 1.0)
        self.assertEqual(out["insertions"], 0.0)

    def test_numeric_tokens(self) -> None:
        self.assertEqual(numeric_tokens("em 2024, foram 1,5 mil"), ["2024", "1.5"])

    def test_numeric_accuracy(self) -> None:
        out = numeric_accuracy(["reunião em 2024 com 12 pessoas"], ["reunião em 2024 com doze pessoas"])
        self.assertEqual(out["ref_numbers"], 2.0)
        self.assertEqual(out["matched"], 1.0)
        self.assertAlmostEqual(out["recall"], 0.5)

    def test_rare_token_recall(self) -> None:
        out = rare_token_recall(["vereador apresentou projeto"], ["vereador apresentou projeto"])
        self.assertGreaterEqual(out["rare_tokens"], 1.0)
        self.assertAlmostEqual(out["rare_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
