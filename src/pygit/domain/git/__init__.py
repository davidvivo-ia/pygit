"""Motor Git: ``GitEngine`` (pygit2) + ``GitCli`` (subprocess) híbrido.

Tabla de decisión motor → operación (vivirá ampliada en docs/architecture.md):

- pygit2 (libgit2): walks, refs, blobs, status, index, blame, low-level diff.
- git CLI: ``rebase -i``, ``git lfs``, ``git flow``, hooks de usuario, comandos
  no expuestos por libgit2 con paridad estable.
"""

from __future__ import annotations

from pygit.domain.git.cli import GitCli
from pygit.domain.git.engine import GitEngine
from pygit.domain.git.errors import (
    GitCliError,
    GitError,
    NotAGitRepositoryError,
    RepositoryNotFoundError,
)
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
    "BranchRef",
    "CommitSummary",
    "GitCli",
    "GitCliError",
    "GitEngine",
    "GitError",
    "GitVersion",
    "HeadInfo",
    "NotAGitRepositoryError",
    "RemoteRef",
    "RepositoryNotFoundError",
    "Signature",
    "TagRef",
]
