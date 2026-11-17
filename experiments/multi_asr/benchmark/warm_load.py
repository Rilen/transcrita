"""Mede tempo de carregamento com pesos já em cache (sem inferência)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from ..adapters import ADAPTERS


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configs", default="experiments/multi_asr/configs/models.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    configs = json.loads(Path(args.configs).read_text(encoding="utf-8"))
    out = {}
    for name, cfg in configs.items():
        adapter = ADAPTERS[cfg["type"]]()
        started = time.perf_counter()
        try:
            adapter.load(cfg)
            out[name] = round(time.perf_counter() - started, 2)
        except Exception as exc:  # noqa: BLE001
            out[name] = f"error: {exc}"[:120]
        finally:
            try:
                adapter.unload()
            except Exception:
                pass
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
