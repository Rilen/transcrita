"""Corpus 005: diálogos/entrevistas multi-falante + conjunto de fronteiras controladas."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .build_corpus_004 import (
    MTEDX, NURC, dataset_revision, duration_s, load_shard, probe,
    sha256_file, sha256_text, write_audio,
)

NURC_SHARDS = [
    "data/original/validation-00000.parquet",
    "data/original/test-00002.parquet",
    "data/original/train-00000.parquet",
]
MTEDX_SHARD = "data/test-00000-of-00003-ef95547d8377e9f8.parquet"


def _rows_nurc(rev: str | None) -> list[dict]:
    out: list[dict] = []
    for shard in NURC_SHARDS:
        out.extend(load_shard(NURC, shard, rev))
    return out


def _rows_mtedx(rev: str | None) -> list[dict]:
    return load_shard(MTEDX, MTEDX_SHARD, rev)


def _to_mono16k(src: Path, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
         "-ar", "16000", "-ac", "1", str(dst)], check=True,
    )


def _concat_with_silence(paths: list[Path], dst: Path, silence_s: float) -> list[dict]:
    work = dst.parent / "concat005"
    work.mkdir(exist_ok=True)
    silent = work / f"sil_{silence_s}.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
         f"anullsrc=r=16000:cl=mono:d={silence_s}", str(silent)], check=True,
    )
    listing = work / "list.txt"
    lines: list[str] = []
    refs: list[dict] = []
    cursor = 0.0
    for i, p in enumerate(paths):
        if i:
            lines.append(f"file '{silent.resolve()}'")
            cursor += silence_s
        dur = duration_s(p)
        lines.append(f"file '{p.resolve()}'")
        refs.append({"start": round(cursor, 3), "end": round(cursor + dur, 3)})
        cursor += dur
    listing.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-ar", "16000", "-ac", "1", str(dst)], check=True,
    )
    return refs


def build(out_dir: Path, n_dialog: int, n_interview: int, n_prep: int, n_ctrl: int) -> dict:
    wav = out_dir / "wav"
    wav.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []

    nurc_rev = dataset_revision(NURC)
    rows = _rows_nurc(nurc_rev)
    per_audio: dict[str, int] = {}

    def pick(genre: str, need: int) -> int:
        taken = 0
        for row in rows:
            if taken >= need:
                break
            if row.get("speech_genre") != genre:
                continue
            if str(row.get("num_speakers")) not in {"2", "3", "4"}:
                continue
            if row.get("quality") != "high" or row.get("variety") != "pt-br":
                continue
            try:
                dur = float(str(row.get("duration")))
            except (TypeError, ValueError):
                continue
            text = (row.get("text") or "").strip()
            if not (3.0 <= dur <= 15.0) or len(text) < 25:
                continue
            name = str(row.get("audio_name"))
            if per_audio.get(name, 0) >= 2:
                continue
            per_audio[name] = per_audio.get(name, 0) + 1
            rid = "nurc5_" + str(row["file_path"]).replace("/", "_").removesuffix(".wav")
            dst = wav / f"{rid}.wav"
            if not dst.exists():
                write_audio(row["audio"], dst)
            sr, ch = probe(dst)
            items.append({
                "id": rid, "path": str(dst), "reference": text,
                "duration": round(duration_s(dst), 3),
                "scenario": f"spontaneous_{genre}", "speech_genre": genre,
                "num_speakers": str(row.get("num_speakers")),
                "source_dataset": NURC, "source_file": row.get("file_path"),
                "source_revision": nurc_rev, "license": "CC-BY-NC-ND-4.0",
                "audio_sha256": sha256_file(dst), "text_sha256": sha256_text(text),
                "sample_rate": sr, "channels": ch,
            })
            taken += 1
        return taken

    pick("dialogue", n_dialog)
    pick("interview", n_interview)

    mtedx_rev = dataset_revision(MTEDX)
    mrows = _rows_mtedx(mtedx_rev)
    with_digits = [r for r in mrows if any(ch.isdigit() for ch in (r.get("transcription") or ""))]
    pool = with_digits + mrows
    taken = 0
    for idx, row in enumerate(pool):
        if taken >= n_prep:
            break
        text = (row.get("transcription") or "").strip()
        if len(text) < 25:
            continue
        rid = f"mtedx5_{idx:05d}"
        dst = wav / f"{rid}.wav"
        if not dst.exists():
            write_audio(row["audio"], dst)
        dur = duration_s(dst)
        if not (3.0 <= dur <= 20.0):
            dst.unlink(missing_ok=True)
            continue
        taken += 1
        sr, ch = probe(dst)
        items.append({
            "id": rid, "path": str(dst), "reference": text,
            "duration": round(dur, 3), "scenario": "prepared",
            "has_digits": any(c.isdigit() for c in text),
            "source_dataset": MTEDX, "source_row": idx,
            "source_revision": mtedx_rev, "license": "CC-BY-NC-4.0",
            "audio_sha256": sha256_file(dst), "text_sha256": sha256_text(text),
            "sample_rate": sr, "channels": ch,
        })

    # Conjunto controlado (mTEDx permite derivados; uso interno)
    ctrl_dir = out_dir / "controlled"
    ctrl_dir.mkdir(exist_ok=True)
    base = [i for i in items if i["scenario"] == "prepared"][:n_ctrl]
    mono_paths: list[Path] = []
    for i, item in enumerate(base):
        mono = ctrl_dir / f"ctrl_{i}.wav"
        _to_mono16k(Path(item["path"]), mono)
        mono_paths.append(mono)
    ctrl_wav = ctrl_dir / "controlled.wav"
    refs = _concat_with_silence(mono_paths, ctrl_wav, 1.0)
    text = " ".join(item["reference"] for item in base)
    for r, item in zip(refs, base):
        r["text"] = item["reference"]
    controlled = {
        "path": str(ctrl_wav),
        "duration": round(duration_s(ctrl_wav), 3),
        "reference_segments": refs,
        "reference_text": text,
        "license": "CC-BY-NC-4.0 (derivado autorizado, uso interno)",
        "note": "silêncios inseridos de 1,0 s delimitam fronteiras conhecidas",
    }
    (ctrl_dir / "controlled_reference.json").write_text(
        json.dumps(controlled, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "items": items,
        "controlled": controlled,
        "provenance": {
            "sources": [
                {"dataset": NURC, "revision": nurc_rev, "license": "CC-BY-NC-ND-4.0",
                 "note": "sem transformação de áudio"},
                {"dataset": MTEDX, "revision": mtedx_rev, "license": "CC-BY-NC-4.0",
                 "note": "derivado permitido apenas no conjunto controlado interno"},
            ],
            "retrieval": "shards parquet oficiais via hf_hub_download (repo_type=dataset)",
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="/var/lib/transcrita-poc/corpus005")
    parser.add_argument("--dialogue", type=int, default=8)
    parser.add_argument("--interview", type=int, default=4)
    parser.add_argument("--prepared", type=int, default=6)
    parser.add_argument("--controlled", type=int, default=6)
    args = parser.parse_args(argv)
    m = build(Path(args.out), args.dialogue, args.interview, args.prepared, args.controlled)
    items = m["items"]
    by = {}
    for i in items:
        by[i["scenario"]] = by.get(i["scenario"], 0) + 1
    print(f"corpus005: {len(items)} itens ({sum(i['duration'] for i in items):.1f}s) {by}; "
          f"controlado={m['controlled']['duration']}s refs={len(m['controlled']['reference_segments'])}")


if __name__ == "__main__":
    main()
