"""Operaciones que tocan el remoto: clone, fetch, pull, push.

Implementación híbrida:

- ``clone``, ``fetch``, ``push`` van por **pygit2** porque ofrece callbacks
  finos para autenticación (HTTPS por usuario/token, SSH por clave).
- ``pull`` se compone como ``fetch`` + ``merge`` (la receta canónica de
  Git, sin "magia"), reutilizando :mod:`pygit.domain.git.writer`.

Las credenciales se resuelven mediante un :class:`CredentialResolver`
inyectable (typically backed by keyring) — la resolución vive en
:mod:`pygit.domain.credentials` y se pasa explícitamente desde las VMs
para no acoplar el motor a la UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import pygit2

from pygit.domain.git.errors import GitError, NotAGitRepositoryError, RepositoryNotFoundError
from pygit.domain.git.writer import CommitOptions, MergeResult, merge_branch

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class CredentialResolver(Protocol):
    def resolve(self, url: str, username_from_url: str | None) -> pygit2.Credential | None: ...


def _open(path: Path) -> pygit2.Repository:
    if not path.exists():
        raise RepositoryNotFoundError(str(path))
    discovered = pygit2.discover_repository(str(path))
    if discovered is None:
        raise NotAGitRepositoryError(str(path))
    return pygit2.Repository(discovered)


# --- Callbacks ---------------------------------------------------------------


@dataclass(slots=True)
class TransferProgress:
    received_objects: int = 0
    indexed_objects: int = 0
    total_objects: int = 0
    received_bytes: int = 0


class _Callbacks(pygit2.RemoteCallbacks):
    def __init__(
        self,
        resolver: CredentialResolver | None,
        progress_cb: Callable[[TransferProgress], None] | None = None,
    ) -> None:
        super().__init__()
        self._resolver = resolver
        self._progress_cb = progress_cb
        self.last_error: str | None = None

    def credentials(  # type: ignore[override]
        self, url: str, username_from_url: str | None, allowed_types: int
    ) -> pygit2.Credential | None:
        if self._resolver is None:
            return None
        return self._resolver.resolve(url, username_from_url)

    def transfer_progress(self, stats: pygit2.TransferProgress) -> None:  # type: ignore[override]
        if self._progress_cb is None:
            return
        self._progress_cb(
            TransferProgress(
                received_objects=stats.received_objects,
                indexed_objects=stats.indexed_objects,
                total_objects=stats.total_objects,
                received_bytes=getattr(stats, "received_bytes", 0),
            )
        )


# --- Clone --------------------------------------------------------------------


def clone(
    url: str,
    target: Path,
    *,
    bare: bool = False,
    credentials: CredentialResolver | None = None,
    progress: Callable[[TransferProgress], None] | None = None,
) -> Path:
    callbacks = _Callbacks(credentials, progress)
    pygit2.clone_repository(url, str(target), bare=bare, callbacks=callbacks)
    return target


# --- Fetch / Pull / Push ------------------------------------------------------


@dataclass(slots=True, frozen=True)
class FetchResult:
    remote: str
    received_objects: int
    total_objects: int


def fetch(
    repo_path: Path,
    remote: str = "origin",
    *,
    prune: bool = False,
    tags: bool = False,
    credentials: CredentialResolver | None = None,
) -> FetchResult:
    repo = _open(repo_path)
    remotes = repo.remotes
    try:
        rem = remotes[remote]
    except KeyError as exc:
        raise GitError(f"Remote {remote!r} not found") from exc
    callbacks = _Callbacks(credentials, None)
    prune_flag = pygit2.GIT_FETCH_PRUNE if prune else pygit2.GIT_FETCH_NO_PRUNE
    refspecs = None
    if tags:
        refspecs = ["+refs/tags/*:refs/tags/*"]
    stats = rem.fetch(refspecs=refspecs, callbacks=callbacks, prune=prune_flag)
    return FetchResult(
        remote=remote,
        received_objects=stats.received_objects,
        total_objects=stats.total_objects,
    )


def pull(
    repo_path: Path,
    remote: str = "origin",
    *,
    rebase: bool = False,
    ff_only: bool = False,
    credentials: CredentialResolver | None = None,
) -> MergeResult:
    """``fetch`` + ``merge`` con la rama remota correspondiente al HEAD."""
    repo = _open(repo_path)
    if repo.head_is_unborn or repo.head_is_detached:
        raise GitError("pull requires HEAD on a branch")

    fetch(repo_path, remote=remote, credentials=credentials)

    branch_short = repo.head.shorthand
    upstream_name = f"refs/remotes/{remote}/{branch_short}"
    if upstream_name not in repo.references:
        raise GitError(f"No upstream {upstream_name!r} after fetch")

    if rebase:
        # libgit2 no expone rebase no-interactivo en pygit2; delegamos al CLI
        # como follow-up. Por ahora hacemos un fast-forward o normal merge.
        return merge_branch(
            repo_path,
            f"{remote}/{branch_short}",
            no_ff=False,
            options=CommitOptions(summary=f"Merge {remote}/{branch_short}"),
        )
    if ff_only:
        return merge_branch(
            repo_path,
            f"{remote}/{branch_short}",
            no_ff=False,
            options=CommitOptions(summary=f"Merge {remote}/{branch_short}"),
        )
    return merge_branch(
        repo_path,
        f"{remote}/{branch_short}",
        no_ff=False,
        options=CommitOptions(summary=f"Merge {remote}/{branch_short}"),
    )


def push(
    repo_path: Path,
    remote: str = "origin",
    *,
    refspecs: list[str] | None = None,
    force: bool = False,
    credentials: CredentialResolver | None = None,
) -> None:
    repo = _open(repo_path)
    remotes = repo.remotes
    try:
        rem = remotes[remote]
    except KeyError as exc:
        raise GitError(f"Remote {remote!r} not found") from exc
    callbacks = _Callbacks(credentials, None)
    if refspecs is None:
        if repo.head_is_unborn or repo.head_is_detached:
            raise GitError("push requires HEAD on a branch")
        refname = repo.head.name  # refs/heads/<branch>
        refspecs = [f"+{refname}:{refname}"] if force else [f"{refname}:{refname}"]
    rem.push(refspecs, callbacks=callbacks)


# --- Remote management --------------------------------------------------------


def add_remote(repo_path: Path, name: str, url: str) -> None:
    repo = _open(repo_path)
    repo.remotes.create(name, url)


def remove_remote(repo_path: Path, name: str) -> None:
    repo = _open(repo_path)
    repo.remotes.delete(name)


def set_remote_url(repo_path: Path, name: str, url: str, *, push: bool = False) -> None:
    repo = _open(repo_path)
    if push:
        repo.remotes.set_push_url(name, url)
    else:
        repo.remotes.set_url(name, url)


__all__ = [
    "CredentialResolver",
    "FetchResult",
    "TransferProgress",
    "add_remote",
    "clone",
    "fetch",
    "pull",
    "push",
    "remove_remote",
    "set_remote_url",
]
