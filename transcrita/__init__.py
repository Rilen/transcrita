"""transcrita - CLI para transcrição local de áudio e vídeo em português."""

from __future__ import annotations

import logging
import sys

__version__ = "0.1.0"

# Garante que eventos INFO+ dos módulos transcrita.* sejam emitidos no stderr
# (capturado pelo journald quando rodando via systemd) sem depender da
# configuração de logging do uvicorn/pytest. O handler fica no logger pai
# "transcrita" e propagate=False evita registros duplicados caso o root
# receba handlers de terceiros.
_pkg_logger = logging.getLogger("transcrita")
if not _pkg_logger.handlers:
    _handler = logging.StreamHandler(stream=sys.stderr)
    _handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    _pkg_logger.addHandler(_handler)
_pkg_logger.setLevel(logging.INFO)
_pkg_logger.propagate = False
