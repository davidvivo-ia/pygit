"""Stack de undo/redo basado en snapshots de refs.

Antes de cada acción potencialmente reversible, el caller llama a
``snapshot(repo)`` y guarda el ``Snapshot`` en el stack. Para deshacer,
``restore(repo, snapshot)`` recoloca cada ref a su sha previa (sin tocar
el árbol más allá de actualizar HEAD si era simbólico).

Limitaciones aceptadas para v1.0:

- No revertimos cambios en el workdir; sólo en refs/HEAD/index.
- Si la operación creó/borró refs, restauramos sus valores guardados;
  refs nuevas no contempladas en el snapshot se eliminan al restaurar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygit2

from pygit.domain.git.errors import NotAGitRepositoryError, RepositoryNotFoundError

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(slots=True, frozen=True)
class Snapshot:
    label: str
    head_target: str
    head_is_symbolic: bool
    head_symbolic: str | None
    refs: dict[str, str]


def _open(path: Path) -> pygit2.Repository:
    if not path.exists():
        raise RepositoryNotFoundError(str(path))
    discovered = pygit2.discover_repository(str(path))
    if discovered is None:
        raise NotAGitRepositoryError(str(path))
    return pygit2.Repository(discovered)


def snapshot(repo_path: Path, label: str) -> Snapshot:
    repo = _open(repo_path)
    refs: dict[str, str] = {}
    for name in repo.references:
        try:
            ref = repo.references[name]
            target = ref.target
            if isinstance(target, str):
                # Symbolic reference: store it differently — we resolve via name.
                continue
            refs[name] = str(target)
        except (KeyError, pygit2.GitError):
            continue

    head_target = ""
    head_is_symbolic = False
    head_symbolic: str | None = None
    try:
        head = repo.lookup_reference("HEAD")
        if head.type == pygit2.GIT_REF_SYMBOLIC:
            head_is_symbolic = True
            head_symbolic = head.target  # type: ignore[assignment]
            try:
                head_target = str(repo.lookup_reference(head.target).target)
            except KeyError:
                head_target = ""
        else:
            head_target = str(head.target)
    except (KeyError, pygit2.GitError):
        pass

    return Snapshot(
        label=label,
        head_target=head_target,
        head_is_symbolic=head_is_symbolic,
        head_symbolic=head_symbolic,
        refs=refs,
    )


def restore(repo_path: Path, snap: Snapshot) -> None:
    repo = _open(repo_path)
    # Set every captured ref to its prior target.
    for name, target_sha in snap.refs.items():
        oid = pygit2.Oid(hex=target_sha)
        try:
            ref = repo.references.get(name)
            if ref is None:
                repo.references.create(name, oid)
            else:
                ref.set_target(oid)
        except (KeyError, pygit2.GitError):
            continue

    # Remove refs that exist now but did not exist in the snapshot
    # (only branches/tags — we leave HEAD and stash refs alone).
    current = set(repo.references)
    for name in current - set(snap.refs):
        if name == "HEAD":
            continue
        if not (name.startswith("refs/heads/") or name.startswith("refs/tags/")):
            continue
        try:
            repo.references[name].delete()
        except (KeyError, pygit2.GitError):
            continue

    # Restore HEAD.
    try:
        head = repo.lookup_reference("HEAD")
        if snap.head_is_symbolic and snap.head_symbolic:
            head.set_target(snap.head_symbolic)
        elif snap.head_target:
            head.set_target(pygit2.Oid(hex=snap.head_target))
    except (KeyError, pygit2.GitError):
        pass


__all__ = ["Snapshot", "restore", "snapshot"]
