"""Estratégia C da missão 006: segmentos VAD + texto integral reconciliado.

Regra: nenhuma palavra é inventada. O texto final é exatamente a hipótese do
passe integral do Parakeet; o alinhamento (estimado, via Whisper) apenas
distribui essas palavras entre os segmentos VAD.
"""

from __future__ import annotations

import difflib
import re

from ..benchmark.metrics import normalize_text

_WORD = re.compile(r"\S+")


def token_times(full_text: str, words: list[tuple[str, float, float]]) -> list[dict]:
    """Atribui tempo estimado a cada palavra do texto integral."""
    orig = _WORD.findall(full_text or "")
    toks: list[str] = []
    owner: list[int] = []
    for i, w in enumerate(orig):
        for part in normalize_text(w).split():
            toks.append(part)
            owner.append(i)
    if not toks or not words:
        raise ValueError("texto ou palavras de alinhamento ausentes")

    w_toks: list[str] = []
    w_owner: list[int] = []
    for i, w in enumerate(words):
        for part in normalize_text(w[0]).split():
            w_toks.append(part)
            w_owner.append(i)

    times: list[tuple[float, float] | None] = [None] * len(toks)
    matcher = difflib.SequenceMatcher(a=toks, b=w_toks, autojunk=False)
    for a0, b0, size in matcher.get_matching_blocks():
        for k in range(size):
            wi = w_owner[b0 + k]
            times[a0 + k] = (words[wi][1], words[wi][2])

    known = [i for i, t in enumerate(times) if t is not None]
    if not known:
        raise ValueError("nenhuma âncora de tempo encontrada")
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
            times[i] = (max(0.0, times[nxt][0] - 0.2), times[nxt][0])

    per_word: list[dict] = []
    seen: set[int] = set()
    for i, (tok, oi) in enumerate(zip(toks, owner)):
        if oi in seen:
            per_word[-1]["end"] = max(per_word[-1]["end"], times[i][1])
            continue
        seen.add(oi)
        per_word.append({"word": orig[oi], "start": times[i][0], "end": times[i][1]})
    return per_word


def reconcile(full_text: str, segments: list[dict],
              words: list[tuple[str, float, float]]) -> list[dict]:
    """Distribui as palavras do texto integral entre segmentos VAD, sem invenção."""
    per_word = token_times(full_text, words)
    if not segments:
        start = per_word[0]["start"]
        end = per_word[-1]["end"]
        return [{"start": start, "end": end, "text": full_text.strip()}]

    buckets: list[list[dict]] = [[] for _ in segments]
    for w in per_word:
        mid = (w["start"] + w["end"]) / 2
        idx = None
        for i, s in enumerate(segments):
            if s["start"] <= mid <= s["end"]:
                idx = i
                break
        if idx is None:
            idx = min(
                range(len(segments)),
                key=lambda i: min(abs(mid - segments[i]["start"]), abs(mid - segments[i]["end"])),
            )
        buckets[idx].append(w)

    out: list[dict] = []
    for seg, bucket in zip(segments, buckets):
        if not bucket:
            continue
        # fronteiras VAD preservadas (o texto pode se estender além do fim visual)
        out.append({"start": seg["start"], "end": seg["end"],
                    "text": " ".join(w["word"] for w in bucket)})
    return out
