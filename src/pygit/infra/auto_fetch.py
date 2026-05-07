"""Timer de auto-fetch.

``QTimer`` con intervalo configurable que dispara una callback async cada
N minutos. Cancelable; ignora errores de red sin spamear el statusbar
(sólo loggea).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog
from PySide6.QtCore import QObject, QTimer

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine


_log = structlog.get_logger()


class AutoFetcher(QObject):
    DEFAULT_INTERVAL_MS = 5 * 60 * 1000

    def __init__(
        self,
        callback: Callable[[], Coroutine[Any, Any, None]],
        *,
        interval_ms: int = DEFAULT_INTERVAL_MS,
    ) -> None:
        super().__init__()
        self._callback = callback
        self._tasks: set[asyncio.Task[None]] = set()
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_interval_ms(self, ms: int) -> None:
        self._timer.setInterval(ms)

    def _tick(self) -> None:
        async def _run() -> None:
            try:
                await self._callback()
            except Exception as exc:
                _log.warning("auto-fetch failed", error=str(exc))

        task = asyncio.ensure_future(_run())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


__all__ = ["AutoFetcher"]
