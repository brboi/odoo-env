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
- Adds `scripts/` to `$PATH` (so `odoo-env` and `setup-odoo-repository` work directly)

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
# Initialize bare repositories
setup-odoo-repository odoo
setup-odoo-repository enterprise

# Create worktrees (wizard runs on first use; suggests how to install Python deps at the end)
odoo-env my-project --setup-only
```

## Usage

Each environment has a name you choose freely (e.g. `my-project`, `fix-invoice`, `review-pr-42`).
The first time you use a name, an interactive wizard asks for the branches and port.
Settings are saved to `.cache/envs/<name>.toml` and reused on subsequent runs.

### Examples

```bash
# First use: wizard runs, then launches shell
odoo-env my-project

# Subsequent uses: loads saved settings immediately
odoo-env my-project

# Re-run the wizard to change branches or port
odoo-env my-project --reconfigure

# List all configured environments
odoo-env --list

# Print env vars only (useful for eval)
eval "$(odoo-env my-project --print-env)"
```

### Interactive wizard

When creating a new environment, the wizard asks:

1. **Base Odoo branch** — e.g. `master`, `18.0`, `17.0`
2. **Branch per extra repo** — per repo found in `.cache/git/`, defaults to the base branch
3. **HTTP port** — defaults to `8069`

### Options

| Flag | Description |
|------|-------------|
| `--list` | List all configured environments |
| `--reconfigure` | Re-run the interactive setup wizard |
| `--port PORT` | Override HTTP port for this run (not saved) |
| `--setup-only` | Create worktrees without launching a shell |
| `--print-env` | Print `export` statements instead of launching a shell |

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

If you have your own Postgres, skip `mise run services` and create
`config/odoo.local.conf` to override the DB connection settings
(see `config/odoo.local.conf.example`).

## Odoo configuration

`config/odoo.conf` is committed with base settings pointing to the compose
stack. `odoo-env` merges it with `config/odoo.local.conf` (if present) and
sets `ODOO_RC` automatically — no need to pass `--config` manually.

## Structure

```
odoo-env/
├── .cache/               # Gitignored runtime data
│   ├── git/              # Bare repositories
│   ├── envs/             # Saved environment settings (TOML)
│   ├── postgres-data/    # Postgres volume
│   └── sessions/{name}/odoo.conf  # Generated merged config
├── src/                  # Worktrees (gitignored)
│   ├── community/{branch}/
│   └── enterprise/{branch}/
├── config/
│   ├── odoo.conf
│   └── odoo.local.conf.example
├── scripts/              # Auto-added to $PATH by mise
│   ├── odoo-env
│   ├── setup-odoo-repository
│   └── install-wkhtmltopdf
├── compose.yml
├── mise.toml
└── odools.toml
```
