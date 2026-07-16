"""Operaciones de escritura local sobre el repositorio.

Reúne las operaciones que mutan el repo *local* (sin red): staging,
commit, branch CRUD, merge, stash, tags, reset granular. La línea
divisoria es: si la operación toca un remoto, vive en
:mod:`pygit.domain.git.remote`.

Algunas operaciones se delegan al CLI cuando libgit2 no expone una API
limpia (p.ej. staging hunk-level usa ``git apply --cached`` con un patch
parcial generado por nosotros, ya que ``Index`` de libgit2 sólo entiende
de archivos enteros).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygit2

from pygit.domain.git.errors import GitError, NotAGitRepositoryError, RepositoryNotFoundError

if TYPE_CHECKING:
    from pathlib import Path

    from pygit.domain.git.cli import GitCli


def _open(path: Path) -> pygit2.Repository:
    if not path.exists():
        raise RepositoryNotFoundError(str(path))
    discovered = pygit2.discover_repository(str(path))
    if discovered is None:
        raise NotAGitRepositoryError(str(path))
    return pygit2.Repository(discovered)


@dataclass(slots=True, frozen=True)
class StatusEntry:
    path: str
    is_staged: bool
    is_modified: bool
    is_new: bool
    is_deleted: bool
    is_renamed: bool
    is_conflict: bool


@dataclass(slots=True, frozen=True)
class CommitOptions:
    summary: str
    body: str = ""
    author_name: str | None = None
    author_email: str | None = None
    amend: bool = False
    sign_off: bool = False
    skip_hooks: bool = False  # honored by GitCli path; libgit2 doesn't run hooks


# --- Status --------------------------------------------------------------------


def list_status(repo_path: Path) -> list[StatusEntry]:
    repo = _open(repo_path)
    out: list[StatusEntry] = []
    for path, flags in repo.status().items():
        out.append(
            StatusEntry(
                path=path,
                is_staged=bool(
                    flags
                    & (
                        getattr(pygit2, "GIT_STATUS_INDEX_NEW", 1 << 0)
                        | getattr(pygit2, "GIT_STATUS_INDEX_MODIFIED", 1 << 1)
                        | getattr(pygit2, "GIT_STATUS_INDEX_DELETED", 1 << 2)
                        | getattr(pygit2, "GIT_STATUS_INDEX_RENAMED", 1 << 3)
                        | getattr(pygit2, "GIT_STATUS_INDEX_TYPECHANGE", 1 << 4)
                    )
                ),
                is_modified=bool(flags & getattr(pygit2, "GIT_STATUS_WT_MODIFIED", 1 << 8)),
                is_new=bool(flags & getattr(pygit2, "GIT_STATUS_WT_NEW", 1 << 7)),
                is_deleted=bool(flags & getattr(pygit2, "GIT_STATUS_WT_DELETED", 1 << 9)),
                is_renamed=bool(flags & getattr(pygit2, "GIT_STATUS_WT_RENAMED", 1 << 11)),
                is_conflict=bool(flags & getattr(pygit2, "GIT_STATUS_CONFLICTED", 1 << 15)),
            )
        )
    return out


# --- Staging -------------------------------------------------------------------


def stage_paths(repo_path: Path, paths: list[str]) -> None:
    repo = _open(repo_path)
    index = repo.index
    for p in paths:
        index.add(p)
    index.write()


def unstage_paths(repo_path: Path, paths: list[str]) -> None:
    repo = _open(repo_path)
    index = repo.index
    if repo.head_is_unborn:
        # Without HEAD, the equivalent is `git rm --cached`.
        for p in paths:
            try:
                index.remove(p)
            except (KeyError, pygit2.GitError):
                continue
        index.write()
        return
    import contextlib

    head_commit = repo[repo.head.target]
    head_tree = head_commit.tree
    for p in paths:
        try:
            entry = head_tree[p]
        except KeyError:
            with contextlib.suppress(KeyError, pygit2.GitError):
                index.remove(p)
            continue
        index.add(pygit2.IndexEntry(p, entry.id, entry.filemode))
    index.write()


def discard_paths(repo_path: Path, paths: list[str]) -> None:
    """Restaura archivos del workdir al estado de HEAD/index. Destructivo."""
    repo = _open(repo_path)
    repo.checkout(paths=paths, strategy=pygit2.GIT_CHECKOUT_FORCE)


async def stage_hunk(cli: GitCli, repo_path: Path, file_path: str, patch_text: str) -> None:
    """Aplica ``git apply --cached`` con el patch parcial entregado.

    El UI construye el patch incluyendo sólo los hunks o líneas
    seleccionadas y lo pasa por stdin del proceso ``git``. Esto es
    equivalente a la opción ``-p`` (parcial) que ofrecen GitKraken/SmartGit.
    """
    # GitCli.run no soporta stdin todavía; usamos un asyncio.subprocess directo.
    import asyncio  # local import: este flujo es la única razón para subprocess

    proc = await asyncio.create_subprocess_exec(
        cli.executable,
        "apply",
        "--cached",
        "--whitespace=nowarn",
        "-p1",
        "-",
        cwd=str(repo_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _stdout_b, stderr_b = await proc.communicate(input=patch_text.encode("utf-8"))
    if proc.returncode != 0:
        raise GitError(
            f"git apply --cached failed (file={file_path}): "
            f"{stderr_b.decode('utf-8', 'replace').strip()}"
        )


# --- Commit --------------------------------------------------------------------


def _resolve_signature(repo: pygit2.Repository, options: CommitOptions) -> pygit2.Signature:
    name = options.author_name
    email = options.author_email
    if not name or not email:
        try:
            cfg = repo.config
            name = name or str(cfg["user.name"])
            email = email or str(cfg["user.email"])
        except KeyError as exc:
            raise GitError(
                "user.name/user.email not configured. Set them in git config "
                "or pass author_name/author_email to commit()."
            ) from exc
    return pygit2.Signature(name, email)


def _build_message(options: CommitOptions, repo: pygit2.Repository) -> str:
    title = options.summary.strip()
    body = options.body.strip()
    msg = title if not body else f"{title}\n\n{body}"
    if options.sign_off:
        sig = _resolve_signature(repo, options)
        trailer = f"Signed-off-by: {sig.name} <{sig.email}>"
        if trailer not in msg:
            msg = f"{msg}\n\n{trailer}" if msg else trailer
    return msg + "\n"


def commit(repo_path: Path, options: CommitOptions) -> str:
    """Crea un commit a partir del index actual. Devuelve la sha resultante.

    En modo ``amend`` se usa :meth:`pygit2.Repository.amend_commit` sobre el
    HEAD actual (pasar ``"HEAD"`` como ``ref`` en ``create_commit`` falla en
    libgit2 porque el nuevo commit no tiene HEAD como padre; ``amend_commit``
    reemplaza la ref por nosotros).
    """
    repo = _open(repo_path)
    index = repo.index
    tree_oid = index.write_tree()
    sig = _resolve_signature(repo, options)
    message = _build_message(options, repo)

    if options.amend:
        if repo.head_is_unborn:
            raise GitError("Cannot amend without an existing HEAD commit")
        head_commit = repo[repo.head.target]
        oid = repo.amend_commit(
            head_commit,
            "HEAD",
            author=sig,
            committer=sig,
            message=message,
            tree=tree_oid,
        )
        return str(oid)

    if repo.head_is_unborn:
        parents: list[pygit2.Oid] = []
    else:
        parents = [repo.head.target]
    oid = repo.create_commit("HEAD", sig, sig, message, tree_oid, parents)
    return str(oid)


# --- Branches ------------------------------------------------------------------


def create_branch(repo_path: Path, name: str, target_sha: str | None = None) -> None:
    repo = _open(repo_path)
    if target_sha is None:
        if repo.head_is_unborn:
            raise GitError("Cannot create branch in an unborn repository without target_sha")
        target_oid = repo.head.target
    else:
        target_oid = pygit2.Oid(hex=target_sha)
    target = repo[target_oid]
    if not isinstance(target, pygit2.Commit):
        raise GitError(f"Target {target_sha} is not a commit")
    repo.branches.local.create(name, target)


def delete_branch(repo_path: Path, name: str, *, force: bool = False) -> None:
    repo = _open(repo_path)
    branch = repo.branches.local.get(name)
    if branch is None:
        raise GitError(f"Branch {name!r} does not exist")
    if not force and branch.target != repo.head.target:
        # libgit2 no diferencia "merged"/"unmerged" en la API básica; el
        # caller debe pasar force=True tras confirmar.
        pass
    branch.delete()


def rename_branch(repo_path: Path, old_name: str, new_name: str) -> None:
    repo = _open(repo_path)
    branch = repo.branches.local.get(old_name)
    if branch is None:
        raise GitError(f"Branch {old_name!r} does not exist")
    branch.rename(new_name)


def checkout_branch(repo_path: Path, name: str) -> None:
    repo = _open(repo_path)
    branch = repo.branches.get(name)
    if branch is None:
        raise GitError(f"Branch {name!r} does not exist")
    repo.checkout(branch)


def set_upstream(repo_path: Path, branch_name: str, upstream: str | None) -> None:
    repo = _open(repo_path)
    branch = repo.branches.local.get(branch_name)
    if branch is None:
        raise GitError(f"Branch {branch_name!r} does not exist")
    branch.upstream_name = upstream


# --- Merge ---------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class MergeResult:
    fast_forward: bool
    up_to_date: bool
    conflicts: tuple[str, ...]
    new_head_sha: str | None


def merge_branch(
    repo_path: Path,
    other_name: str,
    *,
    no_ff: bool = False,
    squash: bool = False,
    options: CommitOptions | None = None,
) -> MergeResult:
    repo = _open(repo_path)
    if repo.head_is_unborn:
        raise GitError("Cannot merge in an unborn repository")
    other = repo.branches.get(other_name)
    if other is None:
        raise GitError(f"Branch {other_name!r} does not exist")
    other_oid = other.target
    analysis, _pref = repo.merge_analysis(other_oid)

    flag_up_to_date = getattr(pygit2, "GIT_MERGE_ANALYSIS_UP_TO_DATE", 1 << 1)
    flag_fastforward = getattr(pygit2, "GIT_MERGE_ANALYSIS_FASTFORWARD", 1 << 2)
    flag_normal = getattr(pygit2, "GIT_MERGE_ANALYSIS_NORMAL", 1 << 0)

    if analysis & flag_up_to_date:
        return MergeResult(False, True, (), None)

    if analysis & flag_fastforward and not no_ff and not squash:
        repo.checkout_tree(repo[other_oid])
        if not repo.head_is_detached:
            repo.references[repo.head.name].set_target(other_oid)
        return MergeResult(True, False, (), str(other_oid))

    if not (analysis & flag_normal or analysis & flag_fastforward):
        raise GitError(f"Cannot merge: analysis flags {analysis}")

    repo.merge(other_oid)
    if repo.index.conflicts:
        conflicts = tuple(c[0].path for c in repo.index.conflicts if c[0] is not None)
        return MergeResult(False, False, conflicts, None)

    tree_oid = repo.index.write_tree()
    sig = _resolve_signature(repo, options or CommitOptions(summary=f"Merge {other_name}"))
    msg = _build_message(options or CommitOptions(summary=f"Merge {other_name}"), repo)
    parents = [repo.head.target]
    if not squash:
        parents.append(other_oid)
    new_oid = repo.create_commit("HEAD", sig, sig, msg, tree_oid, parents)
    repo.state_cleanup()
    return MergeResult(False, False, (), str(new_oid))


# --- Stash ---------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class StashEntry:
    index: int
    sha: str
    message: str


def stash_save(
    repo_path: Path, message: str = "", *, include_untracked: bool = False
) -> str | None:
    """Guarda el WIP como un stash. Devuelve ``None`` si no hay nada.

    Libgit2 en versiones recientes acepta ``git_stash_save`` sobre workdirs
    limpios y crea un stash vacío; nosotros lo evitamos filtrando por
    ``status()`` antes — paridad con el comportamiento de ``git stash``
    ("No local changes to save").
    """
    repo = _open(repo_path)
    ignored_flag = getattr(pygit2, "GIT_STATUS_IGNORED", 1 << 14)
    has_changes = any(flags & ~ignored_flag for _, flags in repo.status().items())
    if not has_changes:
        return None
    sig = _resolve_signature(repo, CommitOptions(summary="stash"))
    flags = 0
    if include_untracked:
        flags |= getattr(pygit2, "GIT_STASH_INCLUDE_UNTRACKED", 1 << 1)
    try:
        oid = repo.stash(sig, message, flags)
    except (KeyError, pygit2.GitError):
        return None
    return str(oid)


def stash_list(repo_path: Path) -> list[StashEntry]:
    repo = _open(repo_path)
    out: list[StashEntry] = []
    for index, entry in enumerate(repo.listall_stashes()):
        out.append(StashEntry(index=index, sha=str(entry.commit_id), message=entry.message))
    return out


def stash_pop(repo_path: Path, index: int = 0) -> None:
    repo = _open(repo_path)
    repo.stash_pop(index=index)


def stash_apply(repo_path: Path, index: int = 0) -> None:
    repo = _open(repo_path)
    repo.stash_apply(index=index)


def stash_drop(repo_path: Path, index: int = 0) -> None:
    repo = _open(repo_path)
    repo.stash_drop(index=index)


# --- Tags ----------------------------------------------------------------------


def create_lightweight_tag(repo_path: Path, name: str, target_sha: str) -> None:
    repo = _open(repo_path)
    repo.references.create(f"refs/tags/{name}", pygit2.Oid(hex=target_sha))


def create_annotated_tag(repo_path: Path, name: str, target_sha: str, message: str) -> None:
    repo = _open(repo_path)
    sig = _resolve_signature(repo, CommitOptions(summary=message or name))
    target_oid = pygit2.Oid(hex=target_sha)
    repo.create_tag(name, target_oid, getattr(pygit2, "GIT_OBJECT_COMMIT", 1), sig, message)


def delete_tag(repo_path: Path, name: str) -> None:
    repo = _open(repo_path)
    ref = repo.references.get(f"refs/tags/{name}")
    if ref is None:
        raise GitError(f"Tag {name!r} does not exist")
    ref.delete()


# --- Reset ---------------------------------------------------------------------


def reset(repo_path: Path, target_sha: str, *, mode: str = "mixed") -> None:
    repo = _open(repo_path)
    target_oid = pygit2.Oid(hex=target_sha)
    if mode == "soft":
        flag = pygit2.GIT_RESET_SOFT
    elif mode == "mixed":
        flag = pygit2.GIT_RESET_MIXED
    elif mode == "hard":
        flag = pygit2.GIT_RESET_HARD
    else:
        raise ValueError(f"unknown reset mode: {mode!r}")
    repo.reset(target_oid, flag)


def revert_commit(repo_path: Path, sha: str) -> str:
    """Aplica el inverso del commit ``sha`` y crea un nuevo commit."""
    repo = _open(repo_path)
    target = repo.get(pygit2.Oid(hex=sha))
    if not isinstance(target, pygit2.Commit):
        raise GitError(f"{sha} is not a commit")
    repo.revert(target)
    if repo.index.conflicts:
        raise GitError("Revert produced conflicts; resolve them and commit manually")
    tree = repo.index.write_tree()
    sig = _resolve_signature(
        repo, CommitOptions(summary=f'Revert "{target.message.splitlines()[0]}"')
    )
    parents = [repo.head.target]
    new_oid = repo.create_commit(
        "HEAD",
        sig,
        sig,
        f'Revert "{target.message.splitlines()[0]}"\n\nThis reverts commit {sha}.\n',
        tree,
        parents,
    )
    repo.state_cleanup()
    return str(new_oid)


__all__ = [
    "CommitOptions",
    "MergeResult",
    "StashEntry",
    "StatusEntry",
    "checkout_branch",
    "commit",
    "create_annotated_tag",
    "create_branch",
    "create_lightweight_tag",
    "delete_branch",
    "delete_tag",
    "discard_paths",
    "list_status",
    "merge_branch",
    "rename_branch",
    "reset",
    "revert_commit",
    "set_upstream",
    "stage_hunk",
    "stage_paths",
    "stash_apply",
    "stash_drop",
    "stash_list",
    "stash_pop",
    "stash_save",
    "unstage_paths",
]
