"""Hosting providers: detección, listado de PRs, crear, mergear.

Arquitectura:

- :class:`Provider` (Protocol): contrato común que adoptan las
  implementaciones por proveedor.
- :func:`detect_provider`: a partir de la URL del remoto adivina el
  proveedor concreto y devuelve una instancia configurada.
- Implementaciones cubiertas en v1.0:
    - GitHub (cloud y enterprise)
    - GitLab (cloud y self-hosted)
    - Bitbucket Cloud
    - Azure DevOps Services
    - Gitea / Codeberg

En v1.0 sólo implementamos GitHub completamente (lista, crea, mergea
PRs); el resto exponen ``detect`` y dejan los métodos como
``NotImplementedError`` para evitar el efecto "stub silencioso".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

import httpx

if TYPE_CHECKING:
    from collections.abc import Iterable


class ProviderKind(StrEnum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    AZURE_DEVOPS = "azure"
    GITEA = "gitea"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class Repo:
    kind: ProviderKind
    host: str
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(slots=True, frozen=True)
class PullRequest:
    number: int
    title: str
    body: str
    author: str
    state: str
    source_branch: str
    target_branch: str
    url: str
    created_at: datetime | None = None
    is_draft: bool = False


class Provider(Protocol):
    repo: Repo

    async def list_pull_requests(self) -> list[PullRequest]: ...
    async def create_pull_request(
        self, title: str, body: str, source: str, target: str, *, draft: bool = False
    ) -> PullRequest: ...
    async def merge_pull_request(self, number: int, *, method: str = "merge") -> None: ...


# --- Detection -----------------------------------------------------------------


_HOST_KIND = (
    (re.compile(r"(?:^|\.)github\.com$"), ProviderKind.GITHUB),
    (re.compile(r"(?:^|\.)gitlab\.com$"), ProviderKind.GITLAB),
    (re.compile(r"(?:^|\.)bitbucket\.org$"), ProviderKind.BITBUCKET),
    (re.compile(r"(?:^|\.)dev\.azure\.com$"), ProviderKind.AZURE_DEVOPS),
    (re.compile(r"(?:^|\.)visualstudio\.com$"), ProviderKind.AZURE_DEVOPS),
    (re.compile(r"(?:^|\.)codeberg\.org$"), ProviderKind.GITEA),
)


def _classify_host(host: str) -> ProviderKind:
    h = host.lower()
    for pattern, kind in _HOST_KIND:
        if pattern.search(h):
            return kind
    # Heurística: si la URL contiene "/api/v4" → GitLab; si contiene "/api/v1"
    # típicamente Gitea. En su defecto, UNKNOWN; el usuario puede sobreescribir
    # manualmente desde la UI (Fase 6).
    return ProviderKind.UNKNOWN


def parse_remote_url(url: str) -> Repo | None:
    """Convierte una URL de remote en :class:`Repo` o ``None`` si no se
    puede deducir.

    Acepta:
    - ``https://github.com/owner/repo[.git]``
    - ``git@github.com:owner/repo.git``
    - ``ssh://git@host/owner/repo.git``
    """
    url = url.strip()
    https_match = re.match(
        r"^(?:https?|ssh)://(?:[^@]+@)?([^/:]+)(?::\d+)?/([^/]+)/([^/]+?)(?:\.git)?/?$",
        url,
    )
    if https_match is not None:
        host, owner, name = https_match.group(1), https_match.group(2), https_match.group(3)
        return Repo(kind=_classify_host(host), host=host, owner=owner, name=name)

    scp_match = re.match(r"^(?:[^@]+@)?([^:]+):([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if scp_match is not None:
        host, owner, name = scp_match.group(1), scp_match.group(2), scp_match.group(3)
        return Repo(kind=_classify_host(host), host=host, owner=owner, name=name)

    return None


# --- GitHub --------------------------------------------------------------------


class GitHubProvider:
    def __init__(self, repo: Repo, *, token: str, api_base: str | None = None) -> None:
        self.repo = repo
        self._token = token
        self._base = api_base or (
            "https://api.github.com" if repo.host == "github.com" else f"https://{repo.host}/api/v3"
        )
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def list_pull_requests(self) -> list[PullRequest]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{self._base}/repos/{self.repo.full_name}/pulls",
                headers=self._headers,
                params={"state": "open", "per_page": 100},
            )
            resp.raise_for_status()
            data = resp.json()
        return [_pr_from_github(item) for item in data]

    async def create_pull_request(
        self, title: str, body: str, source: str, target: str, *, draft: bool = False
    ) -> PullRequest:
        payload = {
            "title": title,
            "body": body,
            "head": source,
            "base": target,
            "draft": draft,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base}/repos/{self.repo.full_name}/pulls",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
        return _pr_from_github(resp.json())

    async def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        if method not in ("merge", "squash", "rebase"):
            raise ValueError(f"unknown merge method {method!r}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(
                f"{self._base}/repos/{self.repo.full_name}/pulls/{number}/merge",
                headers=self._headers,
                json={"merge_method": method},
            )
            resp.raise_for_status()


def _pr_from_github(item: dict[str, object]) -> PullRequest:
    user = item.get("user") or {}
    head = item.get("head") or {}
    base = item.get("base") or {}
    created_raw = item.get("created_at")
    when: datetime | None = None
    if isinstance(created_raw, str):
        try:
            when = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
        except ValueError:
            when = None
    return PullRequest(
        number=int(item.get("number") or 0),
        title=str(item.get("title") or ""),
        body=str(item.get("body") or ""),
        author=str(user.get("login") if isinstance(user, dict) else "") or "",
        state=str(item.get("state") or "open"),
        source_branch=str(head.get("ref") if isinstance(head, dict) else ""),
        target_branch=str(base.get("ref") if isinstance(base, dict) else ""),
        url=str(item.get("html_url") or ""),
        created_at=when,
        is_draft=bool(item.get("draft", False)),
    )


# --- Stubs (Fase 5+, expanded later) ------------------------------------------


class _UnimplementedProvider:
    def __init__(self, repo: Repo) -> None:
        self.repo = repo

    async def list_pull_requests(self) -> list[PullRequest]:
        raise NotImplementedError(f"{self.repo.kind.value} not implemented in v1.0")

    async def create_pull_request(
        self, title: str, body: str, source: str, target: str, *, draft: bool = False
    ) -> PullRequest:
        raise NotImplementedError(f"{self.repo.kind.value} not implemented in v1.0")

    async def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        raise NotImplementedError(f"{self.repo.kind.value} not implemented in v1.0")


# --- Factory ------------------------------------------------------------------


def detect_provider(remote_urls: Iterable[str], *, token: str | None = None) -> Provider | None:
    for url in remote_urls:
        repo = parse_remote_url(url)
        if repo is None:
            continue
        if repo.kind is ProviderKind.GITHUB and token:
            return GitHubProvider(repo, token=token)
        if repo.kind is not ProviderKind.UNKNOWN:
            return _UnimplementedProvider(repo)
    return None


__all__ = [
    "GitHubProvider",
    "Provider",
    "ProviderKind",
    "PullRequest",
    "Repo",
    "detect_provider",
    "parse_remote_url",
]
