"""Motor Git: ``GitEngine`` (pygit2) + ``GitCli`` (subprocess) híbrido.

Tabla de decisión motor → operación (vivirá ampliada en docs/architecture.md):

- pygit2 (libgit2): walks, refs, blobs, status, index, blame, low-level diff.
- git CLI: ``rebase -i``, ``git lfs``, ``git flow``, hooks de usuario, comandos
  no expuestos por libgit2 con paridad estable.
"""

from __future__ import annotations

from pygit.domain.git import undo, writer
from pygit.domain.git.blame import BlameEngine, BlameLine
from pygit.domain.git.cli import GitCli
from pygit.domain.git.diff import (
    DiffEngine,
    DiffLine,
    DiffResult,
    FileDiff,
    FileStatus,
    Hunk,
    LineOrigin,
    file_history,
    search_pickaxe,
)
from pygit.domain.git.engine import GitEngine
from pygit.domain.git.errors import (
    GitCliError,
    GitError,
    NotAGitRepositoryError,
    RepositoryNotFoundError,
)
from pygit.domain.git.graph import GraphRow, assign_lanes, max_lane_width
from pygit.domain.git.models import (
    BranchRef,
    CommitSummary,
    HeadInfo,
    RemoteRef,
    Signature,
    TagRef,
)
from pygit.domain.git.version import MIN_SUPPORTED, GitVersion

__all__ = [
    "MIN_SUPPORTED",
    "BlameEngine",
    "BlameLine",
    "BranchRef",
    "CommitSummary",
    "DiffEngine",
    "DiffLine",
    "DiffResult",
    "FileDiff",
    "FileStatus",
    "GitCli",
    "GitCliError",
    "GitEngine",
    "GitError",
    "GitVersion",
    "GraphRow",
    "HeadInfo",
    "Hunk",
    "LineOrigin",
    "NotAGitRepositoryError",
    "RemoteRef",
    "RepositoryNotFoundError",
    "Signature",
    "TagRef",
    "assign_lanes",
    "file_history",
    "max_lane_width",
    "search_pickaxe",
    "undo",
    "writer",
]
