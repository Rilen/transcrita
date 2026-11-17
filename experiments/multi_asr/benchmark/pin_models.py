"""Registra revisões, licenças e runtimes dos modelos usados (auditoria)."""

from __future__ import annotations

import json
import platform
from pathlib import Path

import ctranslate2
import onnx_asr
import onnxruntime
from huggingface_hub import model_info


def _ct2_repo(model_size: str) -> str:
    from faster_whisper.utils import _MODELS

    return _MODELS[model_size]


def _card_license(repo_id: str) -> str | None:
    try:
        info = model_info(repo_id)
    except Exception:
        return None
    card = info.cardData or {}
    lic = card.get("license")
    return ",".join(lic) if isinstance(lic, list) else lic


def _revision(repo_id: str) -> str | None:
    try:
        return model_info(repo_id).sha
    except Exception:
        return None


def main() -> None:
    import faster_whisper

    repos = {}
    for size in ("small", "medium", "large-v3", "large-v3-turbo"):
        repo = _ct2_repo(size)
        repos[f"whisper-{size}"] = {
            "runtime": "faster-whisper",
            "repo_id": repo,
            "revision": _revision(repo),
            "license": _card_license(repo),
        }
    for key, repo, runtime in (
        ("parakeet-ptbr-tagarela-int8", "calneymgp/parakeet-tdt-0.6b-v3-ptBR-TAGARELA-onnx-int8", "onnx-asr"),
        ("qwen3-asr-0.6b", "Qwen/Qwen3-ASR-0.6B", "qwen-asr/torch-cpu"),
    ):
        repos[key] = {
            "runtime": runtime,
            "repo_id": repo,
            "revision": _revision(repo),
            "license": _card_license(repo),
        }

    payload = {
        "captured_utc": __import__("datetime").datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "faster_whisper": faster_whisper.__version__,
            "ctranslate2": ctranslate2.__version__,
            "onnxruntime": onnxruntime.__version__,
            "onnx_asr": getattr(onnx_asr, "__version__", "unknown"),
        },
        "models": repos,
        "load_time_semantics": (
            "run_benchmark.load_time_s inclui download na primeira execução; "
            "tempos a quente medidos por warm_load.py sem inferência"
        ),
    }
    out = Path("experiments/multi_asr/reports/METADATA.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:800])


if __name__ == "__main__":
    main()
