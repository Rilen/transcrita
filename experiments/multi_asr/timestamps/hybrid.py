"""Estratégia C: texto do Parakeet + tempos de palavra do Whisper (estimados).

Os tempos são ESTIMADOS por alinhamento de sequência (difflib). Não é
alinhamento forçado por palavra e não deve ser apresentado como preciso.
"""

from __future__ import annotations

import difflib
import re

from ..benchmark.metrics import normalize_text
from .audio import load_mono16k

_WORD = re.compile(r"\S+")


def whisper_word_times(model, audio_path: str, language: str = "pt") -> list[tuple[str, float, float]]:
    audio, _sr = load_mono16k(audio_path)
    segments, _info = model.transcribe(
        audio, language=language, beam_size=5,
        vad_filter=False, word_timestamps=True,
    )
    words: list[tuple[str, float, float]] = []
    for seg in segments:
        for w in getattr(seg, "words", []) or []:
            token = (w.word or "").strip()
            if token:
                words.append((token, float(w.start), float(w.end)))
    return words


def _flatten(orig_words: list[str]) -> tuple[list[str], list[int]]:
    toks: list[str] = []
    owner: list[int] = []
    for i, w in enumerate(orig_words):
        norm = normalize_text(w)
        if not norm:
            continue
        for part in norm.split():
            toks.append(part)
            owner.append(i)
    return toks, owner


def align_estimated(parakeet_text: str, words: list[tuple[str, float, float]],
                    max_segment_s: float = 12.0, pause_s: float = 1.0) -> list[dict]:
    orig = _WORD.findall(parakeet_text or "")
    pk_tokens, pk_owner = _flatten(orig)
    if not pk_tokens or not words:
        return []

    w_orig = [w[0] for w in words]
    w_tokens, w_owner = _flatten(w_orig)

    times: list[tuple[float, float] | None] = [None] * len(pk_tokens)
    matcher = difflib.SequenceMatcher(a=pk_tokens, b=w_tokens, autojunk=False)
    for a0, b0, size in matcher.get_matching_blocks():
        for k in range(size):
            wi = w_owner[b0 + k]
            times[a0 + k] = (words[wi][1], words[wi][2])

    known = [i for i, t in enumerate(times) if t is not None]
    if not known:
        return []
    for i in range(len(times)):
        if times[i] is not None:
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        if prev is not None and nxt is not None:
            t0, t1 = times[prev], times[nxt]
            frac = (i - prev) / (nxt - prev)
            times[i] = (t0[1] + frac * max(0.0, t1[0] - t0[1]), t1[0])
        elif prev is not None:
            times[i] = (times[prev][1], times[prev][1] + 0.2)
        else:
            times[i] = (max(0.0, times[nxt][0] - 0.2), times[nxt][0])  # type: ignore[index]

    segments: list[dict] = []
    cur: list[int] = []
    for i in range(len(pk_tokens)):
        t = times[i]
        if t is None:
            continue
        if cur:
            gap = t[0] - (times[cur[-1]][1] if times[cur[-1]] else t[0])
            span = t[1] - (times[cur[0]][0] if times[cur[0]] else t[0])
            if gap > pause_s or span > max_segment_s:
                segments.append(_segment(orig, pk_owner, cur, times))
                cur = []
        cur.append(i)
    if cur:
        segments.append(_segment(orig, pk_owner, cur, times))
    return [s for s in segments if s["end"] > s["start"] and s["text"]]


def _segment(orig: list[str], owner: list[int], idxs: list[int],
             times: list[tuple[float, float] | None]) -> dict:
    tt = [times[i] for i in idxs if times[i] is not None]
    start = min(t[0] for t in tt)
    end = max(t[1] for t in tt)
    words_idx: list[int] = []
    for i in idxs:
        oi = owner[i]
        if not words_idx or words_idx[-1] != oi:
            words_idx.append(oi)
    text = " ".join(orig[i] for i in words_idx)
    return {"start": start, "end": end, "text": text, "estimated": True}
