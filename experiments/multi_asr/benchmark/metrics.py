"""Normalização de texto e métricas WER/CER (jiwer)."""

from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)


def normalize_text(text: str) -> str:
    """Minúsculas, sem pontuação, espaços colapsados; acentos preservados."""
    text = unicodedata.normalize("NFC", text or "").lower()
    text = _PUNCT.sub(" ", text)
    return " ".join(text.split())


def error_rates(reference: str, hypothesis: str) -> dict[str, float]:
    """WER, CER e contagem de palavras da referência (após normalização)."""
    import jiwer

    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    ref_words = max(len(ref.split()), 1)
    if not hyp:
        return {"wer": 1.0, "cer": 1.0 if ref else 0.0, "ref_words": float(ref_words)}
    return {
        "wer": float(jiwer.wer(ref, hyp)),
        "cer": float(jiwer.cer(ref, hyp)),
        "ref_words": float(ref_words),
    }


def aggregate(results: list[dict]) -> dict[str, float]:
    """Agrega métricas ponderando WER/CER por palavras de referência."""
    ok = [r for r in results if r.get("status") == "ok" and r.get("ref_words")]
    total_words = sum(r["ref_words"] for r in ok) or 1.0
    total_audio = sum(r.get("audio_duration", 0.0) for r in ok) or 0.0
    total_proc = sum(r.get("processing_time", 0.0) for r in ok)
    return {
        "clips_ok": float(len(ok)),
        "clips_total": float(len(results)),
        "wer": sum(r["wer"] * r["ref_words"] for r in ok) / total_words,
        "cer": sum(r["cer"] * r["ref_words"] for r in ok) / total_words,
        "audio_seconds": total_audio,
        "proc_seconds": total_proc,
        "rtf": (total_proc / total_audio) if total_audio else 0.0,
    }
