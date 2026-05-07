"""Blame por archivo.

Implementación sobre :func:`pygit2.Repository.blame`, traducida a
estructuras headless. La vista renderiza una tabla `nº línea | sha7 |
autor | fecha | contenido`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pygit2

from pygit.domain.git.errors import GitError, NotAGitRepositoryError, RepositoryNotFoundError
from pygit.domain.git.models import SHORT_SHA_LEN

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(slots=True, frozen=True)
class BlameLine:
    lineno: int
    content: str
    sha: str
    short_sha: str
    author_name: str
    author_email: str
    when: datetime
    summary: str


def _open(path: Path) -> pygit2.Repository:
    if not path.exists():
        raise RepositoryNotFoundError(str(path))
    discovered = pygit2.discover_repository(str(path))
    if discovered is None:
        raise NotAGitRepositoryError(str(path))
    return pygit2.Repository(discovered)


class BlameEngine:
    def blame(self, repo_path: Path, file_path: str) -> list[BlameLine]:
        repo = _open(repo_path)
        try:
            blame = repo.blame(file_path)
        except (KeyError, pygit2.GitError) as exc:
            raise GitError(f"blame failed for {file_path!r}: {exc}") from exc

        # Cargar contenido del fichero en HEAD para reportar la línea textual.
        try:
            head = repo.head
            tree = repo[head.target].tree
            blob = tree[file_path]
            data = repo[blob.id].data
            content_lines = data.decode("utf-8", errors="replace").splitlines()
        except (KeyError, pygit2.GitError, AttributeError):
            content_lines = []

        result: list[BlameLine] = []
        for hunk in blame:
            commit = repo.get(hunk.final_commit_id)
            if not isinstance(commit, pygit2.Commit):
                continue
            sig = commit.author
            tz = timezone(timedelta(minutes=sig.offset))
            when = datetime.fromtimestamp(sig.time, tz=tz)
            sha = str(commit.id)
            summary = commit.message.split("\n", 1)[0]
            for offset in range(hunk.lines_in_hunk):
                lineno = hunk.final_start_line_number + offset
                content = content_lines[lineno - 1] if 0 < lineno <= len(content_lines) else ""
                result.append(
                    BlameLine(
                        lineno=lineno,
                        content=content,
                        sha=sha,
                        short_sha=sha[:SHORT_SHA_LEN],
                        author_name=sig.name,
                        author_email=sig.email,
                        when=when,
                        summary=summary,
                    )
                )
        result.sort(key=lambda b: b.lineno)
        return result


__all__ = ["BlameEngine", "BlameLine"]
