from __future__ import annotations

import unittest

from experiments.multi_asr.timestamps.hybrid import align_estimated
from experiments.multi_asr.timestamps.metrics_ts import boundary_error, text_integrity
from experiments.multi_asr.timestamps.srt import TsSegment, to_srt, validate_srt


class TestSrt(unittest.TestCase):
    def test_valid_srt(self) -> None:
        srt = to_srt([TsSegment(0.0, 1.2, "bom dia"), TsSegment(1.2, 2.5, "a todos")], 2.5)
        check = validate_srt(srt)
        self.assertTrue(check["valid"])
        self.assertEqual(check["blocks"], 2)

    def test_negative_and_overlap_sanitized(self) -> None:
        srt = to_srt([TsSegment(-1.0, 0.5, "a"), TsSegment(0.2, 1.0, "b")], 1.0)
        self.assertTrue(validate_srt(srt)["valid"])

    def test_empty_text_skipped(self) -> None:
        srt = to_srt([TsSegment(0.0, 1.0, "  "), TsSegment(1.0, 2.0, "ok")], 2.0)
        self.assertEqual(validate_srt(srt)["blocks"], 1)


class TestHybrid(unittest.TestCase):
    def test_alignment_groups_by_pause(self) -> None:
        text = "um dois tres quatro cinco seis"
        words = [("um", 0.0, 0.3), ("dois", 0.3, 0.6), ("tres", 0.6, 0.9),
                 ("quatro", 2.5, 2.8), ("cinco", 2.8, 3.1), ("seis", 3.1, 3.4)]
        segs = align_estimated(text, words, max_segment_s=10, pause_s=1.0)
        self.assertEqual(len(segs), 2)
        self.assertLess(segs[0]["end"], segs[1]["start"])
        self.assertIn("tres", segs[0]["text"])
        self.assertIn("quatro", segs[1]["text"])

    def test_no_words_returns_empty(self) -> None:
        self.assertEqual(align_estimated("texto", []), [])

    def test_text_integrity_identical(self) -> None:
        segs = [{"start": 0.0, "end": 1.0, "text": "bom dia a todos"}]
        self.assertEqual(text_integrity("bom dia a todos", segs)["wer_vs_full"], 0.0)


class TestBoundary(unittest.TestCase):
    def test_boundary_match_and_mae(self) -> None:
        pred = [{"start": 0.0}, {"start": 2.1}, {"start": 4.0}]
        ref = [{"start": 0.0}, {"start": 2.0}]
        out = boundary_error(pred, ref, 0.25)
        self.assertEqual(out["recall"], 1.0)
        self.assertAlmostEqual(out["mae_matched_s"], 0.05, places=3)

    def test_boundary_miss_outside_tolerance(self) -> None:
        out = boundary_error([{"start": 0.5}], [{"start": 1.0}], 0.25)
        self.assertEqual(out["recall"], 0.0)


if __name__ == "__main__":
    unittest.main()
