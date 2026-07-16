"""Operaciones avanzadas: rebase interactivo, cherry-pick, reflog, hooks.

Rebase interactivo (driver):

  Git invoca el comando indicado en ``GIT_SEQUENCE_EDITOR`` con la ruta
  del fichero ``git-rebase-todo`` como único argumento. Para que la app
  pueda alterar ese todo desde la UI sin proceso interactivo, exportamos
  un script auxiliar (``rebase_todo_writer``) que sobreescribe el fichero
  con las acciones provistas por nosotros mediante una variable de
  entorno (``PYGIT_REBASE_TODO``) cuyo valor es el contenido completo
  del nuevo todo. El driver lanza ``git rebase -i <upstream>`` con esos
  envs y el script auxiliar respeta lo recibido.

Cherry-pick: pygit2.Repository.cherrypick + commit. Soporta multi-sha
en orden secuencial; aborta a la primera con conflictos y los reporta.

Reflog: lectura de ``HEAD`` reflog para mostrar últimas operaciones
(checkout, commit, merge, rebase…).

Hooks: listado de scripts en ``.git/hooks/``, con detección de
``.disabled`` para enable/disable per-hook.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import pygit2

from pygit.domain.git.errors import GitError, NotAGitRepositoryError, RepositoryNotFoundError
from pygit.domain.git.writer import CommitOptions, _resolve_signature

if TYPE_CHECKING:
    from pygit.domain.git.cli import GitCli


def _open(path: Path) -> pygit2.Repository:
    if not path.exists():
        raise RepositoryNotFoundError(str(path))
    discovered = pygit2.discover_repository(str(path))
    if discovered is None:
        raise NotAGitRepositoryError(str(path))
    return pygit2.Repository(discovered)


# --- Rebase interactivo --------------------------------------------------------


class RebaseAction(StrEnum):
    PICK = "pick"
    REWORD = "reword"
    EDIT = "edit"
    SQUASH = "squash"
    FIXUP = "fixup"
    DROP = "drop"
    EXEC = "exec"
    BREAK = "break"


@dataclass(slots=True, frozen=True)
class RebaseStep:
    action: RebaseAction
    sha: str
    summary: str = ""


def render_todo(steps: list[RebaseStep]) -> str:
    out: list[str] = []
    for step in steps:
        if step.action is RebaseAction.BREAK:
            out.append("break")
            continue
        if step.action is RebaseAction.EXEC:
            out.append(f"exec {step.summary}")
            continue
        out.append(f"{step.action.value} {step.sha[:7]} {step.summary}".rstrip())
    return "\n".join(out) + "\n"


async def run_interactive_rebase(
    cli: GitCli,
    repo_path: Path,
    upstream: str,
    steps: list[RebaseStep],
    *,
    sequence_editor_script: Path,
) -> None:
    """Lanza ``git rebase -i <upstream>`` con el todo precomputado.

    ``sequence_editor_script`` apunta a un script Python (incluido en el
    bundle) que lee ``PYGIT_REBASE_TODO`` y lo escribe sobre el fichero
    pasado como argumento. La función espera a que el rebase termine y
    relanza la salida como :class:`GitError` si falla.
    """
    todo = render_todo(steps)
    env = os.environ.copy()
    # Git ejecuta ``GIT_SEQUENCE_EDITOR`` a través del shell del sistema
    # (``sh -c`` en POSIX, cmd.exe en Windows). Escapamos ambos argumentos
    # para que rutas con espacios o caracteres especiales no rompan el
    # comando ni permitan inyección desde ``sys.executable`` o el script.
    env["GIT_SEQUENCE_EDITOR"] = (
        f"{shlex.quote(sys.executable)} {shlex.quote(str(sequence_editor_script))}"
    )
    env["PYGIT_REBASE_TODO"] = todo
    proc = await asyncio.create_subprocess_exec(
        cli.executable,
        "rebase",
        "-i",
        upstream,
        cwd=str(repo_path),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise GitError(f"git rebase -i failed: {stderr.decode('utf-8', 'replace').strip()}")


# --- Cherry-pick ---------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class CherryPickResult:
    sha_in: str
    sha_out: str | None
    conflicts: tuple[str, ...]


def cherry_pick(repo_path: Path, shas: list[str]) -> list[CherryPickResult]:
    repo = _open(repo_path)
    results: list[CherryPickResult] = []
    for sha in shas:
        commit = repo.get(pygit2.Oid(hex=sha))
        if not isinstance(commit, pygit2.Commit):
            raise GitError(f"{sha} is not a commit")
        repo.cherrypick(commit.id)
        if repo.index.conflicts:
            conflicts = tuple(c[0].path for c in repo.index.conflicts if c[0] is not None)
            results.append(CherryPickResult(sha_in=sha, sha_out=None, conflicts=conflicts))
            return results
        tree = repo.index.write_tree()
        sig = _resolve_signature(repo, CommitOptions(summary=commit.message.splitlines()[0]))
        msg = commit.message + f"\n(cherry picked from commit {sha})\n"
        new_oid = repo.create_commit("HEAD", commit.author, sig, msg, tree, [repo.head.target])
        repo.state_cleanup()
        results.append(CherryPickResult(sha_in=sha, sha_out=str(new_oid), conflicts=()))
    return results


# --- Reflog --------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class ReflogEntry:
    when: datetime
    actor_name: str
    actor_email: str
    old_sha: str
    new_sha: str
    message: str


def reflog(repo_path: Path, ref: str = "HEAD", *, limit: int = 200) -> list[ReflogEntry]:
    repo = _open(repo_path)
    try:
        ref_obj = repo.lookup_reference(ref)
    except (KeyError, pygit2.GitError) as exc:
        raise GitError(f"Reflog for {ref!r} unavailable: {exc}") from exc
    out: list[ReflogEntry] = []
    for entry in ref_obj.log():
        committer = entry.committer
        tz = timezone(timedelta(minutes=committer.offset))
        when = datetime.fromtimestamp(committer.time, tz=tz)
        out.append(
            ReflogEntry(
                when=when,
                actor_name=committer.name,
                actor_email=committer.email,
                old_sha=str(entry.oid_old),
                new_sha=str(entry.oid_new),
                message=entry.message,
            )
        )
        if len(out) >= limit:
            break
    return out


# --- Hooks ---------------------------------------------------------------------


KNOWN_HOOKS = (
    "pre-commit",
    "prepare-commit-msg",
    "commit-msg",
    "post-commit",
    "pre-rebase",
    "post-rewrite",
    "pre-push",
    "pre-receive",
    "post-receive",
    "update",
    "post-update",
    "applypatch-msg",
    "pre-applypatch",
    "post-applypatch",
)


@dataclass(slots=True, frozen=True)
class HookEntry:
    name: str
    path: Path
    enabled: bool


def list_hooks(repo_path: Path) -> list[HookEntry]:
    repo = _open(repo_path)
    hooks_dir = Path(repo.path) / "hooks"
    out: list[HookEntry] = []
    seen: set[str] = set()
    if not hooks_dir.exists():
        return out
    for entry in sorted(hooks_dir.iterdir()):
        if entry.is_dir():
            continue
        name = entry.name
        if name.endswith(".sample"):
            continue
        base = name.removesuffix(".disabled")
        if base in seen:
            continue
        seen.add(base)
        out.append(
            HookEntry(
                name=base,
                path=entry,
                enabled=not name.endswith(".disabled"),
            )
        )
    return out


def set_hook_enabled(repo_path: Path, name: str, enabled: bool) -> None:
    repo = _open(repo_path)
    hooks_dir = Path(repo.path) / "hooks"
    base = hooks_dir / name
    disabled = hooks_dir / f"{name}.disabled"
    if enabled and disabled.exists():
        disabled.rename(base)
    elif not enabled and base.exists():
        base.rename(disabled)


__all__ = [
    "KNOWN_HOOKS",
    "CherryPickResult",
    "HookEntry",
    "RebaseAction",
    "RebaseStep",
    "ReflogEntry",
    "cherry_pick",
    "list_hooks",
    "reflog",
    "render_todo",
    "run_interactive_rebase",
    "set_hook_enabled",
]
