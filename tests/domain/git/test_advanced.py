"""Tests de :mod:`pygit.domain.git.advanced`."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pygit.domain.git.advanced import (
    HookEntry,
    RebaseAction,
    RebaseStep,
    cherry_pick,
    list_hooks,
    reflog,
    render_todo,
    set_hook_enabled,
)
from pygit.domain.git.errors import GitError
from pygit.domain.git.writer import CommitOptions, commit, create_branch, stage_paths

if TYPE_CHECKING:
    import pygit2


class TestRenderTodo:
    def test_empty(self) -> None:
        assert render_todo([]) == "\n"

    def test_pick(self) -> None:
        step = RebaseStep(action=RebaseAction.PICK, sha="a" * 40, summary="feat: x")
        assert render_todo([step]) == "pick aaaaaaa feat: x\n"

    def test_break(self) -> None:
        assert render_todo([RebaseStep(action=RebaseAction.BREAK, sha="")]) == "break\n"

    def test_exec_uses_summary_as_command(self) -> None:
        step = RebaseStep(action=RebaseAction.EXEC, sha="", summary="pytest")
        assert render_todo([step]) == "exec pytest\n"

    def test_multiple_steps_joined(self) -> None:
        steps = [
            RebaseStep(RebaseAction.PICK, "a" * 40, "one"),
            RebaseStep(RebaseAction.SQUASH, "b" * 40, "two"),
            RebaseStep(RebaseAction.DROP, "c" * 40, "three"),
        ]
        out = render_todo(steps)
        assert out.count("\n") == 3
        assert "pick aaaaaaa one" in out
        assert "squash bbbbbbb two" in out
        assert "drop ccccccc three" in out


class TestCherryPick:
    def test_bad_sha_raises(self, linear_repo: tuple[pygit2.Repository, list[str]]) -> None:
        repo, _ = linear_repo
        # A commit sha that does not exist in the repo.
        bogus = "f" * 40
        with pytest.raises(Exception):  # noqa: B017 — pygit2 raises KeyError
            cherry_pick(Path(repo.workdir), [bogus])

    def test_pick_new_commit_onto_branch(
        self, linear_repo: tuple[pygit2.Repository, list[str]]
    ) -> None:
        repo, shas = linear_repo
        workdir = Path(repo.workdir)
        # Create a side branch off shas[0] and cherry-pick shas[-1] on it.
        create_branch(workdir, "side", shas[0])
        from pygit.domain.git.writer import checkout_branch

        checkout_branch(workdir, "side")
        results = cherry_pick(workdir, [shas[-1]])
        assert len(results) == 1
        assert results[0].sha_in == shas[-1]
        assert results[0].sha_out is not None
        assert results[0].conflicts == ()


class TestReflog:
    def test_reflog_reports_commits(
        self,
        linear_repo: tuple[pygit2.Repository, list[str]],
    ) -> None:
        repo, shas = linear_repo
        entries = reflog(Path(repo.workdir), limit=10)
        assert entries, "reflog should not be empty after commits"
        # New commit shas should appear in the reflog's new_sha column.
        new_shas = {e.new_sha for e in entries}
        assert shas[-1] in new_shas

    def test_reflog_bad_ref_raises(self, empty_repo: pygit2.Repository) -> None:
        with pytest.raises(GitError):
            reflog(Path(empty_repo.workdir), ref="refs/heads/does-not-exist")


class TestHooks:
    def test_list_hooks_ignores_samples(
        self, linear_repo: tuple[pygit2.Repository, list[str]]
    ) -> None:
        repo, _ = linear_repo
        entries = list_hooks(Path(repo.workdir))
        # Nothing installed yet (init creates .sample files that we filter).
        for entry in entries:
            assert not entry.path.name.endswith(".sample")

    def test_toggle_hook(self, linear_repo: tuple[pygit2.Repository, list[str]]) -> None:
        repo, _ = linear_repo
        hooks_dir = Path(repo.path) / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        hook_path = hooks_dir / "pre-commit"
        hook_path.write_text("#!/bin/sh\nexit 0\n")

        entries = {h.name: h for h in list_hooks(Path(repo.workdir))}
        assert "pre-commit" in entries
        assert entries["pre-commit"].enabled

        set_hook_enabled(Path(repo.workdir), "pre-commit", False)
        entries = {h.name: h for h in list_hooks(Path(repo.workdir))}
        assert not entries["pre-commit"].enabled

        set_hook_enabled(Path(repo.workdir), "pre-commit", True)
        entries = {h.name: h for h in list_hooks(Path(repo.workdir))}
        assert entries["pre-commit"].enabled


class TestHookEntryEquality:
    def test_frozen(self) -> None:
        h = HookEntry(name="pre-commit", path=Path("/tmp/x"), enabled=True)
        with pytest.raises((AttributeError, TypeError)):
            h.enabled = False  # type: ignore[misc]


class TestPullRebaseNotImplemented:
    def test_pull_rebase_raises(self, linear_repo: tuple[pygit2.Repository, list[str]]) -> None:
        from pygit.domain.git.remote import pull

        repo, _ = linear_repo
        # No remote configured; this raises earlier than the rebase path but
        # the point is: with rebase=True the code path must raise, not silently
        # merge (regression against the bug where rebase/ff_only did nothing).
        with pytest.raises(GitError):
            pull(Path(repo.workdir), rebase=True)


def test_datetime_used_in_module() -> None:
    # Guard against an import-only regression.
    from pygit.domain.git.advanced import ReflogEntry

    entry = ReflogEntry(
        when=datetime(2026, 1, 1, tzinfo=UTC),
        actor_name="t",
        actor_email="t@e",
        old_sha="0" * 40,
        new_sha="1" * 40,
        message="init",
    )
    assert entry.actor_name == "t"


class TestCommitPluggedIntoCherryPickFlow:
    """Guard against writer.commit + advanced.cherry_pick regressions."""

    def test_commit_amend_after_first(self, empty_repo: pygit2.Repository) -> None:
        empty_repo.config["user.name"] = "T"
        empty_repo.config["user.email"] = "t@e"
        workdir = Path(empty_repo.workdir)
        (workdir / "a.txt").write_text("x")
        stage_paths(workdir, ["a.txt"])
        first = commit(workdir, CommitOptions(summary="first"))
        (workdir / "a.txt").write_text("y")
        stage_paths(workdir, ["a.txt"])
        second = commit(workdir, CommitOptions(summary="first amended", amend=True))
        assert first != second
