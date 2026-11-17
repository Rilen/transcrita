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


_NUMERIC = re.compile(r"\b\d+(?:[.,]\d+)*\b")


def error_breakdown(reference: str, hypothesis: str) -> dict[str, float]:
    """Substituições, deleções e inserções (contagens absolutas e por palavra)."""
    import jiwer

    ref = normalize_text(reference)
    hyp = normalize_text(hypothesis)
    if not ref:
        return {"substitutions": 0.0, "deletions": 0.0, "insertions": 0.0, "hits": 0.0}
    out = jiwer.process_words(ref, hyp)
    return {
        "substitutions": float(out.substitutions),
        "deletions": float(out.deletions),
        "insertions": float(out.insertions),
        "hits": float(out.hits),
    }


def numeric_tokens(text: str) -> list[str]:
    """Tokens numéricos normalizados (vírgula decimal convertida para ponto)."""
    return [t.replace(",", ".") for t in _NUMERIC.findall(text or "")]


def numeric_accuracy(references: list[str], hypotheses: list[str]) -> dict[str, float]:
    """Cobertura exata de números da referência e números espúrios na hipótese."""
    ref_all: list[str] = []
    hyp_all: list[str] = []
    ref_n = hyp_n = 0
    for ref, hyp in zip(references, hypotheses):
        refs = numeric_tokens(ref)
        hyps = numeric_tokens(hyp)
        ref_all.extend(refs)
        hyp_all.extend(hyps)
        ref_n += len(refs)
        hyp_n += len(hyps)
    from collections import Counter

    ref_c, hyp_c = Counter(ref_all), Counter(hyp_all)
    matched = sum(min(v, hyp_c.get(k, 0)) for k, v in ref_c.items())
    spurious = hyp_n - matched
    return {
        "ref_numbers": float(ref_n),
        "hyp_numbers": float(hyp_n),
        "matched": float(matched),
        "recall": (matched / ref_n) if ref_n else 0.0,
        "spurious": float(spurious),
    }


def rare_token_recall(references: list[str], hypotheses: list[str], max_freq: int = 1) -> dict[str, float]:
    """Recall de tokens raros do corpus (frequência <= max_freq nas referências)."""
    from collections import Counter

    ref_tokens = [t for r in references for t in normalize_text(r).split()]
    freq = Counter(ref_tokens)
    rare = {t for t, c in freq.items() if c <= max_freq and len(t) >= 4}
    if not rare:
        return {"rare_tokens": 0.0, "rare_recall": 0.0}
    hyp_tokens = {t for h in hypotheses for t in normalize_text(h).split()}
    hit = len(rare & hyp_tokens)
    return {"rare_tokens": float(len(rare)), "rare_recall": hit / len(rare)}


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
