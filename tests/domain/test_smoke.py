"""Smoke tests: importar todos los módulos, comprobar versión, config e i18n."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def test_version_present() -> None:
    import pygit

    assert pygit.__version__
    assert pygit.__version__.startswith("0.")


def test_imports() -> None:
    import pygit.app.bootstrap
    import pygit.app.container
    import pygit.app.main
    import pygit.domain.ai
    import pygit.domain.ai.tasks
    import pygit.domain.credentials
    import pygit.domain.diff
    import pygit.domain.git
    import pygit.domain.git.advanced
    import pygit.domain.git.blame
    import pygit.domain.git.cli
    import pygit.domain.git.diff
    import pygit.domain.git.engine
    import pygit.domain.git.errors
    import pygit.domain.git.flow
    import pygit.domain.git.graph
    import pygit.domain.git.lfs
    import pygit.domain.git.models
    import pygit.domain.git.remote
    import pygit.domain.git.undo
    import pygit.domain.git.version
    import pygit.domain.git.worktrees
    import pygit.domain.git.writer
    import pygit.domain.hosting
    import pygit.infra.auto_fetch
    import pygit.infra.config
    import pygit.infra.fs
    import pygit.infra.logging
    import pygit.infra.net
    import pygit.infra.workers
    import pygit.plugin
    import pygit.ui.i18n
    import pygit.ui.themes
    import pygit.ui.themes.loader
    import pygit.ui.viewmodels
    import pygit.ui.viewmodels.repository
    import pygit.ui.views.main_window
    import pygit.ui.views.onboarding
    import pygit.ui.views.repository_view
    import pygit.ui.views.settings_dialog
    import pygit.ui.views.splash
    import pygit.ui.widgets
    import pygit.ui.widgets.blame_view
    import pygit.ui.widgets.command_palette
    import pygit.ui.widgets.commits_table
    import pygit.ui.widgets.dialogs
    import pygit.ui.widgets.diff_view
    import pygit.ui.widgets.graph_delegate
    import pygit.ui.widgets.pr_panel
    import pygit.ui.widgets.rebase_editor
    import pygit.ui.widgets.refs_tree
    import pygit.ui.widgets.terminal
    import pygit.ui.widgets.wip_panel  # noqa: F401


def test_default_config_when_file_missing(tmp_path: Path) -> None:
    from pygit.infra.config import AppConfig, load_config

    cfg = load_config(path=tmp_path / "does-not-exist.toml")
    assert isinstance(cfg, AppConfig)
    assert cfg.ui.language == "es"
    assert cfg.ui.theme == "dark"


def test_load_config_from_file(tmp_path: Path) -> None:
    from pygit.infra.config import load_config

    target = tmp_path / "config.toml"
    target.write_text(
        '[ui]\nlanguage = "en"\ntheme = "light"\n',
        encoding="utf-8",
    )
    cfg = load_config(path=target)
    assert cfg.ui.language == "en"
    assert cfg.ui.theme == "light"


def test_i18n_install_es() -> None:
    from pygit.ui.i18n import gettext, install_translations

    install_translations("es")
    assert gettext("Ready") == "Listo"
    assert gettext("&File") == "&Archivo"


def test_i18n_install_en() -> None:
    from pygit.ui.i18n import gettext, install_translations

    install_translations("en")
    assert gettext("Ready") == "Ready"
