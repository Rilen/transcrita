"""Interface de linha de comando da transcrita."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from transcrita import __version__
from transcrita.core import Transcriber
from transcrita.srt import to_srt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcrita",
        description="Transcreve arquivos de áudio e vídeo localmente em português usando faster-whisper.",
    )
    parser.add_argument(
        "input",
        help="Caminho do arquivo de áudio ou vídeo a ser transcrito.",
    )
    parser.add_argument(
        "-m",
        "--model",
        default="base",
        help="Tamanho do modelo Whisper (tiny, base, small, medium, large-v3, large-v3-turbo). Padrão: base",
    )
    parser.add_argument(
        "-l",
        "--language",
        default="pt",
        help="Idioma da transcrição (código ISO 639-1). Padrão: pt",
    )
    parser.add_argument(
        "-o",
        "--output-txt",
        metavar="ARQUIVO",
        help="Caminho do arquivo de saída em texto (.txt).",
    )
    parser.add_argument(
        "-s",
        "--output-srt",
        metavar="ARQUIVO",
        help="Caminho do arquivo de saída em legendas (.srt).",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Dispositivo de inferência (auto, cpu, cuda). Padrão: auto",
    )
    parser.add_argument(
        "--compute-type",
        default="auto",
        help="Tipo de computação (auto, int8, int8_float32, int8_float16, float16, float32). Padrão: auto",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Tamanho do feixe para decodificação. Padrão: 5",
    )
    parser.add_argument(
        "--vad",
        action="store_true",
        help="Ativa o filtro de detecção de atividade de voz (VAD). Requer onnxruntime.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = args.input
    if not Path(input_path).is_file():
        print(f"Erro: arquivo não encontrado: {input_path}", file=sys.stderr)
        return 1

    try:
        transcriber = Transcriber(
            model_size=args.model,
            language=args.language,
            device=args.device,
            compute_type=args.compute_type,
        )

        segments = transcriber.transcribe_to_segments(
            input_path,
            beam_size=args.beam_size,
            vad_filter=args.vad,
        )

        if not segments:
            print("Nenhum segmento transcrito.", file=sys.stderr)
            return 1

        full_text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())

        wrote_any = False

        if args.output_txt:
            output_txt = Path(args.output_txt)
            output_txt.write_text(full_text + "\n", encoding="utf-8")
            print(f"Texto salvo em: {output_txt}")
            wrote_any = True

        if args.output_srt:
            output_srt = Path(args.output_srt)
            output_srt.write_text(to_srt(segments), encoding="utf-8")
            print(f"Legendas salvas em: {output_srt}")
            wrote_any = True

        if not wrote_any:
            print(full_text)

        return 0

    except Exception as exc:  # noqa: BLE001
        print(f"Erro durante a transcrição: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
