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
- Adds `scripts/` to `$PATH` (so `odoo-env` works directly)

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

# On Debian/Ubuntu, prefer debinstall.sh (suggested by odoo-env after setup)

# RTL CSS support
npm install -g rtlcss

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
| `odoo-env list` | List all environments from odoo-env.toml |
| `odoo-env activate <env>` | Set up worktrees and launch a shell |
| `odoo-env <env>` | Shorthand for `activate` |
| `odoo-env status` | Git status of worktrees (current env, or all) |
| `odoo-env rebase` | Fetch + rebase worktrees onto upstream (current env, or all) |
| `odoo-env remove <env>` | Remove worktrees for an environment |

`status` and `rebase` use the current active environment (detected via `$ODOO_ENV_NAME`)
when run inside an active shell, and operate on all environments otherwise.

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
cd src/community/master-fix  # or launch via odoo-env
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
odoo-env remove my-project
```

This removes worktrees and deletes local feature branches automatically (unless another
environment in `odoo-env.toml` uses the same branch).

> `src/enterprise/` follows the same pattern.

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
settings in `odoo-env.toml` under `[env.odoorc]` or globally under `[_.odoorc]`.

## Odoo configuration

`odoo-env.toml` (gitignored) declares environments and Odoo conf settings.
`[_.odoorc]` holds global defaults; `[env.odoorc]` holds per-environment overrides.
`odoo-env` merges these and sets `ODOO_RC` automatically — no need to pass
`--config` manually.

## Structure

```
odoo-env/
├── .cache/               # Gitignored runtime data
│   ├── git/              # Bare repositories
│   ├── postgres-data/    # Postgres volume
│   └── envs/{name}/odoorc         # Generated merged config
├── src/                  # Worktrees (gitignored)
│   ├── community/{branch}/
│   └── enterprise/{branch}/
├── scripts/              # Auto-added to $PATH by mise
│   ├── odoo-env
│   └── install-wkhtmltopdf
├── compose.yml
├── mise.toml
├── odoo-env.toml         # Gitignored — copy from .example
├── odoo-env.toml.example
└── odools.toml
```
