from __future__ import annotations

import unittest

from experiments.multi_asr.timestamps.reconcile import reconcile, token_times
from experiments.multi_asr.timestamps.srt import TsSegment, to_srt, validate_srt
from experiments.multi_asr.timestamps.vad_parakeet import merge_segments


class TestMerge(unittest.TestCase):
    def test_merge_small_gaps(self) -> None:
        segs = [{"start": 0.0, "end": 1.0}, {"start": 1.2, "end": 2.0}, {"start": 3.0, "end": 3.5}]
        out = merge_segments(segs, 0.35)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["end"], 2.0)

    def test_merge_clamps_duration(self) -> None:
        out = merge_segments([{"start": -1.0, "end": 99.0}], 0.3, duration=10.0)
        self.assertEqual(out, [{"start": 0.0, "end": 10.0}])

    def test_merge_skips_invalid(self) -> None:
        self.assertEqual(merge_segments([{"start": 1.0, "end": 1.0}], 0.3), [])


class TestReconcile(unittest.TestCase):
    def setUp(self) -> None:
        self.text = "bom dia a todos os presentes"
        self.words = [
            ("bom", 0.0, 0.3), ("dia", 0.3, 0.6), ("a", 0.6, 0.7),
            ("todos", 0.7, 1.0), ("os", 1.0, 1.1), ("presentes", 1.1, 1.6),
        ]
        self.segments = [{"start": 0.0, "end": 0.65}, {"start": 0.65, "end": 1.7}]

    def test_preserves_all_words_once(self) -> None:
        out = reconcile(self.text, self.segments, self.words)
        joined = " ".join(s["text"] for s in out).split()
        self.assertEqual(joined, self.text.split())
        self.assertEqual(len(joined), len(set(joined)) + joined.count("a") - 1)

    def test_no_invented_words(self) -> None:
        out = reconcile(self.text, self.segments, self.words)
        allowed = set(self.text.split())
        for seg in out:
            for w in seg["text"].split():
                self.assertIn(w, allowed)

    def test_boundaries_preserved(self) -> None:
        out = reconcile(self.text, self.segments, self.words)
        self.assertEqual([(s["start"], s["end"]) for s in out],
                         [(0.0, 0.65), (0.65, 1.7)])

    def test_no_segments_single_block(self) -> None:
        out = reconcile(self.text, [], self.words)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], self.text)

    def test_missing_words_raises(self) -> None:
        with self.assertRaises(ValueError):
            reconcile(self.text, self.segments, [])

    def test_srt_valid(self) -> None:
        out = reconcile(self.text, self.segments, self.words)
        srt = to_srt([TsSegment(s["start"], s["end"], s["text"]) for s in out], 1.7)
        self.assertTrue(validate_srt(srt)["valid"])

    def test_token_times_monotonic(self) -> None:
        tw = token_times(self.text, self.words)
        starts = [w["start"] for w in tw]
        self.assertEqual(starts, sorted(starts))


if __name__ == "__main__":
    unittest.main()


class TestEdgeCases(unittest.TestCase):
    def test_srt_clamps_beyond_duration(self) -> None:
        srt = to_srt([TsSegment(0.0, 5.0, "texto")], duration=3.0)
        self.assertTrue(validate_srt(srt)["valid"])

    def test_short_audio_reconcile(self) -> None:
        words = [("oi", 0.0, 0.15), ("tudo", 0.15, 0.35)]
        out = reconcile("oi tudo", [{"start": 0.0, "end": 0.4}], words)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "oi tudo")

    def test_long_audio_multiple_segments(self) -> None:
        words = [(f"p{i}", float(i), float(i) + 0.5) for i in range(40)]
        text = " ".join(w[0] for w in words)
        segs = [{"start": float(i * 5), "end": float(i * 5 + 5)} for i in range(4)]
        out = reconcile(text, segs, words)
        self.assertEqual(" ".join(s["text"] for s in out).split(), text.split())
        self.assertEqual(len(out), 4)
