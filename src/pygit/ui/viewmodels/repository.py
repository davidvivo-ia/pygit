"""ViewModel de un repositorio abierto.

Coordina llamadas al :class:`GitEngine` (en hilos worker) con la UI vía
señales Qt. La VM **no** ejecuta ``pygit2`` en el hilo UI: cualquier acceso
pasa por :meth:`WorkerPool.submit`.

Las señales emiten objetos del dominio (``HeadInfo``, listas de refs y
``CommitSummary``). Los modelos Qt (``QAbstractTableModel``, etc.) viven
en :mod:`pygit.ui.widgets`; la VM no los conoce para mantener separación.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from pathlib import Path

    from pygit.domain.git.engine import GitEngine
    from pygit.domain.git.models import (
        BranchRef,
        CommitSummary,
        HeadInfo,
        RemoteRef,
        TagRef,
    )
    from pygit.infra.workers import WorkerPool


class RepositoryVM(QObject):
    """Estado y operaciones de un repositorio en la UI."""

    head_changed = Signal(object)  # HeadInfo
    branches_changed = Signal(list)  # list[BranchRef]
    tags_changed = Signal(list)  # list[TagRef]
    remotes_changed = Signal(list)  # list[RemoteRef]
    history_changed = Signal(list)  # list[CommitSummary]
    path_changed = Signal(object)  # Path | None
    error = Signal(str)

    def __init__(self, engine: GitEngine, workers: WorkerPool) -> None:
        super().__init__()
        self._engine = engine
        self._workers = workers
        self._path: Path | None = None
        self._head: HeadInfo | None = None

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def head(self) -> HeadInfo | None:
        return self._head

    async def open(self, path: Path) -> None:
        try:
            resolved = await self._workers.submit(self._engine.discover, path)
        except Exception as exc:  # superficie pública: traduce a señal
            self.error.emit(str(exc))
            return
        self._path = resolved
        self.path_changed.emit(resolved)
        await self.refresh()

    async def refresh(self) -> None:
        if self._path is None:
            return
        path = self._path
        try:
            head: HeadInfo = await self._workers.submit(self._engine.head, path)
            branches: list[BranchRef] = await self._workers.submit(self._engine.branches, path)
            tags: list[TagRef] = await self._workers.submit(self._engine.tags, path)
            remotes: list[RemoteRef] = await self._workers.submit(self._engine.remotes, path)
            history: list[CommitSummary] = await self._workers.submit(
                self._engine.walk_history, path
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return

        self._head = head
        self.head_changed.emit(head)
        self.branches_changed.emit(branches)
        self.tags_changed.emit(tags)
        self.remotes_changed.emit(remotes)
        self.history_changed.emit(history)


__all__ = ["RepositoryVM"]
