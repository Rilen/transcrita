"""Missão 006: diagnóstico da perda textual e comparação de estratégias de integridade."""

from __future__ import annotations

import argparse
import difflib
import json
import threading
import time
from pathlib import Path

import psutil

from ..adapters import ADAPTERS
from ..benchmark.metrics import error_rates, normalize_text
from ..timestamps.audio import load_mono16k
from ..timestamps.hybrid import whisper_word_times
from ..timestamps.metrics_ts import (
    boundary_error, coverage, fragmentation, text_integrity, validity,
)
from ..timestamps.reconcile import reconcile
from ..timestamps.srt import TsSegment, to_srt, validate_srt
from ..timestamps.vad_parakeet import detect_segments, transcribe_segmented


class RssSampler:
    def __init__(self) -> None:
        self.peak = 0.0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        proc = psutil.Process()
        while not self._stop.is_set():
            self.peak = max(self.peak, proc.memory_info().rss / (1024 * 1024))
            self._stop.wait(0.05)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join(timeout=2)
        return False


def _tokens(text: str) -> list[str]:
    return normalize_text(text).split()


def _captured(ref: list[str], hyp: list[str]) -> set[int]:
    """Índices de referência capturados (casados) pela hipótese."""
    got: set[int] = set()
    m = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    for a0, _b0, size in m.get_matching_blocks():
        got.update(range(a0, a0 + size))
    return got


def _diff_counts(src: str, dst: str) -> dict:
    m = difflib.SequenceMatcher(a=_tokens(src), b=_tokens(dst), autojunk=False)
    s = d = i = 0
    for tag, i1, i2, j1, j2 in m.get_opcodes():
        if tag == "replace":
            s += max(i2 - i1, j2 - j1)
        elif tag == "delete":
            d += i2 - i1
        elif tag == "insert":
            i += j2 - j1
    return {"substitutions": s, "deletions": d, "insertions": i}


def _dup_bigrams(text: str) -> int:
    t = _tokens(text)
    return sum(1 for a, b in zip(t, t[1:]) if a == b)


