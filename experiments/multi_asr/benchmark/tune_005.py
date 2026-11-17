"""Ciclo de ajuste 005: varre configurações de VAD e do híbrido no conjunto controlado."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..adapters import ADAPTERS
from ..timestamps.audio import load_mono16k
from ..timestamps.hybrid import align_estimated, whisper_word_times
from ..timestamps.metrics_ts import boundary_error, coverage, fragmentation, text_integrity, validity
from ..timestamps.srt import TsSegment, to_srt, validate_srt
from ..timestamps.vad_parakeet import detect_segments, transcribe_segmented


def _speech_onsets(refs: list[dict], silence_s: float = 1.0) -> list[dict]:
    out = []
    for i, r in enumerate(refs):
        off = 0.0 if i == 0 else silence_s
        out.append({"start": r["start"] + off, "end": r["end"]})
    return out


def _metrics(segments: list[dict], duration: float, ref_text: str) -> dict:
    srt = to_srt([TsSegment(s["start"], s["end"], s["text"]) for s in segments], duration)
    return {
        "n": len(segments),
        "valid": validate_srt(srt)["valid"],
        "coverage": coverage(segments, duration)["coverage"],
        "frag_per_min": fragmentation(segments, duration)["per_minute"],
        "median_len": fragmentation(segments, duration)["median_len_s"],
        "integrity_wer": text_integrity(ref_text, segments)["wer_vs_full"],
        "ts_valid": validity(segments, duration)["valid"],
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--configs", default="experiments/multi_asr/configs/models.json")
    p.add_argument("--manifest", default="/var/lib/transcrita-poc/corpus005/manifest.json")
    p.add_argument("--out", default="/var/lib/transcrita-poc/results005/tuning.json")
    args = p.parse_args(argv)

    cfg = json.loads(Path(args.configs).read_text(encoding="utf-8"))
    man = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    ctrl = man["controlled"]
    path, dur, refs, ref_text = ctrl["path"], ctrl["duration"], ctrl["reference_segments"], ctrl["reference_text"]
    onsets = _speech_onsets(refs)

    pk = ADAPTERS[cfg["parakeet-ptbr-tagarela-int8"]["type"]](); pk.load(cfg["parakeet-ptbr-tagarela-int8"])
    wh = ADAPTERS[cfg["whisper-large-v3-turbo"]["type"]](); wh.load(cfg["whisper-large-v3-turbo"])

    audio, _ = load_mono16k(path)
    pk_text = pk.transcribe(path, language="pt").text
    words = whisper_word_times(wh._model, path, language="pt")

    vad_cfgs = [
        {"threshold": 0.50, "min_silence_ms": 400, "min_speech_ms": 250, "pad_ms": 100, "max_speech_s": 25.0},
        {"threshold": 0.35, "min_silence_ms": 500, "min_speech_ms": 200, "pad_ms": 300, "max_speech_s": 25.0},
        {"threshold": 0.30, "min_silence_ms": 600, "min_speech_ms": 200, "pad_ms": 400, "max_speech_s": 20.0},
        {"threshold": 0.35, "min_silence_ms": 500, "min_speech_ms": 200, "pad_ms": 150, "max_speech_s": 25.0},
        {"threshold": 0.40, "min_silence_ms": 450, "min_speech_ms": 200, "pad_ms": 150, "max_speech_s": 25.0},
    ]
    results = {"vad": [], "hybrid": [], "reference": {"silence_starts": refs, "speech_onsets": onsets}}
    for vc in vad_cfgs:
        segs = detect_segments(audio, **{k: vc[k] for k in ("threshold", "min_silence_ms", "min_speech_ms", "pad_ms", "max_speech_s")})
        seg_text = transcribe_segmented(pk._model, audio, segs, language="pt")
        results["vad"].append({
            "cfg": vc,
            **_metrics(seg_text, dur, pk_text),
            "boundary_silence": boundary_error(seg_text, refs, 0.25),
            "boundary_onset": boundary_error(seg_text, onsets, 0.25),
        })

    for hc in ({"pause": 1.0, "max": 12.0}, {"pause": 0.7, "max": 10.0}, {"pause": 1.4, "max": 15.0}):
        segs = align_estimated(pk_text, words, max_segment_s=hc["max"], pause_s=hc["pause"])
        results["hybrid"].append({
            "cfg": hc,
            **_metrics(segs, dur, pk_text),
            "boundary_silence": boundary_error(segs, refs, 0.25),
            "boundary_onset": boundary_error(segs, onsets, 0.25),
        })

    pk.unload(); wh.unload()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    for row in results["vad"]:
        b = row["boundary_onset"]
        print(f"VAD {row['cfg']['threshold']}/{row['cfg']['pad_ms']}ms: cov={row['coverage']:.2f} "
              f"integ={row['integrity_wer']:.3f} frag/min={row['frag_per_min']:.1f} "
              f"onset_recall={b['recall']:.2f} mae={b['mae_matched_s']}")
    for row in results["hybrid"]:
        b = row["boundary_onset"]
        print(f"HYB pause={row['cfg']['pause']} max={row['cfg']['max']}: cov={row['coverage']:.2f} "
              f"frag/min={row['frag_per_min']:.1f} onset_recall={b['recall']:.2f} mae={b['mae_matched_s']}")


if __name__ == "__main__":
    main()
