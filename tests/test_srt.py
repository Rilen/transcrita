"""Testes unitários para o módulo srt."""

from __future__ import annotations

import unittest

from transcrita.core import Segment
from transcrita.srt import format_timestamp, to_srt


class TestSrt(unittest.TestCase):
    def test_format_timestamp(self) -> None:
        self.assertEqual(format_timestamp(0), "00:00:00,000")
        self.assertEqual(format_timestamp(1.5), "00:00:01,500")
        self.assertEqual(format_timestamp(65.123), "00:01:05,123")
        self.assertEqual(format_timestamp(3661.999), "01:01:01,999")
        self.assertEqual(format_timestamp(3600.0), "01:00:00,000")

    def test_to_srt(self) -> None:
        segments = [
            Segment(start=0.0, end=2.5, text="Olá mundo  "),
            Segment(start=3.0, end=5.5, text="Teste de transcrição"),
        ]
        expected = (
            "1\n00:00:00,000 --> 00:00:02,500\nOlá mundo\n\n"
            "2\n00:00:03,000 --> 00:00:05,500\nTeste de transcrição\n"
        )
        self.assertEqual(to_srt(segments), expected)

    def test_to_srt_empty(self) -> None:
        self.assertEqual(to_srt([]), "")
