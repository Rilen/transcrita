"""Runner isolado para Qwen3-ASR (venv própria com torch CPU).

Produz o mesmo esquema JSON de run_benchmark.py, permitindo comparação direta.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import time
from pathlib import Path

from experiments.multi_asr.benchmark.metrics import aggregate, error_rates


def _peak_rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="Qwen/Qwen3-ASR-0.6B")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=300.0, help="reservado (limite externo)")
    args = parser.parse_args(argv)

    import torch
    from qwen_asr import Qwen3ASRModel

    torch.set_num_threads(max(1, args.threads))
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    load_start = time.perf_counter()
    model = Qwen3ASRModel.from_pretrained(
        args.repo,
        dtype=torch.float32,
        device_map="cpu",
        max_inference_batch_size=1,
        max_new_tokens=512,
    )
    load_time = time.perf_counter() - load_start

    results = []
    for item in manifest:
        started = time.perf_counter()
        try:
            out = model.transcribe([item["path"]], language=None)
            elapsed = time.perf_counter() - started
            text = (out[0].text or "").strip() if out else ""
            rates = error_rates(item["reference"], text)
            duration = float(item.get("duration", 0.0))
            results.append(
                {
                    **rates,
                    "clip_id": item["id"],
                    "scenario": item["scenario"],
                    "audio_duration": duration,
                    "processing_time": elapsed,
                    "rtf": (elapsed / duration) if duration else 0.0,
                    "status": "ok",
                    "text": text[:400],
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "clip_id": item["id"],
                    "scenario": item["scenario"],
                    "status": "error",
                    "error": str(exc)[:300],
                    "wer": 1.0,
                    "cer": 1.0,
                    "ref_words": float(max(len(item["reference"].split()), 1)),
                    "audio_duration": float(item.get("duration", 0.0)),
                    "processing_time": 0.0,
                    "rtf": 0.0,
                }
            )

    payload = {
        "model": f"qwen3-asr-0.6b",
        "load_time_s": load_time,
        "peak_rss_mb": _peak_rss_mb(),
        "threads": args.threads,
        "metadata": {"engine": "qwen-asr", "model_id": args.repo, "runtime": "torch-cpu", "dtype": "float32"},
        "results": results,
        "summary": aggregate(results),
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    s = payload["summary"]
    print(
        f"qwen3-asr-0.6b: WER={s['wer']:.4f} CER={s['cer']:.4f} RTF={s['rtf']:.3f} "
        f"load={load_time:.1f}s rss={payload['peak_rss_mb']:.0f}MB ok={int(s['clips_ok'])}/{int(s['clips_total'])}"
    )


if __name__ == "__main__":
    main()
