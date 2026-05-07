# Arquitectura de pygit

> Documento vivo. Las decisiones marcadas como **provisional** se revalidan al
> entrar a la fase indicada.

## Patrón general

MVVM con repositorio como agregado raíz. Inspirado en SourceGit (Avalonia +
CommunityToolkit.Mvvm), adaptado a Qt/PySide6.

```
┌─────────────────────────────────────────────────────────────┐
│                         Views (PySide6)                     │
│  GraphView · DiffView · CommitPanel · BranchTree · Dialogs  │
└──────────────────────────────┬──────────────────────────────┘
                               │ signals/slots, data binding
┌──────────────────────────────▼──────────────────────────────┐
│                       ViewModels                            │
│  RepositoryVM · GraphVM · DiffVM · StashVM · ConflictVM ... │
└──────────────────────────────┬──────────────────────────────┘
                               │ async calls
┌──────────────────────────────▼──────────────────────────────┐
│                     Domain / Services                       │
│  GitEngine (pygit2) · GitCli (subprocess) · DiffEngine ·    │
│  HostingService · CredentialService · AIService · LfsService│
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│       Infraestructura: FS, red, llavero, config, i18n       │
└─────────────────────────────────────────────────────────────┘
```

Regla de oro: **`domain/` no importa Qt**. Esto asegura que el motor sea
testable headless y reutilizable desde un futuro CLI.

## Threading model

| Trabajo | Hilo |
|---|---|
| Pintado de Qt y operaciones < 16 ms | Hilo UI |
| Llamadas pygit2 / subprocess (bloqueantes) | `QThreadPool` (workers cancelables) |
| HTTP a hosting providers / AI | `asyncio` vía `qasync` |
| Watcher de FS para WIP | `QFileSystemWatcher` + debounce 250 ms |
| Auto-fetch | `QTimer` configurable (default 5 min) |

Toda llamada bloqueante > 50 ms va a worker. La UI nunca se congela.

`qasync.QEventLoop` integra el loop asyncio con el event loop de Qt; al cerrar
la última ventana, `QApplication.quit()` dispara `loop.stop()` y el bloque
`with loop:` libera limpiamente.

## Motor Git: pygit2 vs git CLI

Tabla de decisión (provisional, ampliable en Fases 1-4):

| Operación | Motor | Razón |
|---|---|---|
| `clone`, `fetch`, `push`, `pull` | pygit2 | Control fino sobre callbacks (auth, progreso). |
| Walker / log / refs / blobs | pygit2 | Sin spawning, ideal para el grafo. |
| `status`, `index`, staging hunk-level | pygit2 | API estable. |
| `blame`, `diff` low-level | pygit2 | Acceso al árbol y hunks por estructura. |
| `rebase -i` | git CLI | libgit2 no expone el todo-script editable. |
| Hooks (pre-commit, etc.) | git CLI | libgit2 no ejecuta hooks de usuario. |
| `git lfs *` | git CLI | LFS no es libgit2. |
| `git flow *` | git CLI | Plugin externo. |
| `worktree add/remove/prune` | git CLI | libgit2 sólo lectura básica. |
| `bisect` | git CLI | Workflow stateful en `.git/BISECT_*`. |

Tras cada operación CLI, las refs se invalidan en la capa pygit2 antes de
volver a leerse.

## Paquetería y empaquetado

- **Build backend**: hatchling (PEP 517).
- **Locking**: pip-tools (`requirements*.in` → `*.txt` cuando se estabilice).
- **Distribución**: PyInstaller `--onedir` → ZIP. Sin instalador en v1.0.
  - Razón: simplicidad operativa y zero-trust (no requiere admin para correr).
  - Trade-off aceptado: el usuario no obtiene shortcuts en menú Inicio ni
    asociación con `.git`. Se pospone a v1.1 si hay demanda.
- **Firma**: ninguna en v1.0. SmartScreen mostrará warning la primera vez.

## Plataforma

Solo **Windows x64** en v1.0. Implicaciones:

- Terminal embebida (futuro): `pywinpty`, sin fallback POSIX.
- Credenciales: `keyring` → backend nativo `WinVaultKeyring`.
- Watchers de FS: `ReadDirectoryChangesW` vía `QFileSystemWatcher`.
- Versión mínima de Git CLI: 2.20+ (Git for Windows). Features posteriores
  (`--force-with-lease=ref:expect`, `rebase --update-refs`, sparse-checkout v2,
  partial clone estable) requieren guards en runtime — un módulo `GitVersion`
  detectará el binario al arranque y deshabilitará features no disponibles.

## i18n

- `gettext` estándar.
- Fuentes `.po` versionadas; `.mo` compilados al vuelo en runtime con
  `babel.messages.mofile` (sin dependencia de `msgfmt` externo).
- Idiomas en v1.0: `es` (primario), `en`. Resto a partir de Fase 6.

## Configuración

- TOML, leída con `tomllib` (stdlib).
- Path por usuario vía `platformdirs.user_config_path("pygit", roaming=True)`.
- Por repo: en `.git/pygit/config.toml` (a partir de Fase 1).

## Licencias

| Componente | Licencia |
|---|---|
| pygit (este proyecto) | MIT |
| PySide6 | LGPLv3 |
| pygit2 / libgit2 | GPLv2 con linking exception (compatible con MIT) |
| qasync | BSD |
| qdarkstyle | MIT |
| qtawesome | MIT |
| Pygments | BSD |
| httpx, paramiko, cryptography, keyring, structlog, platformdirs, Babel | permisivas |

PyQt6 y QScintilla quedan **excluidas por defecto** (GPL).

## Riesgos abiertos (revisión por fase)

1. **Rendimiento del grafo (Fase 1)**: 50k commits, scroll 60 fps. Descartado
   `QGraphicsScene` con un item por commit. Plan: `QAbstractItemView` custom
   con scroll virtual y caché de paths.
2. **Empaquetado de pygit2 con PyInstaller**: hay que verificar que la libgit2
   binaria queda correctamente incluida en `--onedir`. Prototipar en Fase 0/7.
3. **Resolutor de conflictos 3-vías** in-app: alcance v1.0 = navegación + accept
   current/incoming/both + delegación a herramienta externa configurable. Editor
   propio completo se mueve a v1.1.
4. **Rebase interactivo visual (Fase 4)**: necesita `GIT_SEQUENCE_EDITOR`
   apuntando a un script auxiliar que lee instrucciones desde un fichero/socket
   gestionado por la app.
5. **AI: filtrado de secretos** antes de enviar diffs a proveedores externos.
   Obligatorio en Fase 6.
