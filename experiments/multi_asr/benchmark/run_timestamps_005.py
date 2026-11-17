"""Runner 005: estratégias de timestamps (A: VAD+Parakeet; C: híbrido estimado)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ..adapters import ADAPTERS
from ..benchmark.metrics import error_rates
from ..timestamps.audio import load_mono16k
from ..timestamps.hybrid import align_estimated, whisper_word_times
from ..timestamps.metrics_ts import (
    boundary_error, coverage, fragmentation, text_integrity, validity,
)
from ..timestamps.srt import TsSegment, to_srt, validate_srt
from ..timestamps.vad_parakeet import detect_segments, transcribe_segmented


def _srt_metrics(segments: list[dict], duration: float, full_text: str) -> dict:
    srt = to_srt([TsSegment(s["start"], s["end"], s["text"]) for s in segments], duration)
    check = validate_srt(srt)
    return {
        "srt": srt,
        "srt_valid": check["valid"],
        "srt_reason": check["reason"],
        "srt_blocks": check.get("blocks", 0),
        "validity": validity(segments, duration),
        "coverage": coverage(segments, duration),
        "fragmentation": fragmentation(segments, duration),
        "integrity": text_integrity(full_text, segments),
    }


def run(args) -> dict:
    configs = json.loads(Path(args.configs).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    items = manifest["items"]
    controlled = manifest.get("controlled")

    parakeet = ADAPTERS[configs[args.parakeet]["type"]]()
    parakeet.load(configs[args.parakeet])
    whisper = ADAPTERS[configs[args.whisper]["type"]]()
    whisper.load(configs[args.whisper])

    per_item: list[dict] = []
    totals = {"audio_s": 0.0, "a_proc_s": 0.0, "c_proc_s": 0.0, "p_proc_s": 0.0, "w_proc_s": 0.0}

    for item in items:
        path = item["path"]
        duration = float(item["duration"])
        audio, sr = load_mono16k(path)

        t0 = time.perf_counter()
        pk_text = parakeet.transcribe(path, language="pt").text
        pk_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        w_text = whisper.transcribe(path, language="pt").text
        w_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        segs = detect_segments(
            audio,
            threshold=args.vad_threshold,
            min_silence_ms=args.vad_min_silence,
            min_speech_ms=args.vad_min_speech,
            max_speech_s=args.vad_max_speech,
            pad_ms=args.vad_pad,
        )
        a_segments = transcribe_segmented(parakeet._model, audio, segs, language="pt")
        a_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        words = whisper_word_times(whisper._model, path, language="pt")
        c_segments = align_estimated(pk_text, words, max_segment_s=args.hybrid_max,
                                     pause_s=args.hybrid_pause)
        c_time = time.perf_counter() - t0

        a_m = _srt_metrics(a_segments, duration, pk_text)
        c_m = _srt_metrics(c_segments, duration, pk_text)
        totals["audio_s"] += duration
        totals["a_proc_s"] += a_time
        totals["c_proc_s"] += c_time
        totals["p_proc_s"] += pk_time
        totals["w_proc_s"] += w_time

        per_item.append({
            "id": item["id"], "scenario": item["scenario"], "duration": duration,
            "pk_wer": error_rates(item["reference"], pk_text)["wer"],
            "w_wer": error_rates(item["reference"], w_text)["wer"],
            "pk_time": pk_time, "w_time": w_time,
            "a": {k: v for k, v in a_m.items() if k != "srt"},
            "c": {k: v for k, v in c_m.items() if k != "srt"},
            "a_time": a_time, "c_time": c_time,
            "a_segments": len(a_segments), "c_segments": len(c_segments),
        })
        if len(per_item) == 1:
            Path(args.srt_dir).mkdir(parents=True, exist_ok=True)
            Path(args.srt_dir, "sample_A_vad.srt").write_text(a_m["srt"], encoding="utf-8")
            Path(args.srt_dir, "sample_C_hybrid.srt").write_text(c_m["srt"], encoding="utf-8")

    ctrl = None
    if controlled:
        path = controlled["path"]
        audio, _ = load_mono16k(path)
        refs = controlled["reference_segments"]
        ref_text = controlled["reference_text"]
        duration = float(controlled["duration"])
        pk_controlled = parakeet.transcribe(path, language="pt").text

        segs = detect_segments(audio, threshold=args.vad_threshold,
                               min_silence_ms=args.vad_min_silence,
                               min_speech_ms=args.vad_min_speech,
                               max_speech_s=args.vad_max_speech, pad_ms=args.vad_pad)
        a_segments = transcribe_segmented(parakeet._model, audio, segs, language="pt")
        words = whisper_word_times(whisper._model, path, language="pt")
        c_segments = align_estimated(pk_controlled, words, max_segment_s=args.hybrid_max,
                                     pause_s=args.hybrid_pause)
        ctrl = {
            "duration": duration,
            "reference_segments": len(refs),
            "a": {
                "boundary_025": boundary_error(a_segments, refs, 0.25),
                "boundary_050": boundary_error(a_segments, refs, 0.5),
                "coverage": coverage(a_segments, duration),
                "fragmentation": fragmentation(a_segments, duration),
                "integrity": text_integrity(ref_text, a_segments),
                "validity": validity(a_segments, duration),
            },
            "c": {
                "boundary_025": boundary_error(c_segments, refs, 0.25),
                "boundary_050": boundary_error(c_segments, refs, 0.5),
                "coverage": coverage(c_segments, duration),
                "fragmentation": fragmentation(c_segments, duration),
                "integrity": text_integrity(ref_text, c_segments),
                "validity": validity(c_segments, duration),
            },
        }

    payload = {
        "params": {
            "vad": {"threshold": args.vad_threshold, "min_silence_ms": args.vad_min_silence,
                    "min_speech_ms": args.vad_min_speech, "max_speech_s": args.vad_max_speech,
                    "pad_ms": args.vad_pad},
            "hybrid": {"max_segment_s": args.hybrid_max, "pause_s": args.hybrid_pause},
            "models": {"parakeet": args.parakeet, "whisper": args.whisper},
        },
        "items": per_item,
        "controlled": ctrl,
        "totals": {
            **totals,
            "pk_rtf": totals["p_proc_s"] / totals["audio_s"] if totals["audio_s"] else 0.0,
            "w_rtf": totals["w_proc_s"] / totals["audio_s"] if totals["audio_s"] else 0.0,
            "a_rtf": totals["a_proc_s"] / totals["audio_s"] if totals["audio_s"] else 0.0,
            "c_rtf": totals["c_proc_s"] / totals["audio_s"] if totals["audio_s"] else 0.0,
        },
        "summary": {
            "pk_wer_mean": sum(i["pk_wer"] for i in per_item) / max(len(per_item), 1),
            "w_wer_mean": sum(i["w_wer"] for i in per_item) / max(len(per_item), 1),
            "a_valid_rate": sum(1 for i in per_item if i["a"]["srt_valid"]) / max(len(per_item), 1),
            "c_valid_rate": sum(1 for i in per_item if i["c"]["srt_valid"]) / max(len(per_item), 1),
            "a_integrity_wer": sum(i["a"]["integrity"]["wer_vs_full"] for i in per_item) / max(len(per_item), 1),
            "c_integrity_wer": sum(i["c"]["integrity"]["wer_vs_full"] for i in per_item) / max(len(per_item), 1),
            "a_coverage_mean": sum(i["a"]["coverage"]["coverage"] for i in per_item) / max(len(per_item), 1),
            "c_coverage_mean": sum(i["c"]["coverage"]["coverage"] for i in per_item) / max(len(per_item), 1),
        },
    }
    parakeet.unload()
    whisper.unload()
    return payload


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--configs", default="experiments/multi_asr/configs/models.json")
    p.add_argument("--manifest", default="/var/lib/transcrita-poc/corpus005/manifest.json")
    p.add_argument("--parakeet", default="parakeet-ptbr-tagarela-int8")
    p.add_argument("--whisper", default="whisper-large-v3-turbo")
    p.add_argument("--vad-threshold", type=float, default=0.5)
    p.add_argument("--vad-min-silence", type=int, default=400)
    p.add_argument("--vad-min-speech", type=int, default=250)
    p.add_argument("--vad-max-speech", type=float, default=25.0)
    p.add_argument("--vad-pad", type=int, default=100)
    p.add_argument("--hybrid-max", type=float, default=12.0)
    p.add_argument("--hybrid-pause", type=float, default=1.0)
    p.add_argument("--srt-dir", default="/var/lib/transcrita-poc/results005/srt")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    payload = run(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    s, t = payload["summary"], payload["totals"]
    print(f"PK WER={s['pk_wer_mean']:.4f} W WER={s['w_wer_mean']:.4f} | "
          f"A valid={s['a_valid_rate']:.2f} cov={s['a_coverage_mean']:.2f} integ={s['a_integrity_wer']:.4f} rtf={t['a_rtf']:.3f} | "
          f"C valid={s['c_valid_rate']:.2f} cov={s['c_coverage_mean']:.2f} integ={s['c_integrity_wer']:.4f} rtf={t['c_rtf']:.3f}")


if __name__ == "__main__":
    main()
