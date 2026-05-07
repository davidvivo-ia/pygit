"""Pool de hilos para operaciones bloqueantes (pygit2, FS).

Usamos :class:`concurrent.futures.ThreadPoolExecutor` porque integra de
forma natural con :func:`asyncio.run_in_executor` y, vía ``qasync``, con el
event loop de Qt. Eso da semántica ``await`` para la VM sin tener que
emitir señales manualmente al final de cada worker.

Trade-off vs ``QThreadPool`` (la opción documentada inicialmente en
``docs/architecture.md``):

- A favor de ``ThreadPoolExecutor`` aquí: ergonomía ``await``, cancelación
  natural por ``asyncio.Task``, y desacople total de Qt en la API.
- A favor de ``QThreadPool``: cancelación cooperativa con ``QRunnable``,
  paridad de tooling Qt. Reevaluable en Fase 4 (rebase interactivo) si
  necesitamos cancelación granular en mitad de un walker.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")

DEFAULT_MAX_WORKERS = 4


class WorkerPool:
    """Pool propio de la app, separado del executor por defecto del loop."""

    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="pygit-worker",
        )

    async def submit(
        self,
        fn: Callable[P, R],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        """Ejecuta ``fn(*args, **kwargs)`` en un hilo y devuelve el resultado."""
        loop = asyncio.get_running_loop()
        bound = partial(fn, *args, **kwargs)
        return await loop.run_in_executor(self._executor, bound)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)


__all__ = ["DEFAULT_MAX_WORKERS", "WorkerPool"]
