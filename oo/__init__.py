"""oo — Odoo development environment manager."""
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / ".cache" / "git"
SRC_DIR = ROOT_DIR / "src"
WORKSPACES_DIR = ROOT_DIR / "workspaces"

# Re-export public API for test access via `import oo as mod`
from oo.ui import hyperlink, log_info, log_ok, log_warn, log_error, RED, GREEN, YELLOW, BLUE, NC  # noqa: E402, F401
from oo.config import (  # noqa: E402, F401
    BranchSpec, Profile, Config,
    load_config, list_profiles, get_profile, parse_branch_spec,
    profile_branch_specs, profile_remote_urls, profile_odoorc, profile_options,
    adhoc_profile,
)
from oo.git import (  # noqa: E402, F401
    git_wt, stable_base, branch_to_dir, parse_pr,
    deduce_runbot_bundles, runbot_bundle_urls,
    remotes, dev_remote_exists, setup_bare_repo, fetch_repo,
    find_ref, local_branch_exists, resolve_pr_branch, find_or_add_remote,
    ensure_worktree, setup_js_tooling, github_pr_url, fetch_pr_title,
    REVERSE_ALIAS, RUNBOT_BASE_URL, _pr_annotation,
)
from oo.workspace import (  # noqa: E402, F401
    discover_addons_paths, build_paths, profile_worktree_paths,
    generate_vscode_workspace, generate_zed_workspace,
    generate_odools_config,
)
from oo.shell import build_odoo_conf  # noqa: E402, F401
from oo.cli import (  # noqa: E402, F401
    cmd_list, cmd_status, cmd_rebase, cmd_remove, cmd_activate, cmd_gen,
)
