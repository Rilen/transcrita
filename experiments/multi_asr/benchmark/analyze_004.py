"""Análise da validação 004: cenários, S/D/I, números, termos raros, timestamps e estabilidade."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from .metrics import (
    aggregate,
    error_breakdown,
    numeric_accuracy,
    rare_token_recall,
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def analyze(results_dir: Path, manifest_path: Path) -> dict:
    raw = _load(manifest_path)
    items = raw["items"] if isinstance(raw, dict) else raw
    refs = {i["id"]: i for i in items}

    payload: dict = {"models": {}, "stability": {}}
    for path in sorted(results_dir.glob("*.json")):
        data = _load(path)
        if "model" not in data:
            continue
        name = data["model"]
        rows = data["results"]
        ok = [r for r in rows if r.get("status") == "ok"]
        refs_all = [refs[r["clip_id"]]["reference"] for r in ok if r["clip_id"] in refs]
        hyps_all = [r.get("text", "") for r in ok if r["clip_id"] in refs]

        # S/D/I agregados
        sdi = {"substitutions": 0.0, "deletions": 0.0, "insertions": 0.0, "hits": 0.0}
        for r, ref in zip(ok, refs_all):
            b = error_breakdown(ref, r.get("text", ""))
            for k in sdi:
                sdi[k] += b[k]
        ref_words = max(sum(len(ref.split()) for ref in refs_all), 1)

        # por cenário
        by_scn: dict[str, list[dict]] = defaultdict(list)
        for r in ok:
            by_scn[r["scenario"]].append(r)
        scn = {k: aggregate(v) for k, v in by_scn.items()}

        # timestamps
        ts_counts = [r.get("n_segments", 0) for r in ok]
        cover = [
            (r.get("timestamps_span", 0.0) / r["audio_duration"])
            for r in ok
            if r.get("audio_duration")
        ]

        payload["models"][name] = {
            "overall": {
                **data["summary"],
                "load_time_s": data["load_time_s"],
                "peak_rss_mb": data["peak_rss_mb"],
                "threads": data["threads"],
            },
            "by_scenario": scn,
            "sdi": {
                "substitutions_per_word": sdi["substitutions"] / ref_words,
                "deletions_per_word": sdi["deletions"] / ref_words,
                "insertions_per_word": sdi["insertions"] / ref_words,
                "ref_words": ref_words,
            },
            "numbers": numeric_accuracy(refs_all, hyps_all),
            "rare_terms": rare_token_recall(refs_all, hyps_all),
            "timestamps": {
                "clips_with_segments": sum(1 for c in ts_counts if c > 0),
                "mean_segments": statistics.fmean(ts_counts) if ts_counts else 0.0,
                "mean_span_coverage": statistics.fmean(cover) if cover else 0.0,
            },
        }

    stab_dir = results_dir / "stability"
    if stab_dir.is_dir():
        groups: dict[str, list[dict]] = defaultdict(list)
        for path in sorted(stab_dir.glob("*.json")):
            data = _load(path)
            if "model" not in data:
                continue
            groups[data["model"]].append(data)
        for name, runs in groups.items():
            wers = [r["summary"]["wer"] for r in runs]
            times = [sum(x["processing_time"] for x in r["results"]) for r in runs]
            texts_per_run = [
                {r["clip_id"]: r.get("text", "") for r in run["results"]} for run in runs
            ]
            identical = all(t == texts_per_run[0] for t in texts_per_run)
            payload["stability"][name] = {
                "runs": len(runs),
                "wer_mean": statistics.fmean(wers),
                "wer_sd": statistics.pstdev(wers),
                "proc_time_mean_s": statistics.fmean(times),
                "proc_time_sd_s": statistics.pstdev(times),
                "outputs_identical": identical,
            }
    return payload


def to_markdown(payload: dict) -> str:
    L = ["# Validação 004 — resultados (fala espontânea e preparada)", ""]
    L += ["## Visão geral", "", "| Modelo | WER | CER | RTF | Load (s) | RAM (MB) |", "|---|---:|---:|---:|---:|---:|"]
    for n, m in sorted(payload["models"].items(), key=lambda kv: kv[1]["overall"]["wer"]):
        o = m["overall"]
        L.append(f"| {n} | {o['wer']:.4f} | {o['cer']:.4f} | {o['rtf']:.3f} | {o['load_time_s']:.1f} | {o['peak_rss_mb']:.0f} |")
    L += ["", "## WER por cenário", "", "| Modelo | espontâneo | preparado |", "|---|---:|---:|"]
    for n, m in sorted(payload["models"].items()):
        a = m["by_scenario"].get("spontaneous", {}).get("wer")
        b = m["by_scenario"].get("prepared", {}).get("wer")
        fa = "—" if a is None else f"{a:.4f}"
        fb = "—" if b is None else f"{b:.4f}"
        L.append(f"| {n} | {fa} | {fb} |")
    L += ["", "## Erros por tipo (por palavra de referência)", "", "| Modelo | Subst. | Del. | Ins. |", "|---|---:|---:|---:|"]
    for n, m in sorted(payload["models"].items()):
        s = m["sdi"]
        L.append(f"| {n} | {s['substitutions_per_word']:.4f} | {s['deletions_per_word']:.4f} | {s['insertions_per_word']:.4f} |")
    L += ["", "## Números e termos raros", "", "| Modelo | Recall números | Nº espúrios | Recall raros |", "|---|---:|---:|---:|"]
    for n, m in sorted(payload["models"].items()):
        num, rare = m["numbers"], m["rare_terms"]
        L.append(f"| {n} | {num['recall']:.3f} ({int(num['ref_numbers'])} refs) | {int(num['spurious'])} | {rare['rare_recall']:.3f} ({int(rare['rare_tokens'])}) |")
    L += ["", "## Timestamps", "", "| Modelo | Clipes com segmentos | Segmentos (média) | Cobertura média |", "|---|---:|---:|---:|"]
    for n, m in sorted(payload["models"].items()):
        t = m["timestamps"]
        L.append(f"| {n} | {t['clips_with_segments']} | {t['mean_segments']:.1f} | {t['mean_span_coverage']:.2f} |")
    if payload.get("stability"):
        L += ["", "## Estabilidade (3 repetições, 8 clipes)", "", "| Modelo | WER médio | dp WER | Tempo médio (s) | dp tempo | Saídas idênticas |", "|---|---:|---:|---:|---:|---|"]
        for n, s in sorted(payload["stability"].items()):
            L.append(f"| {n} | {s['wer_mean']:.4f} | {s['wer_sd']:.4f} | {s['proc_time_mean_s']:.1f} | {s['proc_time_sd_s']:.2f} | {'sim' if s['outputs_identical'] else 'não'} |")
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args(argv)
    payload = analyze(Path(args.results_dir), Path(args.manifest))
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.out_md).write_text(to_markdown(payload), encoding="utf-8")
    print(f"analyzed {len(payload['models'])} models")


if __name__ == "__main__":
    main()
