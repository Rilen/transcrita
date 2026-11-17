"""Geração e validação de SRT a partir de segmentos com timestamps."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TS = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})$")


@dataclass
class TsSegment:
    start: float
    end: float
    text: str
    estimated: bool = False


def _fmt(seconds: float) -> str:
    if seconds < 0:
        raise ValueError("timestamp negativo")
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segments: list[TsSegment], duration: float | None = None) -> str:
    """Serializa segmentos em SRT, saneando ordem e limites."""
    blocks: list[str] = []
    prev_end = 0.0
    idx = 1
    for seg in segments:
        start = max(0.0, float(seg.start))
        end = float(seg.end)
        if duration is not None:
            start = min(start, duration)
            end = min(end, duration)
        if end <= start:
            continue
        start = max(start, prev_end)
        if end <= start:
            continue
        text = " ".join((seg.text or "").split())
        if not text:
            continue
        blocks.append(f"{idx}\n{_fmt(start)} --> {_fmt(end)}\n{text}\n")
        prev_end = end
        idx += 1
    return "\n".join(blocks)


def validate_srt(content: str) -> dict:
    """Valida estrutura e monotonicidade do SRT gerado."""
    blocks = [b for b in content.strip().split("\n\n") if b.strip()]
    prev_end = -1.0
    for i, block in enumerate(blocks, start=1):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            return {"valid": False, "reason": f"bloco {i} malformado"}
        m = _TS.match(lines[1].strip())
        if not m:
            return {"valid": False, "reason": f"timestamps inválidos no bloco {i}"}
        g = [int(x) for x in m.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        if end <= start:
            return {"valid": False, "reason": f"fim <= início no bloco {i}"}
        if start < prev_end - 1e-6:
            return {"valid": False, "reason": f"sobreposição/ordem no bloco {i}"}
        prev_end = end
    return {"valid": True, "blocks": len(blocks), "reason": ""}
