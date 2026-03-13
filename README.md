# odoo-env

Odoo development environment using [mise](https://mise.jdx.dev/) and Git worktrees.
Supports working on multiple Odoo versions simultaneously in separate terminals.

## Prerequisites

- [mise](https://mise.jdx.dev/) installed with shell activation
- SSH access to `github.com/odoo` (private repos require Odoo employee access)
- Docker or Podman (optional but recommended) - useful to run services like postgres, pgweb, mailpit

### Activating mise in your shell

mise must be hooked into your shell to automatically activate environments
when entering a project directory:

```bash
# bash — add to ~/.bashrc
eval "$(mise activate bash)"

# zsh — add to ~/.zshrc
eval "$(mise activate zsh)"

# fish — add to ~/.config/fish/config.fish
mise activate fish | source
```

Once active, entering this repo automatically:
- Activates the Python venv (`.venv/`)
- Adds `scripts/` to `$PATH` (so `oo` works directly)

### Mise Setup

```bash
# Install toolchain (Python, Node.js)
mise install

# Bootstrap pip (one-time, creates pip in the venv)
mise run bootstrap
```

### System dependencies

```bash
# System build deps (for pip-based installs, non-Debian/Ubuntu)
xargs sudo apt install -y < apt-system-deps.txt

# On Debian/Ubuntu, prefer debinstall.sh (suggested by oo after setup)

# RTL CSS support
npm install -g rtlcss

# inotify support to reload your odoo server when python changes
sudo apt install python3-inotify

# PDF generation (Debian/Ubuntu only)
install-wkhtmltopdf
```

### Odoo Setup
```bash
# Declare your environments
cp odoo-env.toml.example odoo-env.toml
# Edit odoo-env.toml to set your branches and Odoo conf settings
```

## Usage

Environments are declared in `odoo-env.toml` at the repo root (gitignored).
Copy `odoo-env.toml.example` to get started and edit it to define your environments.

### Commands

| Command | Description |
|---------|-------------|
| `oo list` | List all profiles from odoo-env.toml |
| `oo activate <profile>` | Set up worktrees and launch a shell |
| `oo <profile>` | Shorthand for `activate` |
| `oo status` | Git status of worktrees (current profile, or all) |
| `oo rebase` | Fetch + rebase worktrees onto upstream (current profile, or all) |
| `oo remove <profile>` | Remove worktrees for a profile |
| `oo gen [--ide vscode\|zed\|all] <profile>` | Regenerate IDE workspace files |

`status` and `rebase` use the current active profile (detected via `$ODOO_ENV_NAME`)
when run inside an active shell, and operate on all profiles otherwise.

### Tab completion

Tab completion for subcommands and profile names (optional, requires `argcomplete`):

```bash
pip install argcomplete

# Bash/Zsh — add to ~/.bashrc or ~/.zshrc:
eval "$(register-python-argcomplete oo)"

# Fish — run once:
register-python-argcomplete --shell fish oo > ~/.config/fish/completions/oo.fish
```

## Git workflow with worktrees

Each branch lives in its own directory — no `git checkout` to switch context.
All worktrees share the same bare repo, so fetching from one updates refs for all.

### Start a feature

```bash
cd src/community/master
git fetch -p
git worktree add ../master-fix -b master-fix origin/master

cd ../master-fix
# ... edit code ...
git add .
git commit -m "[FIX] web: a great fix"
git push -u dev HEAD
```

### Rebase on updated master

```bash
cd src/community/master-fix  # or launch via oo
git fetch -p
git rebase origin/master             # detached HEAD — use origin/master, not master
git push --force-with-lease
```

### Fixup + autosquash

```bash
git commit --fixup=123abce
git rebase -i @~3 --autosquash
```

### Clean up after merge

```bash
oo remove my-project
```

This removes worktrees and deletes local feature branches automatically (unless another
profile in `odoo-env.toml` uses the same branch).

> `src/enterprise/` follows the same pattern.

## IDE Workspaces

Running `oo activate <profile>` automatically generates workspace configuration files for
VS Code and Zed in `workspaces/<profile>/`.
Configs are regenerated on every `activate` run. `workspaces/` is gitignored.

### VS Code

A `.code-workspace` file is generated at `workspaces/<profile>/<profile>.code-workspace`.
Open it directly from the terminal link shown after activation, or run:

```bash
code workspaces/<profile>/<profile>.code-workspace
```

The workspace configures:

- **Folders** scoped to each worktree (community, enterprise, custom repos)
- **Python interpreter** pointing to `.venv/bin/python3`
- **Ctrl+P (Quick Open)** finds files across all worktrees (`search.useIgnoreFiles: false`)
- **Heavy directories excluded** from indexing: `__pycache__`, `*.pyc`, `node_modules`
- **Odoo LSP** profile pre-selected (`Odoo.selectedProfile`)
- **Debug launch config** to start Odoo with debugpy using the generated `odoorc`
- **Integrated terminal** pre-loaded with `$ODOO_RC`, `$PYTHONPATH`, `$ODOO_PATH`, etc.

For the repo-level VS Code settings, copy the provided example on first clone:

```bash
cp .vscode/settings.json.example .vscode/settings.json
```

`.vscode/settings.json` is gitignored so your local settings are never committed.

### Zed

Open the environment directory in Zed:

```bash
zed workspaces/<profile>/zed/
```

Zed workspace includes:

- **Symlinks** to each worktree inside `workspaces/<profile>/zed/` (so Zed sees them as project roots)
- **`odoo-env` symlink** pointing to the repo root (access to scripts, configs, etc.)
- **`odools.toml` symlink** pointing to `odools.toml` at the repo root
- **`.zed/settings.json`** with Pyright and Odoo LSP config, terminal env vars, and file scan exclusions
- **`.zed/tasks.json`** with Start Odoo, Debug Shell, and Run Tests tasks
- **`.zed/launch.json`** with debugpy launch configurations

## Dev services (optional)

`compose.yml` provides Postgres+pgvector, a mail catcher, and a browser DB client.
These are opt-in — start them only if you need them.

```bash
mise run services       # start postgres, mailpit, pgweb
mise run services-down  # stop all
```

| Service | URL | Description |
|---------|-----|-------------|
| Postgres (+ pgvector) | `localhost:5432` | user/pass: `odoo/odoo` |
| Mailpit | `localhost:8025` | Mail catcher UI (SMTP on 1025) |
| pgweb | `localhost:8081` | Browser-based DB client |

If you have your own Postgres, skip `mise run services` and set DB connection
settings in `odoo-env.toml` under `[odoorc]` globally or `odoorc.X` per profile.

## Odoo configuration

`odoo-env.toml` (gitignored) declares profiles and Odoo conf settings.
`[odoorc]` holds global defaults; `odoorc.X = ...` inside a `[[profile]]` holds
per-profile overrides. `oo` merges these and sets `ODOO_RC` automatically — no need
to pass `--config` manually.

## Structure

```
odoo-env/
├── .cache/               # Gitignored runtime data
│   ├── git/              # Bare repositories
│   └── postgres-data/    # Postgres volume
├── workspaces/{name}/    # Gitignored generated workspace files
│   ├── odoorc                 # Merged Odoo config
│   ├── {name}.code-workspace  # VS Code workspace
│   └── zed/
│       ├── .zed/settings.json, tasks.json, launch.json
│       ├── community, enterprise, … → symlinks to src/
│       ├── odoo-env → symlink to repo root
│       └── odools.toml → symlink to repo root/odools.toml
├── src/                  # Worktrees (gitignored)
│   ├── community/{branch}/
│   └── enterprise/{branch}/
├── scripts/              # Auto-added to $PATH by mise
│   ├── oo
│   ├── install-wkhtmltopdf
│   ├── odoo-shell-aliases.sh
│   └── odoo-shell-aliases.fish
├── oo/                   # Python package
├── compose.yml
├── mise.toml
├── odoo-env.toml         # Gitignored — copy from .example
├── odoo-env.toml.example
└── odools.toml
```
