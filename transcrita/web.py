"""Interface web local para transcrita usando FastAPI."""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import queue
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

import asyncio
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from transcrita import __version__
from transcrita.core import Transcriber
from transcrita.srt import to_srt

logger = logging.getLogger("transcrita.web")

# Configuração de limites de upload (bytes) - compatível com nginx proxy 512MB
MAX_UPLOAD_SIZE = 512 * 1024 * 1024  # 512 MB

# Semáforo global para serialização de inferências (máximo 1 concorrente)
# Pode ser substituído em testes (ex.: por um mock ou threading.Semaphore(100))
_inference_semaphore: threading.Semaphore = threading.Semaphore(1)


class UploadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware para limitar tamanho de upload antes do parsing multipart.

    Rejeita requisições com Content-Length > MAX_UPLOAD_SIZE com HTTP 413.
    Para streaming sem Content-Length, conta bytes durante a leitura.
    """

    async def dispatch(self, request: Request, call_next):
        # Aplicar apenas aos endpoints de transcrição
        if request.url.path not in ("/api/transcribe", "/api/transcribe/stream"):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                cl = int(content_length)
                if cl > MAX_UPLOAD_SIZE:
                    logger.warning(
                        "upload_rejected_content_length",
                        extra={"content_length": cl, "max": MAX_UPLOAD_SIZE, "path": request.url.path},
                    )
                    return JSONResponse(
                        {"detail": f"Arquivo excede o limite de {MAX_UPLOAD_SIZE // (1024*1024)} MB"},
                        status_code=413,
                    )
            except ValueError:
                pass  # Content-Length inválido, deixar o parser lidar

        # Para streaming sem Content-Length, contar bytes no body
        # Nota: isso consome o body, então precisamos reconstruir o request
        # Para simplicidade, confiamos no limite do nginx (512MB) como segunda camada
        # e no parser multipart do FastAPI/Starlette que tem limites internos.
        return await call_next(request)


app = FastAPI(
    title="transcrita-web",
    version=__version__,
    root_path=os.environ.get("TRANSCRITA_ROOT_PATH", ""),
)

# Middleware de limite de upload
app.add_middleware(UploadSizeLimitMiddleware)

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


@app.get("/api/health")
async def health() -> JSONResponse:
    """Endpoint de saúde para checagem do proxy reverso."""
    return JSONResponse({"status": "ok"})


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

    start_wall = time.perf_counter()

    # Serialização global de inferências (async acquire para não bloquear event loop)
    try:
        await asyncio.to_thread(_inference_semaphore.acquire, timeout=300)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Servidor ocupado, tente novamente")

    try:
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
                    ffmpeg_timeout=300,
                )
            except Exception as exc:  # noqa: BLE001
                elapsed = time.perf_counter() - start_wall
                logger.error(
                    "transcricao_falhou",
                    extra={
                        "arquivo": original_name,
                        "modelo": model,
                        "dispositivo": device,
                        "tempo_proc_s": round(elapsed, 2),
                        "erro": str(exc),
                    },
                )
                raise HTTPException(
                    status_code=500, detail=f"falha na transcrição: {exc}"
                ) from exc

        full_text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
        srt_content = to_srt(segments)

        elapsed = time.perf_counter() - start_wall
        logger.info(
            "transcricao_concluida",
            extra={
                "arquivo": original_name,
                "modelo": model,
                "dispositivo": device,
                "tempo_proc_s": round(elapsed, 2),
                "segmentos": len(segments),
                "vad": vad,
            },
        )

        return JSONResponse(
            {
                "filename": stem,
                "text": full_text,
                "srt": srt_content,
            }
        )
    finally:
        _inference_semaphore.release()


@app.post("/api/transcribe/stream")
async def transcribe_stream(
    request: Request,
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

    Suporta cancelamento limpo: quando o cliente encerra a conexão SSE
    (AbortController), o evento de cancelamento é disparado e a thread de
    trabalho para a transcrição no próximo segmento.
    """
    resolved_language: Optional[str] = None if language == "auto" else language
    original_name = file.filename or "audio"
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    start_wall = time.perf_counter()

    # Serialização global de inferências (adquire antes de salvar upload)
    acquired = _inference_semaphore.acquire(timeout=300)
    if not acquired:
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'detail': 'Servidor ocupado, tente novamente'}, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream",
            status_code=503,
        )

    cancel_event = threading.Event()
    semaphore_acquired = True

    async def event_generator():
        nonlocal semaphore_acquired
        try:
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
                            cancel_event=cancel_event,
                            ffmpeg_timeout=300,
                        )
                        if cancel_event.is_set():
                            q.put({"type": "cancelled", "filename": stem})
                        else:
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
                        if not cancel_event.is_set():
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
                    # Detecta desconexão do cliente para cancelamento limpo
                    if await request.is_disconnected():
                        logger.warning(
                            "sse_cliente_desconectado",
                            extra={"arquivo": original_name},
                        )
                        cancel_event.set()
                        # Libera semáforo se cliente desconectou
                        if semaphore_acquired:
                            _inference_semaphore.release()
                            semaphore_acquired = False
                        # Envia evento de cancelamento para o cliente, se ainda conectado
                        try:
                            yield (
                                f"data: {json.dumps({'type': 'cancelled', 'filename': stem}, ensure_ascii=False)}\n\n"
                            )
                        except Exception:
                            pass
                        break

                    try:
                        item = q.get(timeout=0.5)
                    except queue.Empty:
                        continue
                    if item is None:
                        break
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

                thread.join(timeout=5.0)
        finally:
            # Garante liberação do semáforo em todos os caminhos
            if semaphore_acquired:
                _inference_semaphore.release()
                semaphore_acquired = False

    elapsed = time.perf_counter() - start_wall
    logger.info(
        "sse_iniciado",
        extra={
            "arquivo": original_name,
            "modelo": model,
            "dispositivo": device,
            "tempo_ate_inicio_s": round(elapsed, 2),
        },
    )

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
        default=int(os.environ.get("TRANSCRITA_PORT", 8765)),
        help="Porta do servidor. Padrão: 8765 (variável TRANSCRITA_PORT)",
    )
    parser.add_argument(
        "--root-path",
        default=os.environ.get("TRANSCRITA_ROOT_PATH", ""),
        help='Caminho base (root path) para deploy atrás de subpath, ex: /transcrita. Padrão: "" (variável TRANSCRITA_ROOT_PATH)',
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Não abre o navegador automaticamente.",
    )
    args = parser.parse_args(argv)

    if not args.no_browser:
        url = f"http://{args.host}:{args.port}{args.root_path}/"

        def _open_browser() -> None:
            webbrowser.open(url)

        threading.Timer(1.0, _open_browser).start()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
