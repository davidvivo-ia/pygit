"""ViewModel de un repositorio abierto.

Coordina llamadas al :class:`GitEngine` y al módulo
:mod:`pygit.domain.git.writer` (en hilos worker) con la UI vía señales Qt.
La VM **no** ejecuta ``pygit2`` en el hilo UI: cualquier acceso pasa por
:meth:`WorkerPool.submit`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from pygit.domain.credentials import KeyringStore, build_default_resolver
from pygit.domain.git import advanced, undo, writer
from pygit.domain.git import remote as remote_ops
from pygit.domain.git.diff import DiffEngine
from pygit.domain.git.graph import assign_lanes
from pygit.domain.hosting import detect_provider

if TYPE_CHECKING:
    from pathlib import Path

    from pygit.domain.git.diff import DiffResult
    from pygit.domain.git.engine import GitEngine
    from pygit.domain.git.graph import GraphRow
    from pygit.domain.git.models import (
        BranchRef,
        CommitSummary,
        HeadInfo,
        RemoteRef,
        TagRef,
    )
    from pygit.domain.git.undo import Snapshot
    from pygit.domain.git.writer import CommitOptions, StatusEntry
    from pygit.infra.workers import WorkerPool


class RepositoryVM(QObject):
    """Estado y operaciones de un repositorio en la UI."""

    head_changed = Signal(object)
    branches_changed = Signal(list)
    tags_changed = Signal(list)
    remotes_changed = Signal(list)
    pull_requests_changed = Signal(list)
    history_changed = Signal(list, list)
    status_changed = Signal(list)
    path_changed = Signal(object)
    diff_changed = Signal(object)
    undo_state_changed = Signal(int, int)  # (undo_size, redo_size)
    error = Signal(str)
    info = Signal(str)

    def __init__(self, engine: GitEngine, workers: WorkerPool) -> None:
        super().__init__()
        self._engine = engine
        self._workers = workers
        self._diff = DiffEngine()
        self._credentials = build_default_resolver()
        self._path: Path | None = None
        self._head: HeadInfo | None = None
        self._undo: list[Snapshot] = []
        self._redo: list[Snapshot] = []

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def head(self) -> HeadInfo | None:
        return self._head

    async def open(self, path: Path) -> None:
        try:
            resolved = await self._workers.submit(self._engine.discover, path)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self._path = resolved
        self.path_changed.emit(resolved)
        await self.refresh()

    async def refresh(self) -> None:
        if self._path is None:
            return
        path = self._path
        try:
            head: HeadInfo = await self._workers.submit(self._engine.head, path)
            branches: list[BranchRef] = await self._workers.submit(self._engine.branches, path)
            tags: list[TagRef] = await self._workers.submit(self._engine.tags, path)
            remotes: list[RemoteRef] = await self._workers.submit(self._engine.remotes, path)
            history: list[CommitSummary] = await self._workers.submit(
                self._engine.walk_history, path
            )
            graph: list[GraphRow] = await self._workers.submit(assign_lanes, history)
            status: list[StatusEntry] = await self._workers.submit(writer.list_status, path)
        except Exception as exc:
            self.error.emit(str(exc))
            return

        self._head = head
        self.head_changed.emit(head)
        self.branches_changed.emit(branches)
        self.tags_changed.emit(tags)
        self.remotes_changed.emit(remotes)
        self.history_changed.emit(history, graph)
        self.status_changed.emit(status)

    async def select_commit(self, sha: str) -> None:
        if self._path is None:
            return
        try:
            diff: DiffResult = await self._workers.submit(
                self._diff.diff_commit_to_parent, self._path, sha
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.diff_changed.emit(diff)

    # --- Writes (with undo snapshot) --------------------------------------------

    async def _capture_snapshot(self, label: str) -> None:
        if self._path is None:
            return
        snap = await self._workers.submit(undo.snapshot, self._path, label)
        self._undo.append(snap)
        self._redo.clear()
        self.undo_state_changed.emit(len(self._undo), len(self._redo))

    async def _emit_undo_state(self) -> None:
        self.undo_state_changed.emit(len(self._undo), len(self._redo))

    async def stage_paths(self, paths: list[str]) -> None:
        if self._path is None or not paths:
            return
        try:
            await self._workers.submit(writer.stage_paths, self._path, paths)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def unstage_paths(self, paths: list[str]) -> None:
        if self._path is None or not paths:
            return
        try:
            await self._workers.submit(writer.unstage_paths, self._path, paths)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def discard_paths(self, paths: list[str]) -> None:
        if self._path is None or not paths:
            return
        try:
            await self._workers.submit(writer.discard_paths, self._path, paths)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def commit(self, options: CommitOptions) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"commit: {options.summary[:40]}")
        try:
            sha = await self._workers.submit(writer.commit, self._path, options)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.info.emit(f"committed {sha[:7]}")
        await self.refresh()

    async def create_branch(self, name: str, target_sha: str | None = None) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"branch+: {name}")
        try:
            await self._workers.submit(writer.create_branch, self._path, name, target_sha)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def delete_branch(self, name: str, *, force: bool = False) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"branch-: {name}")
        try:
            await self._workers.submit(writer.delete_branch, self._path, name, force=force)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def rename_branch(self, old_name: str, new_name: str) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"branch~: {old_name}→{new_name}")
        try:
            await self._workers.submit(writer.rename_branch, self._path, old_name, new_name)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def checkout_branch(self, name: str) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"checkout: {name}")
        try:
            await self._workers.submit(writer.checkout_branch, self._path, name)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def merge_branch(self, name: str, *, no_ff: bool = False, squash: bool = False) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"merge: {name}")
        try:
            result = await self._workers.submit(
                writer.merge_branch, self._path, name, no_ff=no_ff, squash=squash
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        if result.conflicts:
            self.error.emit(f"merge produced {len(result.conflicts)} conflicts")
        else:
            self.info.emit("merge ok" if not result.up_to_date else "already up-to-date")
        await self.refresh()

    async def stash_save(self, message: str = "", *, include_untracked: bool = False) -> None:
        if self._path is None:
            return
        await self._capture_snapshot("stash save")
        try:
            await self._workers.submit(
                writer.stash_save, self._path, message, include_untracked=include_untracked
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def stash_pop(self, index: int = 0) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"stash pop {index}")
        try:
            await self._workers.submit(writer.stash_pop, self._path, index)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def create_tag(self, name: str, target_sha: str, *, message: str = "") -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"tag+: {name}")
        try:
            if message:
                await self._workers.submit(
                    writer.create_annotated_tag, self._path, name, target_sha, message
                )
            else:
                await self._workers.submit(
                    writer.create_lightweight_tag, self._path, name, target_sha
                )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def delete_tag(self, name: str) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"tag-: {name}")
        try:
            await self._workers.submit(writer.delete_tag, self._path, name)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    async def reset(self, target_sha: str, *, mode: str = "mixed") -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"reset {mode} {target_sha[:7]}")
        try:
            await self._workers.submit(writer.reset, self._path, target_sha, mode=mode)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    # --- Remote ops -----------------------------------------------------------

    async def fetch(self, remote: str = "origin", *, prune: bool = False) -> None:
        if self._path is None:
            return
        try:
            await self._workers.submit(
                remote_ops.fetch, self._path, remote, prune=prune, credentials=self._credentials
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.info.emit(f"fetched from {remote}")
        await self.refresh()

    async def pull(
        self, remote: str = "origin", *, rebase: bool = False, ff_only: bool = False
    ) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"pull {remote}")
        try:
            await self._workers.submit(
                remote_ops.pull,
                self._path,
                remote,
                rebase=rebase,
                ff_only=ff_only,
                credentials=self._credentials,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.info.emit(f"pulled from {remote}")
        await self.refresh()

    async def push(self, remote: str = "origin", *, force: bool = False) -> None:
        if self._path is None:
            return
        try:
            await self._workers.submit(
                remote_ops.push,
                self._path,
                remote,
                force=force,
                credentials=self._credentials,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.info.emit(f"pushed to {remote}")
        await self.refresh()

    # --- Advanced -------------------------------------------------------------

    async def cherry_pick(self, shas: list[str]) -> None:
        if self._path is None or not shas:
            return
        await self._capture_snapshot(f"cherry-pick {len(shas)}")
        try:
            results = await self._workers.submit(advanced.cherry_pick, self._path, shas)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        for result in results:
            if result.conflicts:
                self.error.emit(f"cherry-pick produced conflicts on {result.sha_in[:7]}")
                break
        await self.refresh()

    async def reflog(self, *, limit: int = 200) -> list[advanced.ReflogEntry]:
        if self._path is None:
            return []
        try:
            return await self._workers.submit(advanced.reflog, self._path, limit=limit)
        except Exception as exc:
            self.error.emit(str(exc))
            return []

    async def list_hooks(self) -> list[advanced.HookEntry]:
        if self._path is None:
            return []
        try:
            return await self._workers.submit(advanced.list_hooks, self._path)
        except Exception as exc:
            self.error.emit(str(exc))
            return []

    async def set_hook_enabled(self, name: str, enabled: bool) -> None:
        if self._path is None:
            return
        try:
            await self._workers.submit(advanced.set_hook_enabled, self._path, name, enabled)
        except Exception as exc:
            self.error.emit(str(exc))

    # --- Hosting / PRs --------------------------------------------------------

    async def list_pull_requests(self) -> None:
        if self._path is None:
            return
        try:
            remotes = await self._workers.submit(self._engine.remotes, self._path)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        urls = [r.fetch_url for r in remotes]
        # Token: hostname → keyring
        provider = None
        for url in urls:
            from pygit.domain.hosting import parse_remote_url

            repo = parse_remote_url(url)
            if repo is None:
                continue
            cred = KeyringStore().lookup(repo.host)
            token = cred[1] if cred else None
            provider = detect_provider([url], token=token)
            if provider is not None:
                break
        if provider is None:
            self.info.emit("no hosting provider detected")
            self.pull_requests_changed.emit([])
            return
        try:
            prs = await provider.list_pull_requests()
        except Exception as exc:
            self.error.emit(f"PR list failed: {exc}")
            return
        self.pull_requests_changed.emit(prs)

    async def create_pull_request(
        self, title: str, body: str, source: str, target: str, *, draft: bool = False
    ) -> None:
        if self._path is None:
            return
        try:
            remotes = await self._workers.submit(self._engine.remotes, self._path)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        provider = None
        for r in remotes:
            from pygit.domain.hosting import parse_remote_url

            repo = parse_remote_url(r.fetch_url)
            if repo is None:
                continue
            cred = KeyringStore().lookup(repo.host)
            token = cred[1] if cred else None
            provider = detect_provider([r.fetch_url], token=token)
            if provider is not None:
                break
        if provider is None:
            self.error.emit("no hosting provider with credentials")
            return
        try:
            pr = await provider.create_pull_request(title, body, source, target, draft=draft)
        except Exception as exc:
            self.error.emit(f"PR create failed: {exc}")
            return
        self.info.emit(f"PR #{pr.number} created")
        await self.list_pull_requests()

    async def merge_pull_request(self, number: int, *, method: str = "merge") -> None:
        if self._path is None:
            return
        try:
            remotes = await self._workers.submit(self._engine.remotes, self._path)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        provider = None
        for r in remotes:
            from pygit.domain.hosting import parse_remote_url

            repo = parse_remote_url(r.fetch_url)
            if repo is None:
                continue
            cred = KeyringStore().lookup(repo.host)
            token = cred[1] if cred else None
            provider = detect_provider([r.fetch_url], token=token)
            if provider is not None:
                break
        if provider is None:
            self.error.emit("no hosting provider with credentials")
            return
        try:
            await provider.merge_pull_request(number, method=method)
        except Exception as exc:
            self.error.emit(f"PR merge failed: {exc}")
            return
        self.info.emit(f"PR #{number} merged ({method})")
        await self.list_pull_requests()
        await self.fetch(prune=True)

    # --- AI helpers -----------------------------------------------------------

    async def ai_commit_message(self, ai_config: object) -> str | None:
        """Genera un mensaje de commit a partir del diff staged.

        ``ai_config`` debe ser :class:`pygit.domain.ai.AiConfig`. Si el
        usuario no opta por AI, el caller no debería llamar a este método.
        """
        from pygit.domain.ai import AiConfig, build_backend
        from pygit.domain.ai.tasks import generate_commit_message

        if not isinstance(ai_config, AiConfig):
            return None
        if self._path is None:
            return None
        try:
            diff = await self._workers.submit(self._diff.diff_index_to_head, self._path)
        except Exception as exc:
            self.error.emit(str(exc))
            return None
        # Render text diff for the prompt.
        chunks: list[str] = []
        for f in diff.files:
            chunks.append(
                f"diff --git a/{f.old_path or ''} b/{f.new_path or ''}\n[{f.status.value}]"
            )
            for h in f.hunks:
                chunks.append(h.header)
                for line in h.lines:
                    chunks.append(f"{line.origin.value}{line.content}")
        text = "\n".join(chunks)
        backend = build_backend(ai_config)
        try:
            message = await generate_commit_message(
                backend, text, scrub=ai_config.provider != "ollama"
            )
        except Exception as exc:
            self.error.emit(f"AI failed: {exc}")
            return None
        return message

    async def revert_commit(self, sha: str) -> None:
        if self._path is None:
            return
        await self._capture_snapshot(f"revert {sha[:7]}")
        try:
            await self._workers.submit(writer.revert_commit, self._path, sha)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        await self.refresh()

    # --- Undo / Redo -----------------------------------------------------------

    async def undo(self) -> None:
        if self._path is None or not self._undo:
            return
        snap = self._undo.pop()
        # Capture forward snapshot for redo before restoring.
        forward = await self._workers.submit(undo.snapshot, self._path, f"redo:{snap.label}")
        self._redo.append(forward)
        try:
            await self._workers.submit(undo.restore, self._path, snap)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.info.emit(f"undid: {snap.label}")
        self.undo_state_changed.emit(len(self._undo), len(self._redo))
        await self.refresh()

    async def redo(self) -> None:
        if self._path is None or not self._redo:
            return
        snap = self._redo.pop()
        backward = await self._workers.submit(undo.snapshot, self._path, f"undo:{snap.label}")
        self._undo.append(backward)
        try:
            await self._workers.submit(undo.restore, self._path, snap)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.info.emit(f"redid: {snap.label}")
        self.undo_state_changed.emit(len(self._undo), len(self._redo))
        await self.refresh()


__all__ = ["RepositoryVM"]
