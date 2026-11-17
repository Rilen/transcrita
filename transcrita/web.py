"""Interface web local para transcrita usando FastAPI."""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import queue
import re
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

from transcrita import __version__
from transcrita.core import Transcriber
from transcrita.srt import to_srt
from transcrita.asr import (
    engine_metadata,
    list_engines,
    parakeet_availability,
    parakeet_enabled,
    parakeet_weights_path,
)

logger = logging.getLogger("transcrita.web")

# Configuração de limites de upload (bytes) - compatível com nginx proxy 512MB
MAX_UPLOAD_SIZE = 512 * 1024 * 1024  # 512 MB

_UPLOAD_PATHS = ("/api/transcribe", "/api/transcribe/stream")
_PATH_RE = re.compile(r"(?<![\w:/])/(?:[^\s'\"<>]+)(?:/[^\s'\"<>]*)?")


def _sanitize_error(exc: object) -> str:
    """Mensagem pública sem caminhos absolutos; detalhe completo vai ao log."""
    msg = str(exc).replace("\n", " ").strip()
    msg = _PATH_RE.sub("[caminho]", msg)
    return msg[:300]

# Semáforo global para serialização de inferências (máximo 1 concorrente)
# Pode ser substituído em testes (ex.: por um mock ou threading.Semaphore(100))
_inference_semaphore: threading.Semaphore = threading.Semaphore(1)

# Teto de corrotinas aguardando a vaga simultaneamente. Impede acúmulo
# ilimitado de threads de espera (controle de concorrência/DoS).
MAX_SLOT_WAITERS = 16
_slot_waiters_lock = threading.Lock()
_slot_waiters = 0


def _slot_waiters_enter() -> bool:
    """Registra um esperador de vaga; False quando o teto foi atingido."""
    global _slot_waiters
    with _slot_waiters_lock:
        if _slot_waiters >= MAX_SLOT_WAITERS:
            return False
        _slot_waiters += 1
        return True


def _slot_waiters_leave() -> None:
    global _slot_waiters
    with _slot_waiters_lock:
        if _slot_waiters > 0:
            _slot_waiters -= 1


async def _acquire_inference_slot(timeout: float = 300.0) -> bool:
    """Adquire a vaga global de inferência sem bloquear o event loop.

    Contrato de propriedade:
    - A espera acontece em thread dedicada (event loop permanece livre).
    - Cancelamento antes da concessão: a coroutine é cancelada e uma
      concessão tardia é devolvida imediatamente ao semáforo, sem vazamento.
    - Concessão entregue: o chamador é dono da vaga e deve liberá-la.
    """
    if not _slot_waiters_enter():
        logger.warning("inference_slot_waiters_limit", extra={"max": MAX_SLOT_WAITERS})
        return False

    loop = asyncio.get_running_loop()
    future: "asyncio.Future[bool]" = loop.create_future()

    def _deliver(acquired: bool) -> None:
        # Executa sempre no thread do event loop: sem corrida com o cancelamento.
        if future.done():
            # A coroutine já não existe (cancelada). Devolve concessão tardia.
            if acquired:
                _inference_semaphore.release()
                logger.warning("inference_slot_late_grant_released")
            return
        future.set_result(acquired)

    def _worker() -> None:
        acquired = False
        try:
            acquired = _inference_semaphore.acquire(timeout=timeout)
        finally:
            try:
                loop.call_soon_threadsafe(_deliver, acquired)
            except RuntimeError:
                # Event loop encerrado durante a espera: não vazar a vaga.
                if acquired:
                    _inference_semaphore.release()
                logger.warning("inference_slot_loop_closed")
            finally:
                _slot_waiters_leave()

    threading.Thread(
        target=_worker, daemon=True, name="transcrita-slot-acquire"
    ).start()

    return await future


