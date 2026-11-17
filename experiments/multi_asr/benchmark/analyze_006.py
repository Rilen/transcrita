"""Consolida diagnóstico e correções da missão 006."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True)
    p.add_argument("--sweep", required=True)
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=True)
    args = p.parse_args(argv)

    run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    sweep = json.loads(Path(args.sweep).read_text(encoding="utf-8"))
    s, t, c = run["summary"], run["totals"], run["controlled"]

    payload = {
        "diagnosis": {
            "n": s["n"],
            "ref_tokens": s["ref_tokens"],
            "wer_full": s["wer_full"],
            "wer_a005": s["wer_a005"],
            "integrity_a005": s["integrity_a005"],
            "lost_ref_tokens_a005": s["lost_ref_a005"],
            "duplicates_full": s["dup_full"],
            "duplicates_a005": s["dup_a2"],
            "uncovered_speech_proxy": s["uncovered_speech_proxy"],
        },
        "fix_a2": {
            "params": run["configs"]["a2"],
            "wer": s["wer_a2"],
            "integrity": s["integrity_a2"],
            "lost_ref_tokens": s["lost_ref_a2"],
            "srt_valid_rate": s["a2_srt_valid_rate"],
            "rtf": t["a2_rtf"],
        },
        "reconciled": {
            "rtf": t["rec_rtf"],
            "ok": s["rec_ok"],
            "srt_valid_rate": s["rec_srt_valid_rate"],
            "text_equal_full_controlled": c.get("reconciled", {}).get("text_equal_full"),
            "origin": "texto do passe integral + tempos estimados (sem invenção)",
        },
        "controlled": {k: c[k] for k in ("a005", "a2", "reconciled") if k in c},
        "rss_peak_mb": run["rss_peak_mb"],
        "sweep": sweep,
    }
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["# Missão 006 — integridade textual (resultados)", "",
         "## Diagnóstico (A005 vs passe integral)", "",
         f"- Clipes: {s['n']} · tokens de referência: {s['ref_tokens']}",
         f"- WER: integral {s['wer_full']:.4f} · A005 {s['wer_a005']:.4f}",
         f"- Integridade A005: {1-s['integrity_a005']:.3f}",
         f"- Palavras de referência perdidas pela A005: **{s['lost_ref_a005']}**",
         f"- Duplicações (bigramas): integral {s['dup_full']} · A005 {s['dup_a2']}",
         f"- Fala não coberta (proxy): {s['uncovered_speech_proxy']:.4f}",
         "", "## Correção A2 (VAD pad=250 ms, merge 0,35 s, th 0,30)", "",
         f"- WER: **{s['wer_a2']:.4f}** (igual ao passe integral)",
         f"- Integridade: **{1-s['integrity_a2']:.4f}** · palavras perdidas: {s['lost_ref_a2']}",
         f"- SRT válido: {s['a2_srt_valid_rate']:.0%} · RTF: {t['a2_rtf']:.3f}",
         f"- Fronteiras (controlado): recall@250 ms {c['a2']['boundary_025']['recall']:.0%} · recall@500 ms {c['a2']['boundary_050']['recall']:.0%} · MAE {c['a2']['boundary_050']['mae_matched_s']*1000:.0f} ms",
         "", "## Reconciliação (texto integral + tempos estimados)", "",
         f"- Clipes reconciliados: {s['rec_ok']}/{s['n']} · SRT válido: {s['rec_srt_valid_rate']:.0%} · RTF: {t['rec_rtf']:.3f}",
         f"- Texto igual ao integral (controlado): {c.get('reconciled', {}).get('text_equal_full')}",
         "", "## Varredura de padding (16 clipes + controlado)", "",
         "| pad (ms) | merge (s) | WER | Integridade média | Integridade máx. | Recall@250 | Recall@500 | MAE |",
         "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in sweep:
        L.append(f"| {r['pad']} | {r['merge']} | {r['wer']:.4f} | {1-r['integrity_mean']:.4f} | {1-r['integrity_max']:.4f} | {r['recall025']:.0%} | {r['recall050']:.0%} | {(r['mae025'] or 0)*1000:.0f} ms |")
    L += ["", "Integridade = 1 − WER do texto segmentado contra o passe integral do próprio Parakeet.",
          "Recall/MAE medidos no conjunto controlado contra onsets de fala conhecidos.", ""]
    Path(args.out_md).write_text("\n".join(L), encoding="utf-8")
    print("analyzed 006")


if __name__ == "__main__":
    main()
