"""Wrappers de Git Flow (vía CLI ``git-flow``).

No reimplementamos el protocolo: si el usuario tiene ``git-flow``
instalado, llamamos al binario. Si no, devolvemos un error claro.
``init`` permite configurar prefijos custom (paridad SmartGit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from pygit.domain.git.cli import GitCli


@dataclass(slots=True, frozen=True)
class FlowPrefixes:
    master: str = "main"
    develop: str = "develop"
    feature: str = "feature/"
    release: str = "release/"
    hotfix: str = "hotfix/"
    support: str = "support/"
    versiontag: str = "v"
    extras: dict[str, str] = field(default_factory=dict)


async def init(cli: GitCli, repo_path: Path, *, prefixes: FlowPrefixes | None = None) -> None:
    p = prefixes or FlowPrefixes()
    args = [
        "flow",
        "init",
        "-d",  # use defaults except where overridden
        "-f",  # force
    ]
    # git-flow accepts -- prefixes via stdin or interactive flags; with -d -f
    # it picks the default master (main since 2.x), develop, etc. For
    # custom prefixes we set them via git config first.
    await cli.run(*args, cwd=repo_path)
    cfg_pairs = {
        "gitflow.branch.master": p.master,
        "gitflow.branch.develop": p.develop,
        "gitflow.prefix.feature": p.feature,
        "gitflow.prefix.release": p.release,
        "gitflow.prefix.hotfix": p.hotfix,
        "gitflow.prefix.support": p.support,
        "gitflow.prefix.versiontag": p.versiontag,
    }
    for key, value in cfg_pairs.items():
        await cli.run("config", key, value, cwd=repo_path)


async def feature_start(cli: GitCli, repo_path: Path, name: str) -> None:
    await cli.run("flow", "feature", "start", name, cwd=repo_path)


async def feature_finish(cli: GitCli, repo_path: Path, name: str) -> None:
    await cli.run("flow", "feature", "finish", name, cwd=repo_path)


async def release_start(cli: GitCli, repo_path: Path, version: str) -> None:
    await cli.run("flow", "release", "start", version, cwd=repo_path)


async def release_finish(cli: GitCli, repo_path: Path, version: str) -> None:
    await cli.run("flow", "release", "finish", "-m", version, version, cwd=repo_path)


async def hotfix_start(cli: GitCli, repo_path: Path, version: str) -> None:
    await cli.run("flow", "hotfix", "start", version, cwd=repo_path)


async def hotfix_finish(cli: GitCli, repo_path: Path, version: str) -> None:
    await cli.run("flow", "hotfix", "finish", "-m", version, version, cwd=repo_path)


__all__ = [
    "FlowPrefixes",
    "feature_finish",
    "feature_start",
    "hotfix_finish",
    "hotfix_start",
    "init",
    "release_finish",
    "release_start",
]
