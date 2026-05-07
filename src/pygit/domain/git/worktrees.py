"""Soporte de worktrees.

pygit2 expone una API de worktree, pero su superficie es limitada
(no incluye ``prune``). Mezclamos pygit2 (listar, añadir) con CLI
(``prune``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pygit2

from pygit.domain.git.errors import GitError, NotAGitRepositoryError, RepositoryNotFoundError

if TYPE_CHECKING:
    from pygit.domain.git.cli import GitCli


@dataclass(slots=True, frozen=True)
class Worktree:
    name: str
    path: Path
    is_locked: bool


def _open(path: Path) -> pygit2.Repository:
    if not path.exists():
        raise RepositoryNotFoundError(str(path))
    discovered = pygit2.discover_repository(str(path))
    if discovered is None:
        raise NotAGitRepositoryError(str(path))
    return pygit2.Repository(discovered)


def list_worktrees(repo_path: Path) -> list[Worktree]:
    repo = _open(repo_path)
    out: list[Worktree] = []
    for name in repo.list_worktrees():
        wt = repo.lookup_worktree(name)
        out.append(
            Worktree(
                name=name,
                path=Path(wt.path),
                is_locked=bool(wt.is_locked),
            )
        )
    return out


def add_worktree(repo_path: Path, name: str, path: Path, ref: str | None = None) -> None:
    repo = _open(repo_path)
    if ref is not None:
        ref_obj = repo.references.get(ref) or repo.references.get(f"refs/heads/{ref}")
        if ref_obj is None:
            raise GitError(f"Ref {ref!r} not found")
        repo.add_worktree(name, str(path), ref_obj)
    else:
        repo.add_worktree(name, str(path))


def remove_worktree(repo_path: Path, name: str) -> None:
    repo = _open(repo_path)
    wt = repo.lookup_worktree(name)
    wt.prune()


async def prune(cli: GitCli, repo_path: Path) -> None:
    await cli.run("worktree", "prune", cwd=repo_path)


__all__ = ["Worktree", "add_worktree", "list_worktrees", "prune", "remove_worktree"]
