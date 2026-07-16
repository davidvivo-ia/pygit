"""Tests de undo/restore basado en snapshots de refs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pygit.domain.git.undo import restore, snapshot
from pygit.domain.git.writer import create_branch, delete_branch

if TYPE_CHECKING:
    import pygit2


def test_snapshot_captures_refs(
    linear_repo: tuple[pygit2.Repository, list[str]],
) -> None:
    repo, _ = linear_repo
    snap = snapshot(Path(repo.workdir), label="pre")
    assert snap.label == "pre"
    assert "refs/heads/main" in snap.refs


def test_restore_removes_created_branch(
    linear_repo: tuple[pygit2.Repository, list[str]],
) -> None:
    repo, _ = linear_repo
    workdir = Path(repo.workdir)
    snap = snapshot(workdir, "before-create")
    create_branch(workdir, "temp")
    assert "temp" in list(repo.branches.local)
    restore(workdir, snap)
    assert "temp" not in list(repo.branches.local)


def test_restore_recreates_deleted_branch(
    linear_repo: tuple[pygit2.Repository, list[str]],
) -> None:
    repo, _ = linear_repo
    workdir = Path(repo.workdir)
    create_branch(workdir, "keeper")
    snap = snapshot(workdir, "before-delete")
    delete_branch(workdir, "keeper", force=True)
    assert "keeper" not in list(repo.branches.local)
    restore(workdir, snap)
    assert "keeper" in list(repo.branches.local)


def test_snapshot_records_head_target(
    linear_repo: tuple[pygit2.Repository, list[str]],
) -> None:
    repo, shas = linear_repo
    snap = snapshot(Path(repo.workdir), "labels")
    assert snap.head_target == shas[-1]
    assert snap.head_is_symbolic
    assert snap.head_symbolic == "refs/heads/main"
