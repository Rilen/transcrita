"""Interface web local para transcrita usando FastAPI."""

from __future__ import annotations

import argparse
import gc
import json
import queue
import tempfile
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from transcrita import __version__
from transcrita.core import Transcriber
from transcrita.srt import to_srt

app = FastAPI(title="transcrita-web", version=__version__)

_STATIC_DIR = Path(__file__).resolve().parent / "static"

# Cache de tamanho 1 (single-model) protegido por threading.Lock().
# Armazena apenas a última chave (model_size, device, compute_type) e sua
# instância Transcriber. Ao trocar de modelo, a instância anterior é
# descartada e a memória é liberada via gc.collect() e, quando disponível,
# torch.cuda.empty_cache().
_transcriber_lock = threading.Lock()
_transcriber_cache: dict = {
    "key": None,  # tuple[str, str, str] | None
    "instance": None,  # Transcriber | None
}


def _get_transcriber(
    model_size: str,
    device: str,
    compute_type: str,
) -> Transcriber:
    """Retorna o Transcriber em cache, criando-o se necessário.

    Mantém no máximo 1 instância ativa. Quando a chave muda, a instância
    anterior é evicta e a memória é liberada antes de instanciar o novo
    modelo.
    """
    key = (model_size, device, compute_type)

    with _transcriber_lock:
        current_key = _transcriber_cache["key"]
        current_instance = _transcriber_cache["instance"]

        if current_key == key and current_instance is not None:
            return current_instance

        # Evicção do modelo anterior
        if current_instance is not None:
            del current_instance
            _transcriber_cache["key"] = None
            _transcriber_cache["instance"] = None

            gc.collect()
            try:
                import torch  # type: ignore

                torch.cuda.empty_cache()
            except ImportError:
                pass

        # Instancia o novo modelo
        transcriber = Transcriber(
            model_size=model_size,
            language="pt",
            device=device,
            compute_type=compute_type,
        )
        _transcriber_cache["key"] = key
        _transcriber_cache["instance"] = transcriber
        return transcriber


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve a interface web estática."""
    index_path = _STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="interface web não encontrada")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form("base"),
    language: str = Form("pt"),
    device: str = Form("auto"),
    compute_type: str = Form("default"),
    beam_size: int = Form(5),
    vad: bool = Form(False),
) -> JSONResponse:
    """Transcreve um arquivo de áudio/vídeo enviado via multipart/form-data.

    Endpoint mantido para compatibilidade retroativa com a CLI anterior.
    """
    resolved_language: Optional[str] = None if language == "auto" else language

    transcriber = _get_transcriber(model, device, compute_type)

    original_name = file.filename or "audio"
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / f"upload{suffix}"

        # Streaming do UploadFile para arquivo temporário
        with open(tmp_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                buffer.write(chunk)

        try:
            segments = await run_in_threadpool(
                transcriber.transcribe_file,
                str(tmp_path),
                beam_size=beam_size,
                vad_filter=vad,
                language=resolved_language,
            )
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=500, detail=f"falha na transcrição: {exc}"
            ) from exc

    full_text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
    srt_content = to_srt(segments)

    return JSONResponse(
        {
            "filename": stem,
            "text": full_text,
            "srt": srt_content,
        }
    )


@app.post("/api/transcribe/stream")
async def transcribe_stream(
    file: UploadFile = File(...),
    model: str = Form("base"),
    language: str = Form("pt"),
    device: str = Form("auto"),
    compute_type: str = Form("default"),
    beam_size: int = Form(5),
    vad: bool = Form(False),
) -> StreamingResponse:
    """Transcreve via Server-Sent Events, emitindo progresso em tempo real.

    Recebe os mesmos campos multipart/form-data de /api/transcribe, mas
    streama eventos (status, segment, done, error) para o cliente, evitando
    timeouts em arquivos longos.
    """
    resolved_language: Optional[str] = None if language == "auto" else language
    original_name = file.filename or "audio"
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix

    async def event_generator():
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / f"upload{suffix}"

            # Salva o upload em arquivo temporário (streaming por chunks)
            with open(tmp_path, "wb") as buffer:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    buffer.write(chunk)

            q: "queue.Queue[dict | None]" = queue.Queue()

            def on_progress(data: dict) -> None:
                q.put({"type": "segment", **data})

            def worker() -> None:
                try:
                    yield_status("Carregando modelo...")
                    transcriber = _get_transcriber(
                        model, device, compute_type
                    )
                    yield_status("Extraindo áudio...")
                    segments = transcriber.transcribe_file(
                        str(tmp_path),
                        beam_size=beam_size,
                        vad_filter=vad,
                        language=resolved_language,
                        on_progress=on_progress,
                    )
                    full_text = " ".join(
                        seg.text.strip() for seg in segments if seg.text.strip()
                    )
                    srt_content = to_srt(segments)
                    q.put(
                        {
                            "type": "done",
                            "filename": stem,
                            "text": full_text,
                            "srt": srt_content,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    q.put(
                        {
                            "type": "error",
                            "detail": f"falha na transcrição: {exc}",
                        }
                    )
                finally:
                    q.put(None)  # sentinel para encerrar o gerador

            def yield_status(message: str) -> None:
                q.put({"type": "status", "message": message})

            thread = threading.Thread(target=worker)
            thread.start()

            while True:
                item = q.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

            thread.join()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada do servidor web transcrita-web."""
    parser = argparse.ArgumentParser(
        prog="transcrita-web",
        description="Interface web local para transcrição de áudio e vídeo com transcrita.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host do servidor. Padrão: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Porta do servidor. Padrão: 8000",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Não abre o navegador automaticamente.",
    )
    args = parser.parse_args(argv)

    if not args.no_browser:
        url = f"http://{args.host}:{args.port}/"

        def _open_browser() -> None:
            webbrowser.open(url)

        threading.Timer(1.0, _open_browser).start()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