class UploadSizeLimitMiddleware:
    """Limite efetivo de upload (Content-Length e corpos chunked).

    - Rejeita cedo quando Content-Length excede o limite.
    - Para corpos sem Content-Length (chunked), conta bytes no receive e
      levanta HTTP 413 sem bufferizar o corpo integral em memória.
    """

    def __init__(self, app):
        self.app = app

    async def _reject(self, send) -> None:
        body = json.dumps(
            {"detail": f"Arquivo excede o limite de {MAX_UPLOAD_SIZE // (1024 * 1024)} MB"}
        ).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        })
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") not in _UPLOAD_PATHS:
            return await self.app(scope, receive, send)

        headers = {k.lower(): v for k, v in (scope.get("headers") or [])}
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                if int(declared) > MAX_UPLOAD_SIZE:
                    logger.warning(
                        "upload_rejected_content_length",
                        extra={"content_length": int(declared), "max": MAX_UPLOAD_SIZE,
                               "path": scope.get("path")},
                    )
                    return await self._reject(send)
            except ValueError:
                pass

        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            if message.get("type") == "http.request":
                total += len(message.get("body", b"") or b"")
                if total > MAX_UPLOAD_SIZE:
                    logger.warning(
                        "upload_rejected_chunked",
                        extra={"bytes_received": total, "max": MAX_UPLOAD_SIZE,
                               "path": scope.get("path")},
                    )
                    raise HTTPException(
                        status_code=413,
                        detail=f"Arquivo excede o limite de {MAX_UPLOAD_SIZE // (1024 * 1024)} MB",
                    )
            return message

        await self.app(scope, limited_receive, send)


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

# Vaga única de modelo: Whisper e Parakeet nunca ficam carregados ao mesmo tempo.
_model_switch_lock = threading.Lock()
_parakeet_lock = threading.Lock()
_parakeet_cache: dict = {"key": None, "instance": None}


def _evict_whisper() -> None:
    freed = False
    with _transcriber_lock:
        if _transcriber_cache["instance"] is not None:
            _transcriber_cache["key"] = None
            _transcriber_cache["instance"] = None
            freed = True
    if freed:
        gc.collect()


def _evict_parakeet() -> None:
    with _parakeet_lock:
        instance = _parakeet_cache["instance"]
        _parakeet_cache["key"] = None
        _parakeet_cache["instance"] = None
    if instance is not None:
        try:
            instance.unload()
        except Exception:  # noqa: BLE001
            logger.warning("parakeet_unload_failed", exc_info=True)
        finally:
            gc.collect()


def _get_parakeet_engine(model: str = "pt-br-int8") -> object:
    """Retorna o motor Parakeet em cache (single-model), criando se necessário."""
    key = ("parakeet", model)
    with _model_switch_lock:
        _evict_whisper()
        with _parakeet_lock:
            if _parakeet_cache["key"] == key and _parakeet_cache["instance"] is not None:
                return _parakeet_cache["instance"]
            from transcrita.asr.parakeet import ParakeetEngine

            engine = ParakeetEngine(parakeet_weights_path())
            _parakeet_cache["key"] = key
            _parakeet_cache["instance"] = engine
            return engine


def _get_engine(engine_id: str, model: str, device: str, compute_type: str) -> object:
    if engine_id == "parakeet":
        return _get_parakeet_engine(model)
    return _get_transcriber(model, device, compute_type)


def _resolve_engine(engine_id: str, model: str) -> None:
    """Valida o motor solicitado; erros explícitos, sem fallback silencioso."""
    if engine_id not in ("whisper", "parakeet"):
        raise HTTPException(status_code=400, detail=f"motor desconhecido: {engine_id}")
    if engine_id == "parakeet":
        if not parakeet_enabled():
            raise HTTPException(
                status_code=403,
                detail="Parakeet desabilitado (TRANSCRITA_ENABLE_PARAKEET=false)",
            )
        ok, reason = parakeet_availability()
        if not ok:
            raise HTTPException(status_code=503, detail=f"Parakeet indisponível: {reason}")
        if model != "pt-br-int8":
            raise HTTPException(
                status_code=400,
                detail="Parakeet aceita somente o modelo pt-br-int8",
            )


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

    with _model_switch_lock:
        _evict_parakeet()
        with _transcriber_lock:
            current_key = _transcriber_cache["key"]
            current_instance = _transcriber_cache["instance"]

            if current_key == key and current_instance is not None:
                return current_instance

        # Evicção do modelo anterior
        with _transcriber_lock:
            if current_instance is not None:
                _transcriber_cache["key"] = None
                _transcriber_cache["instance"] = None
        if current_instance is not None:
            del current_instance
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
        with _transcriber_lock:
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


@app.get("/api/engines")
async def engines() -> JSONResponse:
    """Lista motores, modelos, disponibilidade e limitações."""
    return JSONResponse({"engines": list_engines()})


