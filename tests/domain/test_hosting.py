"""Tests de :mod:`pygit.domain.hosting` — parseo de URLs + detección."""

from __future__ import annotations

import pytest

from pygit.domain.hosting import (
    GitHubProvider,
    ProviderKind,
    detect_provider,
    parse_remote_url,
)


class TestParseRemoteUrl:
    @pytest.mark.parametrize(
        ("url", "kind", "host", "owner", "name"),
        [
            (
                "https://github.com/octocat/hello-world.git",
                ProviderKind.GITHUB,
                "github.com",
                "octocat",
                "hello-world",
            ),
            (
                "git@github.com:octocat/hello-world.git",
                ProviderKind.GITHUB,
                "github.com",
                "octocat",
                "hello-world",
            ),
            (
                "https://gitlab.com/foo/bar.git",
                ProviderKind.GITLAB,
                "gitlab.com",
                "foo",
                "bar",
            ),
            (
                "ssh://git@bitbucket.org/foo/bar.git",
                ProviderKind.BITBUCKET,
                "bitbucket.org",
                "foo",
                "bar",
            ),
            (
                "https://codeberg.org/user/project",
                ProviderKind.GITEA,
                "codeberg.org",
                "user",
                "project",
            ),
            (
                "https://dev.azure.com/org/project",
                ProviderKind.AZURE_DEVOPS,
                "dev.azure.com",
                "org",
                "project",
            ),
            (
                "https://git.internal.corp/team/service.git",
                ProviderKind.UNKNOWN,
                "git.internal.corp",
                "team",
                "service",
            ),
        ],
    )
    def test_variants(self, url: str, kind: ProviderKind, host: str, owner: str, name: str) -> None:
        repo = parse_remote_url(url)
        assert repo is not None
        assert repo.kind == kind
        assert repo.host == host
        assert repo.owner == owner
        assert repo.name == name

    def test_bad_url_returns_none(self) -> None:
        assert parse_remote_url("not a url") is None

    def test_full_name_property(self) -> None:
        repo = parse_remote_url("https://github.com/a/b.git")
        assert repo is not None
        assert repo.full_name == "a/b"


class TestDetectProvider:
    def test_github_with_token_returns_github_provider(self) -> None:
        provider = detect_provider(["https://github.com/a/b.git"], token="ghp_x")
        assert isinstance(provider, GitHubProvider)

    def test_no_urls_returns_none(self) -> None:
        assert detect_provider([]) is None

    def test_unknown_host_returns_none(self) -> None:
        assert detect_provider(["https://git.internal.corp/a/b.git"]) is None

    def test_gitlab_without_token_falls_back_to_stub(self) -> None:
        provider = detect_provider(["https://gitlab.com/a/b.git"])
        assert provider is not None
        assert provider.repo.kind is ProviderKind.GITLAB


def test_github_enterprise_uses_api_v3_base() -> None:
    from pygit.domain.hosting import Repo

    repo = Repo(kind=ProviderKind.GITHUB, host="github.corp.com", owner="a", name="b")
    provider = GitHubProvider(repo, token="tok")
    # The base URL should target /api/v3 on Enterprise, not api.github.com.
    assert provider._base.endswith("/api/v3")
