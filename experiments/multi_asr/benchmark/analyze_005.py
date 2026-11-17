"""Consolida resultados 005 (qualidade, A/C, controlado e B)."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def _mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else 0.0


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tuned", required=True)
    p.add_argument("--default", required=True)
    p.add_argument("--tuning", required=True)
    p.add_argument("--b-ref", required=True)
    p.add_argument("--b-pk", required=True)
    p.add_argument("--out-json", required=True)
    p.add_argument("--out-md", required=True)
    args = p.parse_args(argv)

    tuned = json.loads(Path(args.tuned).read_text(encoding="utf-8"))
    default = json.loads(Path(args.default).read_text(encoding="utf-8"))
    tuning = json.loads(Path(args.tuning).read_text(encoding="utf-8"))
    b_ref = json.loads(Path(args.b_ref).read_text(encoding="utf-8"))
    b_pk = json.loads(Path(args.b_pk).read_text(encoding="utf-8"))

    by_scn: dict[str, list[dict]] = defaultdict(list)
    for i in tuned["items"]:
        by_scn[i["scenario"]].append(i)
    scenarios = {
        s: {
            "n": len(v),
            "pk_wer": _mean([x["pk_wer"] for x in v]),
            "w_wer": _mean([x["w_wer"] for x in v]),
            "a_coverage": _mean([x["a"]["coverage"]["coverage"] for x in v]),
            "a_integrity": _mean([x["a"]["integrity"]["wer_vs_full"] for x in v]),
            "c_coverage": _mean([x["c"]["coverage"]["coverage"] for x in v]),
        }
        for s, v in sorted(by_scn.items())
    }

    ctrl = tuned["controlled"]
    payload = {
        "params": tuned["params"],
        "quality": {
            "pk_wer": tuned["summary"]["pk_wer_mean"],
            "w_wer": tuned["summary"]["w_wer_mean"],
            "by_scenario": scenarios,
        },
        "strategy_a_tuned": {
            "valid_rate": tuned["summary"]["a_valid_rate"],
            "coverage": tuned["summary"]["a_coverage_mean"],
            "integrity_wer": tuned["summary"]["a_integrity_wer"],
            "rtf": tuned["totals"]["a_rtf"],
            "control_boundary_025": ctrl["a"]["boundary_025"],
            "control_boundary_050": ctrl["a"]["boundary_050"],
            "control_frag": ctrl["a"]["fragmentation"],
            "control_validity": ctrl["a"]["validity"],
        },
        "strategy_a_default": {
            "valid_rate": default["summary"]["a_valid_rate"],
            "coverage": default["summary"]["a_coverage_mean"],
            "integrity_wer": default["summary"]["a_integrity_wer"],
            "rtf": default["totals"]["a_rtf"],
        },
        "strategy_c": {
            "valid_rate": tuned["summary"]["c_valid_rate"],
            "coverage": tuned["summary"]["c_coverage_mean"],
            "integrity_wer": tuned["summary"]["c_integrity_wer"],
            "rtf": tuned["totals"]["c_rtf"],
            "control_boundary_025": ctrl["c"]["boundary_025"],
            "control_frag": ctrl["c"]["fragmentation"],
        },
        "strategy_b_mms_fa": {
            "reference_text": b_ref["boundary"],
            "parakeet_text": b_pk["boundary"],
            "proc_s": {"reference_text": b_ref["proc_s"], "parakeet_text": b_pk["proc_s"]},
            "segments": {"reference_text": b_ref["segments"], "parakeet_text": b_pk["segments"]},
        },
        "tuning": tuning,
        "totals": tuned["totals"],
    }
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    L: list[str] = ["# Validação 005 — qualidade e timestamps (CPU-only)", ""]
    L += ["## Qualidade ASR (16 clipes, fala espontânea + preparada)", "",
          "| Métrica | Parakeet PT-BR INT8 | Whisper large-v3-turbo |", "|---|---:|---:|",
          f"| WER | **{payload['quality']['pk_wer']:.4f}** | {payload['quality']['w_wer']:.4f} |", "",
          "| Cenário | n | WER Parakeet | WER Whisper |", "|---|---:|---:|---:|"]
    for s, v in scenarios.items():
        L.append(f"| {s} | {v['n']} | {v['pk_wer']:.4f} | {v['w_wer']:.4f} |")
    a, c = payload["strategy_a_tuned"], payload["strategy_c"]
    L += ["", "## Estratégias de timestamps", "",
          "| Estratégia | SRT válido | Cobertura | Integridade textual* | RTF | Fronteiras (recall@250ms) | MAE |",
          "|---|---:|---:|---:|---:|---:|---:|",
          f"| A — VAD + Parakeet (ajustada) | {a['valid_rate']:.0%} | {a['coverage']:.2f} | {1-a['integrity_wer']:.3f} | {a['rtf']:.3f} | {a['control_boundary_025']['recall']:.0%} | {a['control_boundary_025']['mae_matched_s']*1000:.0f} ms |",
          f"| A — VAD (padrão) | {payload['strategy_a_default']['valid_rate']:.0%} | {payload['strategy_a_default']['coverage']:.2f} | {1-payload['strategy_a_default']['integrity_wer']:.3f} | {payload['strategy_a_default']['rtf']:.3f} | — | — |",
          f"| C — Híbrido estimado | {c['valid_rate']:.0%} | {c['coverage']:.2f} | {1-c['integrity_wer']:.3f} | {c['rtf']:.3f} | {c['control_boundary_025']['recall']:.0%} | {c['control_boundary_025']['mae_matched_s']*1000:.0f} ms |",
          f"| B — MMS_FA (texto Parakeet) | n/a | n/a | 1.000 (texto fixo) | {b_pk['proc_s']/tuned['controlled']['duration']:.3f} | {b_pk['boundary']['recall']:.0%} | {b_pk['boundary']['mae_matched_s']*1000:.0f} ms |",
          "", "*Integridade = 1 - WER do texto segmentado contra o texto integral do mesmo motor.",
          "", "B executa apenas alinhamento (não reconhece); RTF mede alinhamento sobre 46,4 s.",
          "", "## Ajuste de VAD (conjunto controlado, 6 fronteiras conhecidas)", "",
          "| th | pad (ms) | Cobertura | Integridade | Frag./min | Recall | MAE |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in tuning["vad"]:
        cfgb = r["boundary_silence"]
        L.append(f"| {r['cfg']['threshold']} | {r['cfg']['pad_ms']} | {r['coverage']:.2f} | {r['integrity_wer']:.3f} | {r['frag_per_min']:.1f} | {cfgb['recall']:.0%} | {(cfgb['mae_matched_s'] or 0)*1000:.0f} ms |")
    L += ["", "## Limitações", "",
          "- Corpus público sem reuniões com sobreposição real; NURC é espontâneo (diálogos/entrevistas) e mTEDx é preparado.",
          "- Sem referência temporal humana; precisão de fronteira medida em conjunto controlado com silêncios inseridos.",
          "- B (MMS_FA) exige transcrição prévia, licença CC-BY-NC-4.0 do bundle e runtime torchaudio.",
          "- Estratégia C é estimada por alinhamento de sequência; não é alinhamento forçado por palavra.",
          ""]
    Path(args.out_md).write_text("\n".join(L), encoding="utf-8")
    print("analyzed 005")


if __name__ == "__main__":
    main()
