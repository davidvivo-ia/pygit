"""Tests de :class:`GitEngine` con repos sintéticos creados vía pygit2."""

from __future__ import annotations

from pathlib import Path

import pygit2
import pytest

from pygit.domain.git.engine import GitEngine
from pygit.domain.git.errors import NotAGitRepositoryError, RepositoryNotFoundError


@pytest.fixture
def engine() -> GitEngine:
    return GitEngine()


def test_discover_raises_when_path_missing(engine: GitEngine, tmp_path: Path) -> None:
    with pytest.raises(RepositoryNotFoundError):
        engine.discover(tmp_path / "does-not-exist")


def test_discover_raises_when_not_a_repo(engine: GitEngine, tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "README.md").write_text("hi")
    with pytest.raises(NotAGitRepositoryError):
        engine.discover(plain)


def test_discover_resolves_workdir(engine: GitEngine, empty_repo: pygit2.Repository) -> None:
    workdir = engine.discover(Path(empty_repo.workdir))
    assert workdir.resolve() == Path(empty_repo.workdir).resolve()


def test_head_is_unborn_in_empty_repo(engine: GitEngine, empty_repo: pygit2.Repository) -> None:
    head = engine.head(Path(empty_repo.workdir))
    assert head.is_unborn is True
    assert head.is_detached is False
    assert head.branch_name is None
    assert head.target_sha == ""


def test_head_after_first_commit(
    engine: GitEngine, linear_repo: tuple[pygit2.Repository, list[str]]
) -> None:
    repo, shas = linear_repo
    head = engine.head(Path(repo.workdir))
    assert head.is_unborn is False
    assert head.is_detached is False
    assert head.branch_name == "main"
    assert head.target_sha == shas[-1]


def test_branches_lists_main(
    engine: GitEngine, linear_repo: tuple[pygit2.Repository, list[str]]
) -> None:
    repo, _shas = linear_repo
    branches = engine.branches(Path(repo.workdir))
    names = {b.name for b in branches if not b.is_remote}
    assert names == {"main"}
    main = next(b for b in branches if b.name == "main")
    assert main.full_name == "refs/heads/main"
    assert main.is_remote is False


def test_tags_lightweight_and_annotated(
    engine: GitEngine,
    linear_repo: tuple[pygit2.Repository, list[str]],
    signature: pygit2.Signature,
) -> None:
    repo, shas = linear_repo
    head_oid = pygit2.Oid(hex=shas[-1])
    repo.references.create("refs/tags/v0.1", head_oid)
    repo.create_tag("v0.2", head_oid, pygit2.GIT_OBJECT_COMMIT, signature, "release 0.2")

    tags = {t.name: t for t in engine.tags(Path(repo.workdir))}
    assert set(tags) == {"v0.1", "v0.2"}
    assert tags["v0.1"].is_annotated is False
    assert tags["v0.1"].target_sha == shas[-1]
    assert tags["v0.2"].is_annotated is True
    assert tags["v0.2"].message == "release 0.2"
    assert tags["v0.2"].target_sha == shas[-1]


def test_remotes_listed(
    engine: GitEngine, linear_repo: tuple[pygit2.Repository, list[str]]
) -> None:
    repo, _ = linear_repo
    repo.remotes.create("origin", "https://example.com/foo.git")
    remotes = engine.remotes(Path(repo.workdir))
    assert len(remotes) == 1
    assert remotes[0].name == "origin"
    assert remotes[0].fetch_url == "https://example.com/foo.git"


def test_walk_history_returns_topological_order(
    engine: GitEngine, linear_repo: tuple[pygit2.Repository, list[str]]
) -> None:
    repo, shas = linear_repo
    history = engine.walk_history(Path(repo.workdir))
    assert [c.sha for c in history] == list(reversed(shas))
    first = history[0]
    assert first.short_sha == first.sha[:7]
    assert first.author.name == "Tester"
    assert first.summary.startswith("commit ")


def test_walk_history_respects_limit(
    engine: GitEngine, linear_repo: tuple[pygit2.Repository, list[str]]
) -> None:
    repo, _ = linear_repo
    history = engine.walk_history(Path(repo.workdir), limit=2)
    assert len(history) == 2


def test_walk_history_empty_for_unborn(engine: GitEngine, empty_repo: pygit2.Repository) -> None:
    assert engine.walk_history(Path(empty_repo.workdir)) == []