@app.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    engine: str = Form("whisper"),
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
    _resolve_engine(engine, model)

    start_wall = time.perf_counter()

    # Serialização global de inferências (espera em thread dedicada,
    # sem bloquear o event loop e sem vazar a vaga em caso de cancelamento).
    acquired = await _acquire_inference_slot(timeout=300)
    if not acquired:
        raise HTTPException(status_code=503, detail="Servidor ocupado, tente novamente")

    try:
        transcriber = _get_engine(engine, model, device, compute_type)

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
                    status_code=500, detail=f"falha na transcrição: {_sanitize_error(exc)}"
                ) from exc

        full_text = " ".join(seg.text.strip() for seg in segments if seg.text.strip())
        srt_content = to_srt(segments)

        elapsed = time.perf_counter() - start_wall
        meta = engine_metadata(engine, model)
        logger.info(
            "transcricao_concluida",
            extra={
                "arquivo": original_name,
                "motor": engine,
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
                **meta,
            }
        )
    finally:
        _inference_semaphore.release()


@app.post("/api/transcribe/stream")
async def transcribe_stream(
    request: Request,
    file: UploadFile = File(...),
    engine: str = Form("whisper"),
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
    _resolve_engine(engine, model)
    meta = engine_metadata(engine, model)
    original_name = file.filename or "audio"
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    start_wall = time.perf_counter()

    cancel_event = threading.Event()
    worker_finished = threading.Event()
    semaphore_acquired = False

    async def event_generator():
        nonlocal semaphore_acquired
        # Serialização global de inferências (espera em thread dedicada,
        # sem bloquear o event loop e sem vazar a vaga em caso de cancelamento).
        acquired = await _acquire_inference_slot(timeout=300)
        if not acquired:
            yield f"data: {json.dumps({'type': 'error', 'detail': 'Servidor ocupado, tente novamente'}, ensure_ascii=False)}\n\n"
            return

        semaphore_acquired = True
        worker_started = False

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
                    nonlocal worker_started
                    try:
                        worker_started = True
                        yield_status(f"Carregando {meta['engine_name']} ({meta['model_label']})...")
                        transcriber = _get_engine(engine, model, device, compute_type)
                        yield_status(
                            "Segmentando áudio (VAD)..." if engine == "parakeet" else "Extraindo áudio..."
                        )
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
                            q.put({"type": "cancelled", "filename": stem, **meta})
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
                                    **meta,
                                }
                            )
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("sse_transcricao_falhou", extra={"erro": str(exc)})
                        if not cancel_event.is_set():
                            q.put(
                                {
                                    "type": "error",
                                    "detail": f"falha na transcrição: {_sanitize_error(exc)}",
                                    **meta,
                                }
                            )
                    finally:
                        worker_finished.set()
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
                        # NÃO libera semáforo aqui - apenas sinaliza cancelamento
                        # O semáforo será liberado quando o worker terminar (finally)
                        try:
                            cancelled_event = json.dumps(
                                {"type": "cancelled", "filename": stem, **meta},
                                ensure_ascii=False,
                            )
                            yield f"data: {cancelled_event}\n\n"
                        except Exception:
                            pass
                        break

                    # Non-blocking queue get via asyncio.to_thread
                    try:
                        item = await asyncio.to_thread(q.get, timeout=0.5)
                    except queue.Empty:
                        # Timeout temporário da fila - continua aguardando eventos
                        continue
                    except asyncio.CancelledError:
                        # Coroutine cancelada durante espera na fila
                        cancel_event.set()
                        raise
                    except Exception:
                        # Qualquer outro erro na leitura da fila
                        continue
                    if item is None:
                        break
                    yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

                # Aguarda worker terminar (já deve ter terminado se chegou aqui)
                try:
                    await asyncio.to_thread(thread.join, timeout=5.0)
                except asyncio.CancelledError:
                    cancel_event.set()
                    raise
        finally:
            # A vaga nunca é liberada antes de o worker terminar de fato.
            # Sem await aqui: seguro mesmo se o gerador for cancelado.
            if semaphore_acquired:
                semaphore_acquired = False
                if worker_finished.is_set():
                    _inference_semaphore.release()
                else:
                    def _release_after_worker() -> None:
                        # Espera sem limite: a capacidade permanece
                        # indisponível até o worker finalizar.
                        worker_finished.wait()
                        _inference_semaphore.release()
                        logger.info("inference_slot_released_after_worker_exit")

                    threading.Thread(
                        target=_release_after_worker,
                        daemon=True,
                        name="transcrita-slot-release",
                    ).start()

    elapsed = time.perf_counter() - start_wall
    logger.info(
        "sse_iniciado",
        extra={
            "arquivo": original_name,
            "motor": engine,
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
