"""Estratégia B: alinhamento forçado com MMS_FA (torchaudio, CPU).

Requer torchaudio + torch CPU e baixa o bundle MMS_FA (licença CC-BY-NC 4.0).
Uso experimental interno; não integrar sem validação jurídica.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import torch
import torchaudio
from torchaudio.pipelines import MMS_FA

from .audio import load_mono16k


def align_words(audio_path: str, transcript: str) -> tuple[list[dict], float]:
    bundle = MMS_FA
    model = bundle.get_model()
    model.eval()
    audio, _ = load_mono16k(audio_path)
    wav = torch.from_numpy(audio).unsqueeze(0)
    start = time.perf_counter()
    with torch.inference_mode():
        emissions, _ = model(wav)
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()
    dictionary = bundle.get_dict()
    raw_words = transcript.split()
    alignable: list[tuple[int, str, str]] = []
    for i, w in enumerate(raw_words):
        core = "".join(c for c in w.lower() if c in dictionary)
        if core:
            alignable.append((i, w, core))
    tokens = tokenizer([core for _i, _w, core in alignable])
    spans = aligner(emissions[0], tokens)
    elapsed = time.perf_counter() - start
    ratio = wav.size(1) / emissions.size(1) / bundle.sample_rate
    words: list[dict] = []
    for (i, word, _core), word_spans in zip(alignable, spans):
        if not word_spans:
            continue
        words.append({
            "index": i,
            "word": word,
            "start": round(float(word_spans[0].start) * ratio, 3),
            "end": round(float(word_spans[-1].end) * ratio, 3),
        })
    return words, elapsed


def group_segments(words: list[dict], pause_s: float = 1.0, max_s: float = 12.0) -> list[dict]:
    segments: list[dict] = []
    cur: list[dict] = []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > pause_s or w["end"] - cur[0]["start"] > max_s):
            segments.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                             "text": " ".join(x["word"] for x in cur)})
            cur = []
        cur.append(w)
    if cur:
        segments.append({"start": cur[0]["start"], "end": cur[-1]["end"],
                         "text": " ".join(x["word"] for x in cur)})
    return segments
