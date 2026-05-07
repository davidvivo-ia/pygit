"""Motor Git (pygit2 + git CLI híbrido). Implementación en Fase 1.

Tabla de decisión motor → operación (vivirá en docs/architecture.md):

- pygit2 (libgit2): walks, refs, blobs, status, index, blame, low-level diff.
- git CLI: ``rebase -i``, ``git lfs``, ``git flow``, hooks de usuario, comandos
  no expuestos por libgit2 con paridad estable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path


class GitEngine(Protocol):
    """API síncrona de alto nivel sobre pygit2. Llamadas se ejecutan en worker."""

    def open(self, path: Path) -> None: ...


class GitCli(Protocol):
    """Wrapper async sobre el binario ``git``."""

    async def run(self, *args: str, cwd: Path) -> tuple[int, str, str]: ...


__all__ = ["GitCli", "GitEngine"]
