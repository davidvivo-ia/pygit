"""Fixtures para tests de la capa Git: repos sintéticos en ``tmp_path``."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pygit2
import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def signature() -> pygit2.Signature:
    """Author/committer determinista para tests."""
    when = int(datetime(2026, 1, 1, 12, 0, tzinfo=UTC).timestamp())
    return pygit2.Signature("Tester", "tester@example.com", when, 0)


@pytest.fixture
def empty_repo(tmp_path: Path) -> pygit2.Repository:
    """Repo recién inicializado, HEAD unborn."""
    return pygit2.init_repository(str(tmp_path / "repo"), bare=False)


@pytest.fixture
def linear_repo(tmp_path: Path, signature: pygit2.Signature) -> tuple[pygit2.Repository, list[str]]:
    """Repo con 3 commits lineales en ``main``. Devuelve ``(repo, [shas])``.

    Se fuerza HEAD a ``refs/heads/main`` antes del primer commit para que el
    test sea determinista (independiente del default de libgit2/Git for Windows,
    que puede variar entre ``master`` y ``main``).
    """
    repo = pygit2.init_repository(str(tmp_path / "linear"), bare=False)
    repo.references.create_symbolic("HEAD", "refs/heads/main", force=True)

    shas: list[str] = []
    parents: list[pygit2.Oid] = []
    for i in range(3):
        tree_builder = repo.TreeBuilder()
        blob = repo.create_blob(f"hello {i}\n".encode())
        tree_builder.insert(f"file_{i}.txt", blob, pygit2.GIT_FILEMODE_BLOB)
        tree_oid = tree_builder.write()
        commit_oid = repo.create_commit(
            "HEAD",
            signature,
            signature,
            f"commit {i}\n\nbody {i}",
            tree_oid,
            parents,
        )
        shas.append(str(commit_oid))
        parents = [commit_oid]

    return repo, shas
