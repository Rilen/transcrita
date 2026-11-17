"""Constrói corpus controlado a partir do MLS Portuguese (CC-BY-4.0).

Baixa amostras públicas (audio + transcript humano), converte para WAV 16 kHz
mono e deriva cenários: clean, noisy, distant, multi e long.

Áudio e referências são gravados FORA do repositório (--out), nunca versionados.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

ROWS_API = "https://datasets-server.huggingface.co/rows"


def _fetch_rows(offset: int, length: int = 100) -> list[dict]:
    query = urllib.parse.urlencode(
        {
            "dataset": "facebook/multilingual_librispeech",
            "config": "portuguese",
            "split": "test",
            "offset": offset,
            "length": length,
        }
    )
    with urllib.request.urlopen(f"{ROWS_API}?{query}", timeout=60) as resp:
        payload = json.load(resp)
    return [row["row"] for row in payload.get("rows", [])]


def _download(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=120) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())


def _to_wav(src: Path, dst: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ar", "16000", "-ac", "1", str(dst)],
        check=True,
    )


def _derive(src: Path, dst: Path, kind: str) -> None:
    if kind == "noisy":
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex",
               "[0:a]volume=1.0[a];anoisesrc=color=white:amplitude=0.05,highpass=f=80[n];[a][n]amix=inputs=2:duration=first:normalize=0", str(dst)]
    elif kind == "distant":
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af",
               "lowpass=f=3500,aecho=0.8:0.6:45:0.25,volume=0.55", str(dst)]
    else:
        raise ValueError(kind)
    subprocess.run(cmd, check=True)


def _concat(paths: list[Path], dst: Path, silence_s: float = 0.5) -> None:
    work = dst.parent / "concat"
    work.mkdir(exist_ok=True)
    listing = work / "list.txt"
    silent = work / "silence.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"anullsrc=r=16000:cl=mono:d={silence_s}", str(silent)], check=True)
    lines = []
    for i, part in enumerate(paths):
        if i:
            lines.append(f"file '{silent.resolve()}'")
        lines.append(f"file '{part.resolve()}'")
    listing.write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-ar", "16000", "-ac", "1", str(dst)], check=True)


def _dur(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def build(out_dir: Path, shorts: int, noise: int, distant: int, multi: int, long_clips: int) -> list[dict]:
    raw = out_dir / "raw"
    wav = out_dir / "wav"
    raw.mkdir(parents=True, exist_ok=True)
    wav.mkdir(parents=True, exist_ok=True)

    needed = shorts + noise + distant + multi * 3
    selected: list[dict] = []
    offset = 0
    speaker_counts: dict[str, int] = {}
    while len(selected) < needed and offset < 900:
        rows = _fetch_rows(offset)
        if not rows:
            break
        for row in rows:
            dur = float(row.get("audio_duration") or 0.0)
            speaker = str(row.get("speaker_id"))
            if not (6.0 <= dur <= 25.0) or not row.get("transcript"):
                continue
            if speaker_counts.get(speaker, 0) >= 2:
                continue
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
            selected.append(row)
            if len(selected) >= needed:
                break
        offset += 100

    manifest: list[dict] = []
    clips: list[dict] = []
    for idx, row in enumerate(selected):
        rid = str(row["id"]).replace("/", "_")
        src_opus = raw / f"{rid}.opus"
        src_wav = wav / f"{rid}.wav"
        audio_url = row["audio"][0]["src"]
        _download(audio_url, src_opus)
        _to_wav(src_opus, src_wav)
        clips.append(
            {
                "id": rid,
                "path": str(src_wav),
                "reference": row["transcript"],
                "duration": _dur(src_wav),
                "speaker": str(row.get("speaker_id")),
            }
        )

    def add(item: dict) -> None:
        manifest.append(item)

    for clip in clips[:shorts]:
        add({**clip, "scenario": "clean"})

    for clip in clips[shorts:shorts + noise]:
        dst = wav / f"{clip['id']}_noisy.wav"
        _derive(Path(clip["path"]), dst, "noisy")
        add({**clip, "id": dst.stem, "path": str(dst), "duration": _dur(dst), "scenario": "noisy"})

    base = shorts + noise
    for clip in clips[base:base + distant]:
        dst = wav / f"{clip['id']}_distant.wav"
        _derive(Path(clip["path"]), dst, "distant")
        add({**clip, "id": dst.stem, "path": str(dst), "duration": _dur(dst), "scenario": "distant"})

    base += distant
    for g in range(multi):
        group = clips[base + g * 3: base + g * 3 + 3]
        if len(group) < 3:
            break
        dst = wav / f"multi_{g}.wav"
        _concat([Path(c["path"]) for c in group], dst)
        add(
            {
                "id": dst.stem,
                "path": str(dst),
                "reference": " ".join(c["reference"] for c in group),
                "duration": _dur(dst),
                "speaker": ",".join(c["speaker"] for c in group),
                "scenario": "multi",
            }
        )

    if len(clips) >= long_clips:
        group = clips[:long_clips]
        dst = wav / "long_0.wav"
        _concat([Path(c["path"]) for c in group], dst)
        add(
            {
                "id": dst.stem,
                "path": str(dst),
                "reference": " ".join(c["reference"] for c in group),
                "duration": _dur(dst),
                "speaker": ",".join(c["speaker"] for c in group),
                "scenario": "long",
            }
        )

    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="/var/lib/transcrita-poc/corpus")
    parser.add_argument("--shorts", type=int, default=6)
    parser.add_argument("--noise", type=int, default=2)
    parser.add_argument("--distant", type=int, default=2)
    parser.add_argument("--multi", type=int, default=1)
    parser.add_argument("--long", type=int, default=4)
    args = parser.parse_args(argv)
    manifest = build(Path(args.out), args.shorts, args.noise, args.distant, args.multi, args.long)
    print(f"manifest: {len(manifest)} itens em {args.out}/manifest.json")


if __name__ == "__main__":
    main()
