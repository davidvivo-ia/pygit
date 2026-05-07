"""Wrapper async sobre el binario ``git``.

Reservado para operaciones que ``libgit2``/``pygit2`` no cubren con paridad
estable: ``rebase -i``, hooks de usuario, ``git lfs``, ``git flow``, worktrees,
bisect. Para todo lo demás, usar :class:`GitEngine`.

Diseño:

- Sin estado por instancia más allá del path del ejecutable.
- ``run`` lanza ``GitCliError`` si ``returncode != 0``.
- Decodificación tolerante (``errors="replace"``) para evitar petes con
  mensajes de commit en encodings raros (común en repos legacy).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pygit.domain.git.errors import GitCliError
from pygit.domain.git.version import GitVersion

if TYPE_CHECKING:
    from pathlib import Path


class GitCli:
    """Cliente async del binario ``git``."""

    def __init__(self, executable: str = "git") -> None:
        self._exe = executable

    @property
    def executable(self) -> str:
        return self._exe

    async def run(
        self,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        """Ejecuta ``git <args>`` en ``cwd``. Devuelve ``(stdout, stderr)``."""
        proc = await asyncio.create_subprocess_exec(
            self._exe,
            *args,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise GitCliError(proc.returncode or -1, stderr, (self._exe, *args))
        return stdout, stderr

    async def version(self) -> GitVersion:
        """Devuelve la versión del binario detectado."""
        stdout, _ = await self.run("--version")
        return GitVersion.parse(stdout)


__all__ = ["GitCli"]