def _srt_block(segments: list[dict], duration: float, ref_text: str) -> dict:
    srt = to_srt([TsSegment(s["start"], s["end"], s["text"]) for s in segments], duration)
    check = validate_srt(srt)
    return {
        "srt_valid": check["valid"], "srt_reason": check["reason"],
        "validity": validity(segments, duration),
        "coverage": coverage(segments, duration),
        "fragmentation": fragmentation(segments, duration),
        "integrity": text_integrity(ref_text, segments),
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--configs", default="experiments/multi_asr/configs/models.json")
    p.add_argument("--manifest", default="/var/lib/transcrita-poc/corpus005/manifest.json")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)

    cfg = json.loads(Path(args.configs).read_text(encoding="utf-8"))
    man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    items = man["items"]
    ctrl = man["controlled"]

    pk = ADAPTERS[cfg["parakeet-ptbr-tagarela-int8"]["type"]](); pk.load(cfg["parakeet-ptbr-tagarela-int8"])
    wh = ADAPTERS[cfg["whisper-large-v3-turbo"]["type"]](); wh.load(cfg["whisper-large-v3-turbo"])

    A005 = dict(threshold=0.35, min_silence_ms=500, min_speech_ms=200, pad_ms=150,
                max_speech_s=25.0, merge_gap_s=0.0)
    A2 = dict(threshold=0.30, min_silence_ms=550, min_speech_ms=150, pad_ms=250,
              max_speech_s=25.0, merge_gap_s=0.35)

    out_items: list[dict] = []
    totals = {"audio_s": 0.0, "full_s": 0.0, "a005_s": 0.0, "a2_s": 0.0, "rec_s": 0.0}
    rss = {"full": 0.0, "a005": 0.0, "a2": 0.0, "rec": 0.0}

    for item in items:
        path, dur, ref = item["path"], float(item["duration"]), item["reference"]
        audio, _ = load_mono16k(path)

        with RssSampler() as rs:
            t0 = time.perf_counter()
            full_text = pk.transcribe(path, language="pt").text
            totals["full_s"] += time.perf_counter() - t0
        rss["full"] = max(rss["full"], rs.peak)

        def seg_text(params: dict) -> tuple[list[dict], float, float]:
            with RssSampler() as rsx:
                t0 = time.perf_counter()
                segs = detect_segments(audio, **params)
                segs_out = transcribe_segmented(pk._model, audio, segs, language="pt")
                elapsed = time.perf_counter() - t0
            return segs_out, elapsed, rsx.peak

        a005_segs, a005_t, a005_rss = seg_text(A005)
        a2_segs, a2_t, a2_rss = seg_text(A2)
        totals["a005_s"] += a005_t
        totals["a2_s"] += a2_t
        rss["a005"] = max(rss["a005"], a005_rss)
        rss["a2"] = max(rss["a2"], a2_rss)

        with RssSampler() as rs2:
            t0 = time.perf_counter()
            words = whisper_word_times(wh._model, path, language="pt")
            try:
                rec_segs = reconcile(full_text, a2_segs, words)
                rec_status = "ok"
            except Exception as exc:  # noqa: BLE001
                rec_segs, rec_status = [], f"error: {exc}"
            totals["rec_s"] += time.perf_counter() - t0
        rss["rec"] = max(rss["rec"], rs2.peak)

        a005_text = " ".join(s["text"] for s in a005_segs)
        a2_text = " ".join(s["text"] for s in a2_segs)
        rec_text = " ".join(s["text"] for s in rec_segs)

        ref_tok = _tokens(ref)
        cap_full = _captured(ref_tok, _tokens(full_text))
        cap_a005 = _captured(ref_tok, _tokens(a005_text))
        cap_a2 = _captured(ref_tok, _tokens(a2_text))

        sensitive = detect_segments(audio, threshold=0.20, min_silence_ms=200,
                                    min_speech_ms=100, pad_ms=0, max_speech_s=30.0)
        sensitive_s = sum(s["end"] - s["start"] for s in sensitive) or 1e-9

        w005 = error_rates(ref, a005_text)
        w2 = error_rates(ref, a2_text)
        wf = error_rates(ref, full_text)

        out_items.append({
            "id": item["id"], "scenario": item["scenario"], "duration": dur,
            "wer": {"full": wf["wer"], "a005": w005["wer"], "a2": w2["wer"],
                    "reconciled": wf["wer"] if rec_status == "ok" else None},
            "cer": {"full": wf["cer"], "a005": w005["cer"], "a2": w2["cer"],
                    "reconciled": wf["cer"] if rec_status == "ok" else None},
            "integrity": {
                "a005": text_integrity(full_text, a005_segs)["wer_vs_full"],
                "a2": text_integrity(full_text, a2_segs)["wer_vs_full"],
                "reconciled": text_integrity(full_text, rec_segs)["wer_vs_full"] if rec_status == "ok" else None,
            },
            "diff_vs_full": {"a005": _diff_counts(full_text, a005_text),
                             "a2": _diff_counts(full_text, a2_text)},
            "effective_loss": {
                "ref_tokens": len(ref_tok),
                "lost_a005": len(cap_full - cap_a005),
                "lost_a2": len(cap_full - cap_a2),
                "gained_a2": len(cap_a2 - cap_full),
            },
            "dups": {"full": _dup_bigrams(full_text), "a2": _dup_bigrams(a2_text)},
            "uncovered_speech_proxy": max(0.0, 1.0 - sum(s["end"] - s["start"] for s in a2_segs) / sensitive_s),
            "blocks": {
                "a005": _srt_block(a005_segs, dur, full_text),
                "a2": _srt_block(a2_segs, dur, full_text),
                "reconciled": _srt_block(rec_segs, dur, full_text) if rec_status == "ok" else {"srt_valid": False},
            },
            "reconciled_status": rec_status,
            "times": {"full": 0.0, "a005": a005_t, "a2": a2_t},
        })
        totals["audio_s"] += dur

    # controlado
    cpath, cdur, cref = ctrl["path"], float(ctrl["duration"]), ctrl["reference_segments"]
    caudio, _ = load_mono16k(cpath)
    c_full = pk.transcribe(cpath, language="pt").text
    c_words = whisper_word_times(wh._model, cpath, language="pt")
    ctrl_out = {"duration": cdur, "reference_segments": len(cref)}
    for name, params in (("a005", A005), ("a2", A2)):
        segs = detect_segments(caudio, **params)
        segt = transcribe_segmented(pk._model, caudio, segs, language="pt")
        ctrl_out[name] = {
            "boundary_025": boundary_error(segt, cref, 0.25),
            "boundary_050": boundary_error(segt, cref, 0.5),
            "coverage": coverage(segt, cdur),
            "integrity": text_integrity(c_full, segt),
            "validity": validity(segt, cdur),
        }
        if name == "a2":
            try:
                rec = reconcile(c_full, segs, c_words)
                ctrl_out["reconciled"] = {
                    "boundary_025": boundary_error(rec, cref, 0.25),
                    "boundary_050": boundary_error(rec, cref, 0.5),
                    "coverage": coverage(rec, cdur),
                    "integrity": text_integrity(c_full, rec),
                    "validity": validity(rec, cdur),
                    "text_equal_full": " ".join(s["text"] for s in rec) == c_full.strip(),
                }
            except Exception as exc:  # noqa: BLE001
                ctrl_out["reconciled"] = {"error": str(exc)}

    pk.unload(); wh.unload()

    payload = {
        "configs": {"a005": A005, "a2": A2},
        "items": out_items,
        "controlled": ctrl_out,
        "totals": {
            **totals,
            "full_rtf": totals["full_s"] / totals["audio_s"] if totals["audio_s"] else 0.0,
            "a005_rtf": totals["a005_s"] / totals["audio_s"] if totals["audio_s"] else 0.0,
            "a2_rtf": totals["a2_s"] / totals["audio_s"] if totals["audio_s"] else 0.0,
            "rec_rtf": totals["rec_s"] / totals["audio_s"] if totals["audio_s"] else 0.0,
        },
        "rss_peak_mb": rss,
        "summary": {
            "n": len(out_items),
            "wer_full": sum(i["wer"]["full"] for i in out_items) / max(len(out_items), 1),
            "wer_a005": sum(i["wer"]["a005"] for i in out_items) / max(len(out_items), 1),
            "wer_a2": sum(i["wer"]["a2"] for i in out_items) / max(len(out_items), 1),
            "integrity_a005": sum(i["integrity"]["a005"] for i in out_items) / max(len(out_items), 1),
            "integrity_a2": sum(i["integrity"]["a2"] for i in out_items) / max(len(out_items), 1),
            "lost_ref_a005": sum(i["effective_loss"]["lost_a005"] for i in out_items),
            "lost_ref_a2": sum(i["effective_loss"]["lost_a2"] for i in out_items),
            "ref_tokens": sum(i["effective_loss"]["ref_tokens"] for i in out_items),
            "dup_full": sum(i["dups"]["full"] for i in out_items),
            "dup_a2": sum(i["dups"]["a2"] for i in out_items),
            "uncovered_speech_proxy": sum(i["uncovered_speech_proxy"] for i in out_items) / max(len(out_items), 1),
            "a2_srt_valid_rate": sum(1 for i in out_items if i["blocks"]["a2"]["srt_valid"]) / max(len(out_items), 1),
            "rec_srt_valid_rate": sum(1 for i in out_items if i["blocks"]["reconciled"].get("srt_valid")) / max(len(out_items), 1),
            "rec_ok": sum(1 for i in out_items if i["reconciled_status"] == "ok"),
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    s, t = payload["summary"], payload["totals"]
    print(f"WER full={s['wer_full']:.4f} A005={s['wer_a005']:.4f} A2={s['wer_a2']:.4f} | "
          f"integr A005={s['integrity_a005']:.4f} A2={s['integrity_a2']:.4f} | "
          f"lost_ref A005={s['lost_ref_a005']:.0f} A2={s['lost_ref_a2']:.0f}/{s['ref_tokens']} | "
          f"RTF A2={t['a2_rtf']:.3f} REC={t['rec_rtf']:.3f} | rec_ok={s['rec_ok']}/{s['n']}")


if __name__ == "__main__":
    main()
