"""Excepciones de la capa Git."""

from __future__ import annotations


class GitError(Exception):
    """Raíz de errores específicos del dominio Git."""


class RepositoryNotFoundError(GitError):
    """La ruta indicada no existe en el filesystem."""


class NotAGitRepositoryError(GitError):
    """La ruta existe pero ``pygit2.discover_repository`` no encontró un repo."""


class GitCliError(GitError):
    """``git`` invocado desde subprocess devolvió código de error."""

    def __init__(self, returncode: int, stderr: str, command: tuple[str, ...]) -> None:
        cmd_str = " ".join(command)
        super().__init__(f"git {cmd_str} (exit {returncode}): {stderr.strip()}")
        self.returncode = returncode
        self.stderr = stderr
        self.command = command


__all__ = [
    "GitCliError",
    "GitError",
    "NotAGitRepositoryError",
    "RepositoryNotFoundError",
]
