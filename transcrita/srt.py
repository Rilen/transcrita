"""Geração de legendas no formato SRT a partir de segmentos de transcrição."""

from __future__ import annotations

from typing import Sequence

from transcrita.core import Segment


def format_timestamp(seconds: float) -> str:
    """Converte segundos no formato HH:MM:SS,mmm usado por SRT."""
    millis = int(round(seconds * 1000))
    hours = millis // 3_600_000
    millis %= 3_600_000
    minutes = millis // 60_000
    millis %= 60_000
    secs = millis // 1000
    millis %= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def to_srt(segments: Sequence[Segment]) -> str:
    """Renderiza uma lista de segmentos como string no formato SRT."""
    lines: list[str] = []
    for index, segment in enumerate(segments, start=1):
        lines.append(str(index))
        lines.append(f"{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}")
        lines.append(segment.text.strip())
        lines.append("")
    return "\n".join(lines)
