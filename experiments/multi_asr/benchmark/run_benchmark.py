"""Executor de benchmark CPU-only (sequencial, com limites)."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psutil

from ..adapters import ADAPTERS
from ..adapters.base import ASRAdapter
from .metrics import aggregate, error_rates


def _peak_rss_sampler(pid: int, stop: threading.Event, out: list[float]) -> None:
    proc = psutil.Process(pid)
    while not stop.is_set():
        try:
            rss = proc.memory_info().rss / (1024 * 1024)
            if rss > out[0]:
                out[0] = rss
        except psutil.Error:
            break
        stop.wait(0.05)


def _make_adapter(kind: str) -> ASRAdapter:
    cls = ADAPTERS[kind]
    return cls()


def run_model(
    name: str,
    cfg: dict[str, Any],
    manifest: list[dict],
    language: str,
    timeout_s: float,
    warmup: bool,
) -> dict[str, Any]:
    adapter = _make_adapter(cfg["type"])
    load_start = time.perf_counter()
    adapter.load(cfg)
    load_time = time.perf_counter() - load_start

    pid = os.getpid()
    stop = threading.Event()
    peak = [0.0]
    sampler = threading.Thread(target=_peak_rss_sampler, args=(pid, stop, peak), daemon=True)
    sampler.start()

    results: list[dict[str, Any]] = []
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        if warmup and manifest:
            try:
                pool.submit(adapter.transcribe, manifest[0]["path"], language).result(timeout=timeout_s)
            except Exception:
                pass

        for item in manifest:
            started = time.perf_counter()
            try:
                fut = pool.submit(adapter.transcribe, item["path"], language)
                res = fut.result(timeout=timeout_s)
                elapsed = time.perf_counter() - started
                duration = res.audio_duration or float(item.get("duration", 0.0))
                rates = error_rates(item["reference"], res.text)
                results.append(
                    {
                        **rates,
                        "clip_id": item["id"],
                        "scenario": item["scenario"],
                        "audio_duration": duration,
                        "processing_time": elapsed,
                        "rtf": (elapsed / duration) if duration else 0.0,
                        "status": res.status,
                        "text": res.text[:400],
                    }
                )
            except TimeoutError:
                results.append(
                    {
                        "clip_id": item["id"],
                        "scenario": item["scenario"],
                        "status": "timeout",
                        "wer": 1.0,
                        "cer": 1.0,
                        "ref_words": float(max(len(item["reference"].split()), 1)),
                        "audio_duration": float(item.get("duration", 0.0)),
                        "processing_time": timeout_s,
                        "rtf": 0.0,
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
    finally:
        try:
            adapter.unload()
        finally:
            stop.set()
            sampler.join(timeout=2)
            pool.shutdown(wait=False, cancel_futures=True)

    return {
        "model": name,
        "load_time_s": load_time,
        "peak_rss_mb": peak[0],
        "threads": int(cfg.get("cpu_threads", 12)),
        "metadata": adapter.metadata(),
        "results": results,
        "summary": aggregate(results),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="nome no arquivo de configs")
    parser.add_argument("--configs", default="experiments/multi_asr/configs/models.json")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--language", default="pt")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    configs = json.loads(Path(args.configs).read_text(encoding="utf-8"))
    if args.model not in configs:
        raise SystemExit(f"modelo desconhecido: {args.model}")
    cfg = configs[args.model]
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    out = run_model(
        args.model,
        cfg,
        manifest,
        args.language,
        args.timeout,
        warmup=not args.no_warmup,
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    s = out["summary"]
    print(
        f"{args.model}: WER={s['wer']:.4f} CER={s['cer']:.4f} RTF={s['rtf']:.3f} "
        f"load={out['load_time_s']:.1f}s rss={out['peak_rss_mb']:.0f}MB "
        f"ok={int(s['clips_ok'])}/{int(s['clips_total'])}"
    )


if __name__ == "__main__":
    main()
