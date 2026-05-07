"""Lectura del repositorio sobre ``pygit2``.

Diseño thread-safe pragmático: cada operación abre su propio
``pygit2.Repository`` localmente. Las instancias de ``Repository`` no son
seguras para compartir entre hilos en libgit2; el coste de re-abrir es bajo
comparado con el de leer commits/refs. Si al perfilar la Fase 1 turno 2
aparece overhead notable, se mueve a un único worker dedicado con
``Repository`` persistente.

La engine es **headless**: no importa Qt. Sus métodos se invocan desde la
:class:`pygit.infra.workers.WorkerPool`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pygit2

from pygit.domain.git.errors import NotAGitRepositoryError, RepositoryNotFoundError
from pygit.domain.git.models import (
    SHORT_SHA_LEN,
    BranchRef,
    CommitSummary,
    HeadInfo,
    RemoteRef,
    Signature,
    TagRef,
)

DEFAULT_HISTORY_LIMIT = 500


def _open(path: Path) -> pygit2.Repository:
    if not path.exists():
        raise RepositoryNotFoundError(str(path))
    discovered = pygit2.discover_repository(str(path))
    if discovered is None:
        raise NotAGitRepositoryError(str(path))
    return pygit2.Repository(discovered)


def _signature(sig: pygit2.Signature) -> Signature:
    tz = timezone(timedelta(minutes=sig.offset))
    when = datetime.fromtimestamp(sig.time, tz=tz)
    return Signature(name=sig.name, email=sig.email, when=when)


def _commit_summary(commit: pygit2.Commit) -> CommitSummary:
    sha = str(commit.id)
    message = commit.message
    summary = message.split("\n", 1)[0].rstrip()
    return CommitSummary(
        sha=sha,
        short_sha=sha[:SHORT_SHA_LEN],
        summary=summary,
        message=message,
        author=_signature(commit.author),
        committer=_signature(commit.committer),
        parents=tuple(str(parent) for parent in commit.parent_ids),
    )


class GitEngine:
    """Operaciones de lectura sobre un repositorio."""

    def discover(self, path: Path) -> Path:
        """Resuelve la ruta a workdir (no a ``.git``). Lanza si no es repo."""
        repo = _open(path)
        workdir = repo.workdir
        if workdir:
            return Path(workdir).resolve()
        return Path(repo.path).resolve()

    def head(self, repo_path: Path) -> HeadInfo:
        repo = _open(repo_path)
        if repo.head_is_unborn:
            return HeadInfo(
                is_detached=False,
                is_unborn=True,
                branch_name=None,
                target_sha="",
            )
        head = repo.head
        is_detached = repo.head_is_detached
        return HeadInfo(
            is_detached=is_detached,
            is_unborn=False,
            branch_name=None if is_detached else head.shorthand,
            target_sha=str(head.target),
        )

    def branches(self, repo_path: Path) -> list[BranchRef]:
        repo = _open(repo_path)
        result: list[BranchRef] = []
        for name in repo.branches.local:
            branch = repo.branches.local[name]
            upstream_name: str | None = None
            try:
                upstream = branch.upstream
            except (pygit2.GitError, KeyError):
                upstream = None
            if upstream is not None:
                upstream_name = upstream.shorthand
            result.append(
                BranchRef(
                    name=name,
                    full_name=f"refs/heads/{name}",
                    target_sha=str(branch.target),
                    is_remote=False,
                    upstream=upstream_name,
                )
            )
        for name in repo.branches.remote:
            branch = repo.branches.remote[name]
            result.append(
                BranchRef(
                    name=name,
                    full_name=f"refs/remotes/{name}",
                    target_sha=str(branch.target),
                    is_remote=True,
                )
            )
        return result

    def tags(self, repo_path: Path) -> list[TagRef]:
        repo = _open(repo_path)
        result: list[TagRef] = []
        for ref_name in repo.references:
            if not ref_name.startswith("refs/tags/"):
                continue
            ref = repo.references[ref_name]
            target_obj = repo.get(ref.target)
            short = ref_name.removeprefix("refs/tags/")
            if isinstance(target_obj, pygit2.Tag):
                msg = target_obj.message.strip() or None
                result.append(
                    TagRef(
                        name=short,
                        full_name=ref_name,
                        target_sha=str(target_obj.target),
                        is_annotated=True,
                        message=msg,
                    )
                )
            else:
                result.append(
                    TagRef(
                        name=short,
                        full_name=ref_name,
                        target_sha=str(ref.target),
                        is_annotated=False,
                    )
                )
        return result

    def remotes(self, repo_path: Path) -> list[RemoteRef]:
        repo = _open(repo_path)
        result: list[RemoteRef] = []
        for remote in repo.remotes:
            push_url: str | None = getattr(remote, "push_url", None)
            result.append(
                RemoteRef(
                    name=remote.name,
                    fetch_url=remote.url,
                    push_url=push_url,
                )
            )
        return result

    def walk_history(
        self,
        repo_path: Path,
        *,
        limit: int = DEFAULT_HISTORY_LIMIT,
        start: str | None = None,
    ) -> list[CommitSummary]:
        """Walker topológico+cronológico desde ``start`` (default: HEAD)."""
        repo = _open(repo_path)
        if start is None:
            if repo.head_is_unborn:
                return []
            start_oid = repo.head.target
        else:
            start_oid = pygit2.Oid(hex=start)
        sort = pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_TIME
        result: list[CommitSummary] = []
        for index, commit in enumerate(repo.walk(start_oid, sort)):
            if index >= limit:
                break
            result.append(_commit_summary(commit))
        return result


__all__ = ["DEFAULT_HISTORY_LIMIT", "GitEngine"]
