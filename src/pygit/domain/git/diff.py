"""Motor de diff sobre pygit2.

Proporciona diffs textuales hunk + line para tres escenarios principales:

- ``diff_commit_to_parent``: commit vs su primer padre (default del log).
- ``diff_workdir_to_index``: cambios sin stage (WIP).
- ``diff_index_to_head``: cambios en stage.

Devuelve estructuras headless (sin Qt) que luego la view convierte en
side-by-side, unified, swipe o blend.

Para búsquedas pickaxe (``-S`` / ``-G``) y file-history con detección de
renames se delega al :class:`pygit.domain.git.cli.GitCli` porque libgit2
no expone ``--follow`` con paridad estable y pickaxe requiere el motor de
diff de Git (no su variante en libgit2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum
from typing import TYPE_CHECKING

import pygit2

from pygit.domain.git.errors import GitError, NotAGitRepositoryError, RepositoryNotFoundError
from pygit.domain.git.models import SHORT_SHA_LEN, CommitSummary, Signature

if TYPE_CHECKING:
    from pathlib import Path

    from pygit.domain.git.cli import GitCli


class FileStatus(StrEnum):
    ADDED = "A"
    DELETED = "D"
    MODIFIED = "M"
    RENAMED = "R"
    COPIED = "C"
    TYPECHANGE = "T"
    UNTRACKED = "U"
    BINARY = "B"


class LineOrigin(StrEnum):
    CONTEXT = " "
    ADDITION = "+"
    DELETION = "-"
    HEADER = "H"


@dataclass(slots=True, frozen=True)
class DiffLine:
    origin: LineOrigin
    content: str
    old_lineno: int | None
    new_lineno: int | None


@dataclass(slots=True, frozen=True)
class Hunk:
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    header: str
    lines: tuple[DiffLine, ...]


@dataclass(slots=True, frozen=True)
class FileDiff:
    old_path: str | None
    new_path: str | None
    status: FileStatus
    is_binary: bool
    additions: int
    deletions: int
    hunks: tuple[Hunk, ...] = field(default_factory=tuple)


@dataclass(slots=True, frozen=True)
class DiffResult:
    files: tuple[FileDiff, ...]

    @property
    def total_additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)


def _open(path: Path) -> pygit2.Repository:
    if not path.exists():
        raise RepositoryNotFoundError(str(path))
    discovered = pygit2.discover_repository(str(path))
    if discovered is None:
        raise NotAGitRepositoryError(str(path))
    return pygit2.Repository(discovered)


def _status_from_pygit2(delta_status: int) -> FileStatus:
    # libgit2 status enum to our enum (best-effort).
    mapping = {
        getattr(pygit2, "GIT_DELTA_ADDED", 1): FileStatus.ADDED,
        getattr(pygit2, "GIT_DELTA_DELETED", 2): FileStatus.DELETED,
        getattr(pygit2, "GIT_DELTA_MODIFIED", 3): FileStatus.MODIFIED,
        getattr(pygit2, "GIT_DELTA_RENAMED", 4): FileStatus.RENAMED,
        getattr(pygit2, "GIT_DELTA_COPIED", 5): FileStatus.COPIED,
        getattr(pygit2, "GIT_DELTA_TYPECHANGE", 8): FileStatus.TYPECHANGE,
        getattr(pygit2, "GIT_DELTA_UNTRACKED", 7): FileStatus.UNTRACKED,
    }
    return mapping.get(delta_status, FileStatus.MODIFIED)


def _convert_diff(diff: pygit2.Diff) -> DiffResult:
    files: list[FileDiff] = []
    for patch in diff:
        delta = patch.delta
        is_binary = bool(getattr(delta, "is_binary", False))
        old_path = delta.old_file.path if delta.old_file is not None else None
        new_path = delta.new_file.path if delta.new_file is not None else None
        status = _status_from_pygit2(int(delta.status)) if not is_binary else FileStatus.BINARY

        hunks_out: list[Hunk] = []
        additions = 0
        deletions = 0

        for hunk in patch.hunks:
            lines: list[DiffLine] = []
            for line in hunk.lines:
                origin_char = line.origin
                if origin_char == "+":
                    origin = LineOrigin.ADDITION
                    additions += 1
                elif origin_char == "-":
                    origin = LineOrigin.DELETION
                    deletions += 1
                else:
                    origin = LineOrigin.CONTEXT
                lines.append(
                    DiffLine(
                        origin=origin,
                        content=line.content.rstrip("\n"),
                        old_lineno=line.old_lineno if line.old_lineno > 0 else None,
                        new_lineno=line.new_lineno if line.new_lineno > 0 else None,
                    )
                )
            hunks_out.append(
                Hunk(
                    old_start=hunk.old_start,
                    old_lines=hunk.old_lines,
                    new_start=hunk.new_start,
                    new_lines=hunk.new_lines,
                    header=hunk.header.rstrip("\n"),
                    lines=tuple(lines),
                )
            )

        files.append(
            FileDiff(
                old_path=old_path,
                new_path=new_path,
                status=status,
                is_binary=is_binary,
                additions=additions,
                deletions=deletions,
                hunks=tuple(hunks_out),
            )
        )
    return DiffResult(files=tuple(files))


class DiffEngine:
    """Lecturas de diff sobre pygit2."""

    def diff_commit_to_parent(self, repo_path: Path, sha: str) -> DiffResult:
        repo = _open(repo_path)
        commit = repo.get(pygit2.Oid(hex=sha))
        if not isinstance(commit, pygit2.Commit):
            raise GitError(f"{sha} is not a commit")
        if commit.parents:
            parent_tree = commit.parents[0].tree
            diff = parent_tree.diff_to_tree(commit.tree)
        else:
            # Initial commit: diff vs empty tree.
            empty = repo.TreeBuilder().write()
            diff = repo[empty].diff_to_tree(commit.tree)
        return _convert_diff(diff)

    def diff_workdir_to_index(self, repo_path: Path) -> DiffResult:
        repo = _open(repo_path)
        diff = repo.diff(cached=False)
        return _convert_diff(diff)

    def diff_index_to_head(self, repo_path: Path) -> DiffResult:
        repo = _open(repo_path)
        diff = repo.diff(cached=True)
        return _convert_diff(diff)


# --- File history y pickaxe (vía CLI, libgit2 no soporta --follow estable) ----


@dataclass(slots=True, frozen=True)
class HistoryEntry:
    sha: str
    short_sha: str
    summary: str
    author_name: str
    author_email: str
    when: datetime


def _parse_history(stdout: str) -> list[HistoryEntry]:
    entries: list[HistoryEntry] = []
    # Formato: <sha>\x1f<author>\x1f<email>\x1f<unix_ts>\x1f<offset_min>\x1f<summary>
    for line in stdout.splitlines():
        if not line:
            continue
        parts = line.split("\x1f", 5)
        if len(parts) != 6:
            continue
        sha, name, email, ts, offset, summary = parts
        try:
            tz = timezone(timedelta(minutes=int(offset)))
            when = datetime.fromtimestamp(int(ts), tz=tz)
        except ValueError:
            when = datetime.now(tz=UTC)
        entries.append(
            HistoryEntry(
                sha=sha,
                short_sha=sha[:SHORT_SHA_LEN],
                summary=summary,
                author_name=name,
                author_email=email,
                when=when,
            )
        )
    return entries


def _entry_to_summary(entry: HistoryEntry) -> CommitSummary:
    sig = Signature(name=entry.author_name, email=entry.author_email, when=entry.when)
    return CommitSummary(
        sha=entry.sha,
        short_sha=entry.short_sha,
        summary=entry.summary,
        message=entry.summary,
        author=sig,
        committer=sig,
        parents=(),
    )


PRETTY_FORMAT = "%H%x1f%an%x1f%ae%x1f%at%x1f%aI%x1f%s"


async def file_history(
    cli: GitCli,
    repo_path: Path,
    file_path: str,
    *,
    follow: bool = True,
    limit: int = 200,
) -> list[CommitSummary]:
    """``git log --follow -- <path>`` con formato controlado."""
    args = ["log"]
    if follow:
        args.append("--follow")
    args += [
        f"--max-count={limit}",
        # Usamos %ai (ISO con offset) parseable; pero más simple: timestamps unix.
        "--pretty=format:%H%x1f%an%x1f%ae%x1f%at%x1f%aI%x1f%s",
        "--",
        file_path,
    ]
    stdout, _ = await cli.run(*args, cwd=repo_path)
    # Aprovechamos el campo offset ignorando el ISO completo.
    summaries: list[CommitSummary] = []
    for line in stdout.splitlines():
        if not line:
            continue
        parts = line.split("\x1f", 5)
        if len(parts) != 6:
            continue
        sha, name, email, ts, _iso, summary = parts
        try:
            when = datetime.fromtimestamp(int(ts), tz=UTC)
        except ValueError:
            when = datetime.now(tz=UTC)
        sig = Signature(name=name, email=email, when=when)
        summaries.append(
            CommitSummary(
                sha=sha,
                short_sha=sha[:SHORT_SHA_LEN],
                summary=summary,
                message=summary,
                author=sig,
                committer=sig,
                parents=(),
            )
        )
    return summaries


async def search_pickaxe(
    cli: GitCli,
    repo_path: Path,
    term: str,
    *,
    mode: str = "S",
    limit: int = 200,
) -> list[CommitSummary]:
    """Busca commits que añaden/eliminan ``term`` (``-S``) o lo cambian (``-G``)."""
    if mode not in ("S", "G"):
        raise ValueError(f"mode must be 'S' or 'G', got {mode!r}")
    flag = f"-{mode}{term}"
    args = [
        "log",
        flag,
        f"--max-count={limit}",
        "--pretty=format:%H%x1f%an%x1f%ae%x1f%at%x1f%aI%x1f%s",
    ]
    stdout, _ = await cli.run(*args, cwd=repo_path)
    summaries: list[CommitSummary] = []
    for line in stdout.splitlines():
        if not line:
            continue
        parts = line.split("\x1f", 5)
        if len(parts) != 6:
            continue
        sha, name, email, ts, _iso, summary = parts
        try:
            when = datetime.fromtimestamp(int(ts), tz=UTC)
        except ValueError:
            when = datetime.now(tz=UTC)
        sig = Signature(name=name, email=email, when=when)
        summaries.append(
            CommitSummary(
                sha=sha,
                short_sha=sha[:SHORT_SHA_LEN],
                summary=summary,
                message=summary,
                author=sig,
                committer=sig,
                parents=(),
            )
        )
    return summaries


__all__ = [
    "PRETTY_FORMAT",
    "DiffEngine",
    "DiffLine",
    "DiffResult",
    "FileDiff",
    "FileStatus",
    "HistoryEntry",
    "Hunk",
    "LineOrigin",
    "file_history",
    "search_pickaxe",
]
