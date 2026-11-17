"""Agrega resultados por cenário, detecta possíveis alucinações e gera relatório."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .metrics import aggregate


def _hyp_ratio(item: dict) -> float:
    ref = max(len((item.get("reference") or "").split()), 1)
    hyp = len((item.get("text") or "").split())
    return hyp / ref


def summarize(results: dict[str, dict], manifest: list[dict]) -> dict:
    refs = {m["id"]: m for m in manifest}
    table = {}
    per_scenario = defaultdict(dict)
    for name, payload in results.items():
        table[name] = {
            "wer": payload["summary"]["wer"],
            "cer": payload["summary"]["cer"],
            "rtf": payload["summary"]["rtf"],
            "load_time_s": payload["load_time_s"],
            "peak_rss_mb": payload["peak_rss_mb"],
            "clips_ok": payload["summary"]["clips_ok"],
            "clips_total": payload["summary"]["clips_total"],
        }
        by_scn = defaultdict(list)
        for row in payload["results"]:
            by_scn[row["scenario"]].append(row)
        for scn, rows in by_scn.items():
            agg = aggregate(rows)
            per_scenario[scn][name] = {
                "wer": agg["wer"],
                "cer": agg["cer"],
                "rtf": agg["rtf"],
                "n": int(agg["clips_ok"]),
            }

    halluc = {}
    for name, payload in results.items():
        flagged = 0
        worst = 0.0
        for row in payload["results"]:
            if row.get("status") != "ok":
                continue
            item = refs.get(row["clip_id"], {})
            item = {**item, "reference": item.get("reference", ""), "text": row.get("text", "")}
            ratio = _hyp_ratio(item)
            worst = max(worst, ratio)
            if ratio > 1.5:
                flagged += 1
        halluc[name] = {"clips_ratio_gt_1_5": flagged, "max_hyp_ref_ratio": round(worst, 3)}

    return {"overall": table, "by_scenario": per_scenario, "hallucination_proxy": halluc}


def to_markdown(payload: dict) -> str:
    lines = ["# Resultados do benchmark multimotor (CPU-only)", ""]
    lines.append("## Visão geral")
    lines.append("")
    lines.append("| Modelo | WER | CER | RTF | Load (s) | RAM pico (MB) | OK |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for name, row in sorted(payload["overall"].items(), key=lambda kv: kv[1]["wer"]):
        lines.append(
            f"| {name} | {row['wer']:.4f} | {row['cer']:.4f} | {row['rtf']:.3f} | "
            f"{row['load_time_s']:.1f} | {row['peak_rss_mb']:.0f} | "
            f"{int(row['clips_ok'])}/{int(row['clips_total'])} |"
        )
    lines += ["", "## WER por cenário", ""]
    scenarios = sorted(payload["by_scenario"])
    models = sorted(payload["overall"])
    lines.append("| Modelo | " + " | ".join(scenarios) + " |")
    lines.append("|---|" + "---:|" * len(scenarios))
    for name in models:
        cells = []
        for scn in scenarios:
            val = payload["by_scenario"][scn].get(name, {}).get("wer")
            cells.append("—" if val is None else f"{val:.4f}")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", "## Proxy de alucinação (razão palavras hipótese/referência)", ""]
    lines.append("| Modelo | Clipes com razão > 1,5 | Razão máxima |")
    lines.append("|---|---:|---:|")
    for name, row in sorted(payload["hallucination_proxy"].items()):
        lines.append(f"| {name} | {row['clips_ratio_gt_1_5']} | {row['max_hyp_ref_ratio']:.2f} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args(argv)

    results = {}
    for path in sorted(Path(args.results_dir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if "model" not in payload:
            continue
        results[payload["model"]] = payload
    raw_manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    manifest = raw_manifest["items"] if isinstance(raw_manifest, dict) else raw_manifest
    summary = summarize(results, manifest)

    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out_md).write_text(to_markdown(summary), encoding="utf-8")
    print(f"summarized {len(results)} models")


if __name__ == "__main__":
    main()
