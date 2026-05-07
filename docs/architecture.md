# Arquitectura de pygit

> Documento vivo. Refleja la implementación a fecha del último commit y
> se ajusta al cierre de cada fase.

## Patrón general

MVVM con repositorio como agregado raíz. Inspirado en SourceGit
(Avalonia + CommunityToolkit.Mvvm), adaptado a Qt/PySide6.

```
┌─────────────────────────────────────────────────────────────┐
│                         Views (PySide6)                     │
│  GraphView · DiffView · CommitPanel · BranchTree · WipPanel │
│  PrPanel · CommandPalette · OnboardingWizard · Settings     │
└──────────────────────────────┬──────────────────────────────┘
                               │ signals/slots, data binding
┌──────────────────────────────▼──────────────────────────────┐
│                       ViewModels                            │
│  RepositoryVM (history, diff, status, undo, refs, PRs, AI)  │
└──────────────────────────────┬──────────────────────────────┘
                               │ async calls
┌──────────────────────────────▼──────────────────────────────┐
│                     Domain / Services                       │
│  GitEngine · GitCli · DiffEngine · BlameEngine · graph      │
│  writer · undo · remote · advanced · flow · lfs · worktrees │
│  HostingService (GitHub/…) · CredentialResolver · AiBackend │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  Infra: WorkerPool · AutoFetcher · config (TOML) · logging  │
│         keyring · plugin entry-points · themes loader       │
└─────────────────────────────────────────────────────────────┘
```

Regla de oro: **`domain/` no importa Qt**. El motor es testable headless
y reusable desde un futuro CLI.

## Threading model

| Trabajo | Hilo |
|---|---|
| Pintado Qt y operaciones < 16 ms | Hilo UI |
| pygit2 / subprocess (bloqueantes) | `WorkerPool` (`ThreadPoolExecutor`) |
| HTTP a hosting providers / AI | `asyncio` vía `qasync` |
| Watcher FS para WIP | (Fase 8: `QFileSystemWatcher` + debounce 250 ms) |
| Auto-fetch | `QTimer` cada 5 min, errores silenciados |

`qasync.QEventLoop` integra el loop asyncio con el event loop de Qt.
Tasks largas se almacenan en `_tasks: set[Task]` para evitar que el GC
las recoja antes de tiempo (RUF006).

## Motor Git: pygit2 vs git CLI

| Operación | Motor | Razón |
|---|---|---|
| `clone`, `fetch`, `push` | pygit2 | Callbacks finos para auth/progreso. |
| Walker / log / refs / blobs | pygit2 | Sin spawning, ideal para grafo. |
| `status`, `index`, staging por archivo | pygit2 | API estable. |
| Staging hunk-level | git CLI (`apply --cached`) | libgit2 Index sólo opera por archivo. |
| `blame`, `diff` low-level | pygit2 | Acceso al árbol y hunks por estructura. |
| `rebase -i` | git CLI + sequence editor | Doc en `domain.git.advanced`. |
| Hooks (pre-commit, etc.) | git CLI | libgit2 no ejecuta hooks. |
| `git lfs *` | git CLI | LFS no es libgit2. |
| `git flow *` | git CLI | Plugin externo. |
| `worktree add/remove` | pygit2 | API expuesta. |
| `worktree prune` | git CLI | libgit2 no lo soporta. |
| File history `--follow` | git CLI | libgit2 sin paridad estable. |
| Pickaxe `-S`/`-G` | git CLI | Motor de diff de Git. |

## Rebase interactivo

Driver basado en `GIT_SEQUENCE_EDITOR`:

1. La UI permite reordenar/cambiar acciones de los commits que va a
   rebasar.
2. Antes de invocar `git rebase -i <upstream>`, exportamos
   `GIT_SEQUENCE_EDITOR` apuntando al script auxiliar
   `pygit/resources/scripts/rebase_sequence_editor.py` y
   `PYGIT_REBASE_TODO` con el contenido completo del nuevo todo.
3. Git ejecuta nuestro script, que sobreescribe `git-rebase-todo` con
   el payload entregado y termina; el rebase prosigue como si el
   usuario hubiera editado el fichero a mano.

## Hosting providers

`detect_provider(remote_urls, token)` clasifica el host y devuelve la
implementación adecuada. v1.0 cubre **GitHub** completamente
(list/create/merge); GitLab, Bitbucket, Azure DevOps, Gitea quedan como
`_UnimplementedProvider` con `NotImplementedError` explícito hasta que
se priorice cada uno.

## AI

