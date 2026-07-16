"""Tests de :mod:`pygit.domain.git.writer` con repos sintéticos."""

from __future__ import annotations

from pathlib import Path

import pygit2
import pytest

from pygit.domain.git.errors import GitError
from pygit.domain.git.writer import (
    CommitOptions,
    checkout_branch,
    commit,
    create_annotated_tag,
    create_branch,
    create_lightweight_tag,
    delete_branch,
    delete_tag,
    list_status,
    merge_branch,
    rename_branch,
    reset,
    stage_paths,
    stash_list,
    stash_save,
    unstage_paths,
)


class TestStatus:
    def test_empty_repo_has_no_status(self, empty_repo: pygit2.Repository) -> None:
        assert list_status(Path(empty_repo.workdir)) == []

    def test_untracked_file_reported(self, empty_repo: pygit2.Repository) -> None:
        workdir = Path(empty_repo.workdir)
        (workdir / "note.txt").write_text("hi")
        entries = list_status(workdir)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.path == "note.txt"
        assert entry.is_new
        assert not entry.is_staged


class TestStagingAndCommit:
    def test_stage_and_commit_creates_history(self, empty_repo: pygit2.Repository) -> None:
        workdir = Path(empty_repo.workdir)
        # Configure identity for the commit.
        empty_repo.config["user.name"] = "Tester"
        empty_repo.config["user.email"] = "t@e"
        (workdir / "hello.txt").write_text("world\n")

        stage_paths(workdir, ["hello.txt"])
        entries = list_status(workdir)
        staged = [e for e in entries if e.is_staged]
        assert len(staged) == 1

        sha = commit(workdir, CommitOptions(summary="add hello"))
        assert len(sha) == 40
        assert not empty_repo.head_is_unborn
        assert str(empty_repo.head.target) == sha

    def test_commit_without_identity_raises(self, empty_repo: pygit2.Repository) -> None:
        workdir = Path(empty_repo.workdir)
        (workdir / "a.txt").write_text("hi")
        stage_paths(workdir, ["a.txt"])
        with pytest.raises(GitError, match=r"user\.name/user\.email"):
            commit(workdir, CommitOptions(summary="oops"))

    def test_signoff_trailer_added(self, empty_repo: pygit2.Repository) -> None:
        workdir = Path(empty_repo.workdir)
        empty_repo.config["user.name"] = "Alice"
        empty_repo.config["user.email"] = "alice@ex.com"
        (workdir / "f.txt").write_text("x")
        stage_paths(workdir, ["f.txt"])
        sha = commit(workdir, CommitOptions(summary="feat: x", sign_off=True))
        message = empty_repo[pygit2.Oid(hex=sha)].message
        assert "Signed-off-by: Alice <alice@ex.com>" in message


class TestBranches:
    def test_create_and_delete_branch(
        self, linear_repo: tuple[pygit2.Repository, list[str]]
    ) -> None:
        repo, _ = linear_repo
        workdir = Path(repo.workdir)
        create_branch(workdir, "feature")
        assert "feature" in list(repo.branches.local)

        delete_branch(workdir, "feature", force=True)
        assert "feature" not in list(repo.branches.local)

    def test_rename_branch(self, linear_repo: tuple[pygit2.Repository, list[str]]) -> None:
        repo, _ = linear_repo
        workdir = Path(repo.workdir)
        create_branch(workdir, "old")
        rename_branch(workdir, "old", "new")
        assert "new" in list(repo.branches.local)
        assert "old" not in list(repo.branches.local)

    def test_checkout_branch(self, linear_repo: tuple[pygit2.Repository, list[str]]) -> None:
        repo, _ = linear_repo
        workdir = Path(repo.workdir)
        create_branch(workdir, "feature")
        checkout_branch(workdir, "feature")
        assert repo.head.shorthand == "feature"


class TestMerge:
    def test_up_to_date_reports_flag(
        self, linear_repo: tuple[pygit2.Repository, list[str]]
    ) -> None:
        repo, _ = linear_repo
        workdir = Path(repo.workdir)
        create_branch(workdir, "same")
        result = merge_branch(workdir, "same")
        assert result.up_to_date


class TestTags:
    def test_lightweight_tag(self, linear_repo: tuple[pygit2.Repository, list[str]]) -> None:
        repo, shas = linear_repo
        create_lightweight_tag(Path(repo.workdir), "v0.1", shas[-1])
        assert "refs/tags/v0.1" in list(repo.references)

    def test_annotated_tag_and_delete(
        self, linear_repo: tuple[pygit2.Repository, list[str]]
    ) -> None:
        repo, shas = linear_repo
        create_annotated_tag(Path(repo.workdir), "v0.2", shas[-1], "release 0.2")
        assert "refs/tags/v0.2" in list(repo.references)
        delete_tag(Path(repo.workdir), "v0.2")
        assert "refs/tags/v0.2" not in list(repo.references)

    def test_delete_missing_tag_raises(
        self, linear_repo: tuple[pygit2.Repository, list[str]]
    ) -> None:
        repo, _ = linear_repo
        with pytest.raises(GitError):
            delete_tag(Path(repo.workdir), "does-not-exist")


class TestStash:
    def test_stash_save_when_workdir_dirty(
        self, linear_repo: tuple[pygit2.Repository, list[str]]
    ) -> None:
        repo, _ = linear_repo
        workdir = Path(repo.workdir)
        # Modify a tracked file so there is something to stash.
        (workdir / "file_0.txt").write_text("changed\n")
        stage_paths(workdir, ["file_0.txt"])
        sha = stash_save(workdir, "wip")
        assert sha is not None
        entries = stash_list(workdir)
        assert len(entries) == 1
        assert entries[0].sha == sha

    def test_stash_save_no_changes_returns_none(
        self, linear_repo: tuple[pygit2.Repository, list[str]]
    ) -> None:
        repo, _ = linear_repo
        assert stash_save(Path(repo.workdir), "empty") is None


class TestReset:
    def test_reset_soft_moves_head(self, linear_repo: tuple[pygit2.Repository, list[str]]) -> None:
        repo, shas = linear_repo
        # Move HEAD one commit back.
        reset(Path(repo.workdir), shas[0], mode="soft")
        assert str(repo.head.target) == shas[0]


class TestUnstage:
    def test_unstage_removes_staged(self, empty_repo: pygit2.Repository) -> None:
        empty_repo.config["user.name"] = "Tester"
        empty_repo.config["user.email"] = "t@e"
        workdir = Path(empty_repo.workdir)
        (workdir / "hello.txt").write_text("world")
        stage_paths(workdir, ["hello.txt"])
        # Unborn HEAD path: unstage should remove from index.
        unstage_paths(workdir, ["hello.txt"])
        entries = list_status(workdir)
        # After unstage, file appears untracked (worktree new) but not staged.
        assert all(not e.is_staged for e in entries)
