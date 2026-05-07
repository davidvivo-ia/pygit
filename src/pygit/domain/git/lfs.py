"""Soporte ligero para Git LFS.

Detección, status y track/untrack vía CLI (``git lfs``). pygit2 no expone
LFS; siempre vamos por subprocess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from pygit.domain.git.cli import GitCli


@dataclass(slots=True, frozen=True)
class LfsStatus:
    enabled: bool
    tracked_patterns: tuple[str, ...]


async def detect(cli: GitCli, repo_path: Path) -> LfsStatus:
    try:
        stdout, _ = await cli.run("lfs", "track", cwd=repo_path)
    except Exception:
        return LfsStatus(enabled=False, tracked_patterns=())
    patterns: list[str] = []
    for line in stdout.splitlines():
        match = re.match(r"\s+([^\s]+)\s+\(.*\)", line)
        if match:
            patterns.append(match.group(1))
    return LfsStatus(enabled=True, tracked_patterns=tuple(patterns))


async def track(cli: GitCli, repo_path: Path, pattern: str) -> None:
    await cli.run("lfs", "track", pattern, cwd=repo_path)


async def untrack(cli: GitCli, repo_path: Path, pattern: str) -> None:
    await cli.run("lfs", "untrack", pattern, cwd=repo_path)


async def pull(cli: GitCli, repo_path: Path) -> None:
    await cli.run("lfs", "pull", cwd=repo_path)


async def push(cli: GitCli, repo_path: Path, remote: str = "origin") -> None:
    await cli.run("lfs", "push", remote, "--all", cwd=repo_path)


__all__ = ["LfsStatus", "detect", "pull", "push", "track", "untrack"]
