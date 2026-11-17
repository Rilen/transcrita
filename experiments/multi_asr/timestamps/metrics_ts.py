"""Métricas temporais: validade, cobertura, fragmentação, fronteiras e integridade textual."""

from __future__ import annotations

import statistics

from ..benchmark.metrics import normalize_text


def validity(segments: list[dict], duration: float) -> dict:
    bad = 0
    prev_end = -1.0
    for s in segments:
        if s["start"] < -1e-6 or s["end"] <= s["start"] or s["end"] > duration + 0.05:
            bad += 1
        if s["start"] < prev_end - 1e-6:
            bad += 1
        prev_end = s["end"]
    return {"invalid_segments": bad, "valid": bad == 0}


def coverage(segments: list[dict], duration: float) -> dict:
    covered = sum(max(0.0, s["end"] - s["start"]) for s in segments)
    return {"covered_s": covered, "coverage": (covered / duration) if duration else 0.0}


def fragmentation(segments: list[dict], duration: float) -> dict:
    lens = [s["end"] - s["start"] for s in segments if s["end"] > s["start"]]
    return {
        "n_segments": len(segments),
        "per_minute": (len(segments) / (duration / 60.0)) if duration else 0.0,
        "median_len_s": statistics.median(lens) if lens else 0.0,
        "min_len_s": min(lens) if lens else 0.0,
    }


def text_integrity(full_text: str, segments: list[dict]) -> dict:
    """Diferença entre texto segmentado e texto integral (perda silenciosa)."""
    import jiwer

    joined = " ".join(s.get("text", "") for s in segments)
    ref = normalize_text(full_text)
    hyp = normalize_text(joined)
    if not ref:
        return {"wer_vs_full": 0.0, "chars_lost": 0}
    return {
        "wer_vs_full": float(jiwer.wer(ref, hyp)),
        "chars_lost": max(0, len(ref) - len(hyp)),
    }


def boundary_error(predicted: list[dict], reference: list[dict], tol: float = 0.25) -> dict:
    """Erro de fronteiras contra referência controlada (início/fim por segmento)."""
    pred_starts = [s["start"] for s in predicted]
    ref_starts = [s["start"] for s in reference]
    matched, errors = 0, []
    used = set()
    for rs in ref_starts:
        best, best_i = None, None
        for i, ps in enumerate(pred_starts):
            if i in used:
                continue
            d = abs(ps - rs)
            if best is None or d < best:
                best, best_i = d, i
        if best is not None and best <= tol:
            matched += 1
            used.add(best_i)
            errors.append(best)
    return {
        "ref_segments": len(reference),
        "pred_segments": len(predicted),
        "matched_within_tol": matched,
        "recall": (matched / len(reference)) if reference else 0.0,
        "mae_matched_s": (statistics.fmean(errors) if errors else None),
        "tol_s": tol,
    }
