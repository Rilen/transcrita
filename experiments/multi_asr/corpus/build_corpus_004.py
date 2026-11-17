"""Corpus 004: fala espontânea (NURC-SP) e preparada (mTEDx), sem derivar áudio.

Fontes públicas (lidas via shards parquet oficiais do repositório HF):
- nilc-nlp/CORAA-NURC-SP-Audio-Corpus (CC-BY-NC-ND-4.0) — fala espontânea pt-BR.
- dominguesm/mTEDx-ptbr (CC-BY-NC-4.0) — palestras TEDx pt-BR.

Nenhuma transformação de áudio é aplicada (NURC é ND). Apenas manifesto,
hashes e instruções são versionados; áudio permanece fora do repositório.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path

NURC = "nilc-nlp/CORAA-NURC-SP-Audio-Corpus"
MTEDX = "dominguesm/mTEDx-ptbr"
NURC_SHARDS = [
    "data/original/validation-00001.parquet",
    "data/original/test-00002.parquet",
    "data/original/validation-00000.parquet",
]
MTEDX_SHARD = "data/test-00000-of-00003-ef95547d8377e9f8.parquet"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def duration_s(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def probe(path: Path) -> tuple[int, int]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    sr, ch = out.stdout.strip().split(",")[:2]
    return int(sr), int(ch)


def load_shard(repo: str, filename: str, revision: str | None) -> list[dict]:
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    local = hf_hub_download(repo_id=repo, filename=filename, revision=revision,
                            local_dir=f"/var/lib/transcrita-poc/shards/{repo.replace('/', '_')}", repo_type="dataset")
    return pq.read_table(local).to_pylist()


def write_audio(audio: dict, dst: Path) -> None:
    data = audio.get("bytes") if isinstance(audio, dict) else None
    if data is None and isinstance(audio, dict) and audio.get("path"):
        data = Path(audio["path"]).read_bytes()
    if data is None:
        raise RuntimeError("áudio sem bytes no parquet")
    dst.write_bytes(data)


def dataset_revision(repo: str) -> str | None:
    try:
        from huggingface_hub import dataset_info

        return dataset_info(repo).sha
    except Exception:
        return None


def build(out_dir: Path, n_spont: int, n_prep: int) -> dict:
    wav = out_dir / "wav"
    wav.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []

    nurc_rev = dataset_revision(NURC)
    per_audio: dict[str, int] = {}
    for shard in NURC_SHARDS:
        if len([i for i in items if i["scenario"] == "spontaneous"]) >= n_spont:
            break
        rows = load_shard(NURC, shard, nurc_rev)
        for row in rows:
            if len([i for i in items if i["scenario"] == "spontaneous"]) >= n_spont:
                break
            if row.get("variety") != "pt-br" or row.get("quality") != "high":
                continue
            try:
                dur = float(str(row.get("duration")))
            except (TypeError, ValueError):
                continue
            text = (row.get("text") or "").strip()
            if not (3.0 <= dur <= 15.0) or len(text) < 25:
                continue
            name = str(row.get("audio_name"))
            if per_audio.get(name, 0) >= 3:
                continue
            per_audio[name] = per_audio.get(name, 0) + 1
            rid = "nurc_" + str(row["file_path"]).replace("/", "_").removesuffix(".wav")
            dst = wav / f"{rid}.wav"
            if not dst.exists():
                write_audio(row["audio"], dst)
            sr, ch = probe(dst)
            items.append({
                "id": rid, "path": str(dst), "reference": text,
                "duration": round(duration_s(dst), 3), "scenario": "spontaneous",
                "speech_genre": row.get("speech_genre"), "speech_style": row.get("speech_style"),
                "source_dataset": NURC, "source_split": shard.split("/")[2], "source_file": row.get("file_path"),
                "source_revision": nurc_rev, "license": "CC-BY-NC-ND-4.0",
                "audio_sha256": sha256_file(dst), "text_sha256": sha256_text(text),
                "sample_rate": sr, "channels": ch,
            })

    mtedx_rev = dataset_revision(MTEDX)
    rows = load_shard(MTEDX, MTEDX_SHARD, mtedx_rev)
    taken = 0
    for idx, row in enumerate(rows):
        if taken >= n_prep:
            break
        text = (row.get("transcription") or "").strip()
        if len(text) < 25:
            continue
        rid = f"mtedx_{idx:05d}"
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
            "source_dataset": MTEDX, "source_split": "test", "source_row": idx,
            "source_revision": mtedx_rev, "license": "CC-BY-NC-4.0",
            "audio_sha256": sha256_file(dst), "text_sha256": sha256_text(text),
            "sample_rate": sr, "channels": ch,
        })

    manifest = {
        "items": items,
        "provenance": {
            "sources": [
                {"dataset": NURC, "revision": nurc_rev, "license": "CC-BY-NC-ND-4.0",
                 "shards": NURC_SHARDS, "note": "uso interno, sem redistribuição/derivação de áudio"},
                {"dataset": MTEDX, "revision": mtedx_rev, "license": "CC-BY-NC-4.0",
                 "shard": MTEDX_SHARD, "note": "uso interno, sem redistribuição de áudio"},
            ],
            "retrieval": "hf_hub_download dos shards parquet; áudio extraído sem transformação.",
            "no_derivatives": "NURC-SP é CC-BY-NC-ND: nenhuma transformação de áudio aplicada.",
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="/var/lib/transcrita-poc/corpus004")
    parser.add_argument("--spontaneous", type=int, default=16)
    parser.add_argument("--prepared", type=int, default=8)
    args = parser.parse_args(argv)
    manifest = build(Path(args.out), args.spontaneous, args.prepared)
    items = manifest["items"]
    total = sum(i["duration"] for i in items)
    scn: dict[str, int] = {}
    for i in items:
        scn[i["scenario"]] = scn.get(i["scenario"], 0) + 1
    print(f"corpus004: {len(items)} itens ({total:.1f}s) {scn}")


if __name__ == "__main__":
    main()