Backends conmutables (`OpenAi`, `Anthropic`, `Ollama`) implementados
sobre REST con `httpx` directo — sin SDKs propietarios.
**Privacy first**: `scrub_secrets()` ejecuta una pasada de regex
(estilo gitleaks) sobre el payload antes de hablar con cualquier
proveedor cloud; los locales (Ollama) lo saltan opcionalmente. Los
diffs jamás se envían sin filtrar.

## Plugins

Entry-point group `pygit.plugin.api.v1` (versionado para forward-compat).
La API expone `register_action`, `register_hosting_provider`,
`register_ai_backend`, `register_theme`. Los plugins corren in-process
pero sus errores se sandboxan: una excepción al cargar un plugin se
loggea y la app sigue arrancando.

## Themes

Carga JSON con `{name, kind, qss, graph_palette}`. La paleta del grafo
se inyecta en `GraphDelegate`; `qss` se aplica con
`QApplication.setStyleSheet`. Light, Dark, High-Contrast nativos
disponibles; los custom van en `~/.config/pygit/themes/*.json`
(o equivalente Windows AppData).

## Paquetería y empaquetado

- **Build backend**: hatchling (PEP 517).
- **Locking**: pip-tools (`requirements*.in` → `*.txt`).
- **Distribución**: PyInstaller `--onedir` → ZIP.
  Spec en `packaging/pygit.spec`; build con `packaging/build.ps1`.
  Sin instalador en v1.0; el usuario descarga el ZIP, descomprime y
  ejecuta `pygit.exe`.
- **Firma**: ninguna en v1.0. SmartScreen mostrará warning la primera
  vez (decisión registrada del propietario).

## Plataforma

Sólo **Windows x64** en v1.0. Implicaciones:

- Terminal embebida (futuro): `pywinpty`, sin fallback POSIX.
- Credenciales: `keyring` → backend `WinVaultKeyring`.
- File watchers: `ReadDirectoryChangesW` vía `QFileSystemWatcher`.
- Versión mínima de Git CLI: 2.20+. Features posteriores se gating
  con `GitVersion`.

## Estructura de paquetes

```
src/pygit/
  app/            entry point, bootstrap, contenedor de servicios
  domain/
    git/          engine, cli, diff, blame, graph, writer, undo,
                  remote, advanced (rebase/cherry-pick/reflog/hooks),
                  flow, lfs, worktrees, version, errors, models
    hosting/      providers (GitHub completo + stubs)
    ai/           backends (OpenAI/Anthropic/Ollama) + tasks + scrub
    credentials/  KeyringStore + SshKeyStore + CompositeResolver
    diff/
  infra/
    config/       TOML load + write con platformdirs
    logging/      structlog
    workers.py    ThreadPoolExecutor + asyncio.run_in_executor
    auto_fetch.py QTimer-based silent fetcher
    fs/  net/
  plugin/         entry-point discovery + PluginAPI
  ui/
    views/        MainWindow, RepositoryView, splash, onboarding,
                  settings_dialog
    viewmodels/   RepositoryVM
    widgets/      commits_table + graph_delegate, refs_tree, diff_view,
                  blame_view, wip_panel, dialogs, command_palette,
                  rebase_editor, pr_panel
    themes/       qdarkstyle wrapper + JSON loader
    i18n/         gettext + on-the-fly .mo compilation
  resources/
    icons/  themes/  translations/  scripts/
packaging/        pygit.spec + build.ps1
tests/            unit (domain) + UI (pytest-qt)
docs/             architecture.md (este documento)
```

## Riesgos abiertos / pendientes documentados

1. **Rebase no-interactivo (pull --rebase)**: pygit2 no expone una API
   no-interactiva limpia; actualmente caemos a merge_branch. Follow-up:
   delegar al CLI con `git rebase` no-interactivo cuando el usuario lo
   solicite.
2. **Resolutor de conflictos in-app 3-way**: alcance v1.0 = navegación
   + accept current/incoming/both + delegación a herramienta externa
   configurable. Editor 3-way propio movido a v1.1.
3. **PyInstaller + pygit2**: el spec incluye `collect_dynamic_libs`,
   pero requiere validación en CI Windows con un build real
   (Fase 7+ post-merge).
4. **Themes light/high-contrast**: el loader lee JSON; falta empaquetar
   ejemplos curados (light "rose-pine-dawn" y "high-contrast").
5. **Watchers de FS para WIP**: pendiente conectar
   `QFileSystemWatcher` + debounce 250 ms a `RepositoryVM.refresh()`.
6. **Hosting non-GitHub**: GitLab/Bitbucket/Azure/Gitea siguen como
   `_UnimplementedProvider`. Cada uno se incorpora cuando hay un
   usuario real con la necesidad.
7. **mypy --strict en CI**: aún no validado fin a fin (este entorno no
   tiene PySide6/pygit2 instalados; el CI Windows queda como single
   source of truth).
