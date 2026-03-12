"""CLI commands for the oo tool."""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import argcomplete
except ImportError:
    argcomplete = None

import argparse

import oo.git as _git
from oo.config import (
    Config, BranchSpec,
    load_config, list_profiles, get_profile,
    profile_branch_specs, profile_remote_urls, profile_odoorc, profile_options,
    adhoc_profile,
)
from oo.git import (
    git_wt, branch_to_dir, parse_pr, stable_base,
    ensure_worktree, fetch_repo, setup_bare_repo, setup_js_tooling,
    local_branch_exists, deduce_runbot_bundles, runbot_bundle_urls,
    _pr_annotation,
)
from oo.workspace import (
    build_paths, generate_vscode_workspace, generate_zed_workspace,
    generate_idea_project, generate_odools_config, profile_worktree_paths,
)
from oo.shell import build_odoo_conf, launch_shell
from oo.ui import log_info, log_ok, log_warn, log_error, GREEN, BLUE, YELLOW, RED, NC, hyperlink


def cmd_list(config: Config) -> None:
    """List all profiles and their branch specs."""
    profiles = list_profiles(config)
    if profiles:
        print("Configured profiles:")
        for name in profiles:
            profile = get_profile(config, name)
            repos_info = ", ".join(
                f"{repo}@{spec.branch}" for repo, spec in profile.branch_specs.items()
            )
            print(f"  {GREEN}{name}{NC}  ({repos_info})")
    else:
        print("No profiles configured in odoo-env.toml.")


def cmd_status(profile_names: list[str], config: Config) -> None:
    """Show git status (branch, ahead/behind, dirty) for each worktree."""
    import oo as _pkg
    for profile_name in profile_names:
        print(f"\n{BLUE}{profile_name}{NC}")
        branch_specs = profile_branch_specs(config, profile_name)
        resolved_pr_branches: dict[str, str] = {}

        for repo, spec in branch_specs.items():
            branch = spec.branch
            branch_dir = branch_to_dir(branch)
            worktree_path = _pkg.SRC_DIR / repo / branch_dir
            pr_spec = parse_pr(branch)

            if not worktree_path.is_dir():
                annotation = ""
                if pr_spec:
                    bare_path = _pkg.CACHE_DIR / f"{repo}.git"
                    annotation = _pr_annotation(bare_path, pr_spec)
                print(f"  {YELLOW}{repo}@{branch}{NC}  [not created]{annotation}")
                continue

            head = git_wt(worktree_path, "symbolic-ref", "--short", "HEAD", check=False, capture=True)
            current_branch = head.stdout.decode().strip() if head.returncode == 0 else "(detached)"

            ab = git_wt(worktree_path, "rev-list", "--left-right", "--count", "@{u}...HEAD",
                        check=False, capture=True)
            if ab.returncode == 0:
                parts = ab.stdout.decode().strip().split()
                ab_str = f"↓{parts[0]} ↑{parts[1]}"
            else:
                ab_str = "(no upstream)"

            dirty = git_wt(worktree_path, "status", "--porcelain", check=False, capture=True)
            dirty_str = f"  {RED}*dirty*{NC}" if dirty.stdout.decode().strip() else ""

            annotation = ""
            if pr_spec:
                bare_path = _pkg.CACHE_DIR / f"{repo}.git"
                annotation = _pr_annotation(bare_path, pr_spec)
                resolved_pr_branches[branch] = current_branch

            print(f"  {GREEN}{repo}{NC}@{current_branch}  {ab_str}{dirty_str}{annotation}")

        repo_branches_str = {repo: spec.branch for repo, spec in branch_specs.items()}
        bundles = deduce_runbot_bundles(repo_branches_str, resolved_pr_branches)
        for bundle, url in zip(bundles, runbot_bundle_urls(bundles)):
            print(f"  {BLUE}{hyperlink('runbot: ' + bundle, url)}{NC}")


def cmd_rebase(profile_names: list[str], config: Config) -> None:
    """Fetch bare repos and rebase tracking worktrees onto their upstream (or declared base)."""
    import oo as _pkg

    worktree_infos = []  # [(repo, branch, worktree_path, remote, upstream_branch, declared_base)]

    for profile_name in profile_names:
        branch_specs = profile_branch_specs(config, profile_name)
        for repo, spec in branch_specs.items():
            branch = spec.branch
            branch_dir = branch_to_dir(branch)
            worktree_path = _pkg.SRC_DIR / repo / branch_dir
            if not worktree_path.is_dir():
                log_warn(f"Worktree not found, skipping: {worktree_path}")
                continue

            head = git_wt(worktree_path, "symbolic-ref", "HEAD", check=False, capture=True)
            if head.returncode != 0:
                log_warn(f"Detached HEAD in {worktree_path}, skipping rebase")
                continue

            declared_base = spec.rebase_base  # e.g. "origin/master" from arrow syntax
            if declared_base:
                remote, _, upstream_branch = declared_base.partition("/")
                if not upstream_branch:
                    remote, upstream_branch = "origin", declared_base
                worktree_infos.append((repo, branch, worktree_path, remote, upstream_branch, declared_base))
            else:
                upstream = git_wt(worktree_path, "rev-parse", "--abbrev-ref", "@{u}", check=False, capture=True)
                if upstream.returncode != 0:
                    log_warn(f"No upstream configured for {repo}@{branch}, skipping rebase")
                    continue
                upstream_ref = upstream.stdout.decode().strip()
                remote, _, upstream_branch = upstream_ref.partition("/")
                worktree_infos.append((repo, branch, worktree_path, remote, upstream_branch, None))

    repo_urls: dict[str, str] = {}
    for profile_name in profile_names:
        repo_urls.update(profile_remote_urls(config, profile_name))

    fetch_tasks: set[tuple[str, str, str]] = {
        (repo, remote, upstream_branch)
        for repo, _, _, remote, upstream_branch, _ in worktree_infos
    }

    def fetch_specific(repo: str, remote: str, upstream_branch: str) -> None:
        bare_path = _pkg.CACHE_DIR / f"{repo}.git"
        if not bare_path.is_dir():
            log_info(f"Bare repo not found for '{repo}', setting it up automatically...")
            setup_bare_repo(repo, url=repo_urls.get(repo))
        log_info(f"Fetching {repo} {upstream_branch} ({remote})...")
        result = _git.git(bare_path, "fetch", remote, upstream_branch, check=False)
        if result.returncode != 0:
            log_warn(f"Could not fetch {repo}/{upstream_branch} from {remote}")

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(fetch_specific, repo, remote, upstream_branch): (repo, remote, upstream_branch)
            for repo, remote, upstream_branch in sorted(fetch_tasks)
        }
        for future in as_completed(futures):
            future.result()

    for repo, branch, worktree_path, remote, upstream_branch, declared_base in worktree_infos:
        rebase_onto = declared_base if declared_base else "@{u}"
        log_info(f"Rebasing {repo}@{branch} onto {rebase_onto}...")
        result = git_wt(worktree_path, "rebase", "--autostash", rebase_onto, check=False)
        if result.returncode != 0:
            log_warn(f"Rebase failed for {repo}@{branch} — resolve manually")
        else:
            log_ok(f"Rebased: {repo}@{branch}")


def cmd_remove(profile_name: str, config: Config, force: bool = False) -> None:
    """Remove worktrees for the given profile."""
    import oo as _pkg
    branch_specs = profile_branch_specs(config, profile_name)

    other_branch_usage: set[tuple[str, str]] = set()
    for other_profile in config.profiles:
        if other_profile.name == profile_name:
            continue
        for repo, spec in other_profile.branch_specs.items():
            other_branch_usage.add((repo, spec.branch))

    removed_repos = []
    for repo, spec in branch_specs.items():
        branch = spec.branch
        branch_dir = branch_to_dir(branch)
        worktree_path = _pkg.SRC_DIR / repo / branch_dir
        bare_path = _pkg.CACHE_DIR / f"{repo}.git"

        if not worktree_path.is_dir():
            continue

        dirty = git_wt(worktree_path, "status", "--porcelain", check=False, capture=True)
        if dirty.stdout.decode().strip() and not force:
            log_error(f"Worktree is dirty, skipping: {worktree_path}")
            log_info("Commit or stash your changes, or use --force to override.")
            continue

        log_info(f"Removing worktree: {worktree_path}")
        _git.git(bare_path, "worktree", "remove", str(worktree_path), check=False)
        removed_repos.append(repo)

        if stable_base(branch) is not None and (repo, branch) not in other_branch_usage:
            if local_branch_exists(bare_path, branch):
                log_info(f"Deleting local branch: {branch} in {repo}")
                _git.git(bare_path, "branch", "-D", branch, check=False)

    for repo in branch_specs:
        bare_path = _pkg.CACHE_DIR / f"{repo}.git"
        if bare_path.is_dir():
            _git.git(bare_path, "worktree", "prune", check=False)

    env_dir = _pkg.ROOT_DIR / ".cache" / "envs" / profile_name
    if env_dir.is_dir() and removed_repos:
        import shutil
        shutil.rmtree(env_dir)
        log_ok(f"Removed cache: {env_dir.relative_to(_pkg.ROOT_DIR)}")


def cmd_gen(profile_name: str, config: Config, ide: str) -> None:
    """Regenerate IDE workspace files for a profile without activating."""
    import oo as _pkg
    branch_specs = profile_branch_specs(config, profile_name)
    effective_odoorc = profile_odoorc(config, profile_name)
    port = int(effective_odoorc.get("port", 8069))

    worktree_paths = profile_worktree_paths(config, profile_name)
    if worktree_paths is None:
        log_error(f"No worktrees found for profile '{profile_name}'. Run 'oo {profile_name}' first.")
        sys.exit(1)

    community_path = worktree_paths.get("community")
    if not community_path:
        log_error("community worktree is required")
        sys.exit(1)

    extra_worktrees = {repo: path for repo, path in worktree_paths.items() if repo != "community"}
    python_path, addons_path = build_paths(community_path, extra_worktrees)
    odoo_conf = build_odoo_conf(_pkg.ROOT_DIR, addons_path, port, profile_name,
                                config.odoorc, profile_odoorc(config, profile_name))

    community_spec = branch_specs.get("community")
    community_branch = community_spec.branch if community_spec else "master"
    odoo_version = stable_base(community_branch) or community_branch

    enterprise_path = worktree_paths.get("enterprise")
    extra_paths = ":".join(
        str(p) for r, p in worktree_paths.items() if r not in ("community", "enterprise")
    )
    env = {
        "ODOO_ENV_NAME": profile_name,
        "ODOO_VERSION": odoo_version,
        "ODOO_RC": str(odoo_conf),
        "PYTHONPATH": python_path,
        "ODOO_ADDONS_PATH": addons_path,
        "ODOO_PORT": str(port),
        "ODOO_PATH": str(community_path),
        "ODOO_ENTERPRISE_PATH": str(enterprise_path) if enterprise_path else "",
        "ODOO_EXTRA_PATHS": extra_paths,
        "COMMUNITY": str(community_path),
        "ENTERPRISE": str(enterprise_path) if enterprise_path else "",
        "PATH": str(community_path) + ":" + os.environ.get("PATH", ""),
    }
    for repo, path in worktree_paths.items():
        if repo not in ("community", "enterprise"):
            env[repo.upper().replace("-", "_")] = str(path)

    if ide in ("vscode", "all"):
        generate_vscode_workspace(profile_name, worktree_paths, env, str(odoo_conf))
    if ide in ("zed", "all"):
        generate_zed_workspace(profile_name, worktree_paths, env)
    if ide in ("jetbrains", "all"):
        generate_idea_project(profile_name, worktree_paths, env)
    if ide == "all":
        generate_odools_config(profile_name, worktree_paths, python_path, config)


def cmd_activate(profile_name: str, config: Config) -> None:
    """Set up worktrees for a profile and launch an interactive shell."""
    import oo as _pkg
    current_env = os.environ.get("ODOO_ENV_NAME")
    if current_env:
        log_info(f"Switching from '{current_env}' to '{profile_name}'...")
        log_info("Tip: use `exec oo <profile>` to switch without nesting shells")

    profile = get_profile(config, profile_name)
    branch_specs = profile.branch_specs
    repo_urls = profile_remote_urls(config, profile_name)
    effective_odoorc = profile_odoorc(config, profile_name)
    opts = profile_options(config, profile_name)
    skip_js_tooling: set[str] = set(opts.get("skip_js_tooling", []))

    port = int(effective_odoorc.get("port", 8069))

    if "community" not in branch_specs:
        log_error("'community' branch is required in the profile.")
        sys.exit(1)

    community_branch = branch_specs["community"].branch
    odoo_version = stable_base(community_branch) or community_branch

    log_info(f"Profile: {profile_name}")
    for repo, spec in branch_specs.items():
        log_info(f"  {repo}: {spec}")

    _pkg.SRC_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch only repos whose worktree doesn't exist yet
    for repo, spec in branch_specs.items():
        branch_dir = branch_to_dir(spec.branch)
        if not (_pkg.SRC_DIR / repo / branch_dir).is_dir():
            fetch_repo(repo, url=repo_urls.get(repo))

    # Create worktrees (with stable-base fallback for non-community repos)
    worktree_paths: dict[str, Path] = {}
    for repo, spec in branch_specs.items():
        branch = spec.branch
        path = ensure_worktree(repo, branch)
        if path is None and repo != "community":
            fallback = stable_base(branch)
            if fallback:
                log_warn(f"Branch {branch!r} not found in {repo}, falling back to {fallback!r}...")
                fetch_repo(repo, url=repo_urls.get(repo))
                path = ensure_worktree(repo, fallback)
        if path is None:
            if repo == "community":
                log_error("community worktree is required")
                sys.exit(1)
            log_warn(f"Skipping {repo} (branch {branch!r} not found)")
            continue
        worktree_paths[repo] = path

    community_path = worktree_paths.get("community")
    if community_path is None:
        log_error("community worktree not available")
        sys.exit(1)

    setup_js_tooling(worktree_paths, skip_js_tooling)

    extra_worktrees = {repo: path for repo, path in worktree_paths.items() if repo != "community"}
    python_path, addons_path = build_paths(community_path, extra_worktrees)
    odoo_conf = build_odoo_conf(_pkg.ROOT_DIR, addons_path, port, profile_name,
                                config.odoorc, effective_odoorc)

    generate_odools_config(profile_name, worktree_paths, python_path, config)

    enterprise_path = worktree_paths.get("enterprise")
    extra_paths = ":".join(
        str(p) for r, p in worktree_paths.items()
        if r not in ("community", "enterprise")
    )
    env = {
        "ODOO_ENV_NAME": profile_name,
        "ODOO_VERSION": odoo_version,
        "ODOO_RC": str(odoo_conf),
        "PYTHONPATH": python_path,
        "ODOO_ADDONS_PATH": addons_path,
        "ODOO_PORT": str(port),
        "ODOO_PATH": str(community_path),
        "ODOO_ENTERPRISE_PATH": str(enterprise_path) if enterprise_path else "",
        "ODOO_EXTRA_PATHS": extra_paths,
        "COMMUNITY": str(community_path),
        "ENTERPRISE": str(enterprise_path) if enterprise_path else "",
        "PATH": str(community_path) + ":" + os.environ.get("PATH", ""),
    }
    for repo, path in worktree_paths.items():
        if repo not in ("community", "enterprise"):
            env[repo.upper().replace("-", "_")] = str(path)

    env_dir = _pkg.ROOT_DIR / ".cache" / "envs" / profile_name
    vscode_ws = generate_vscode_workspace(profile_name, worktree_paths, env, str(odoo_conf))
    generate_zed_workspace(profile_name, worktree_paths, env)
    generate_idea_project(profile_name, worktree_paths, env)

    print()
    log_ok("Environment ready!")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Profile: {profile_name}")
    print(f"  Port: {port}")
    print( "  Worktrees:")
    for repo, path in worktree_paths.items():
        print(f"    {path.relative_to(_pkg.ROOT_DIR)}")
    ws_rel = vscode_ws.relative_to(_pkg.ROOT_DIR)
    dir_rel = env_dir.relative_to(_pkg.ROOT_DIR)
    print("  IDE workspaces:")
    print(f"    VS Code:   code {hyperlink(str(ws_rel), 'file://' + str(vscode_ws))}")
    print(f"    Zed:       zed  {dir_rel}")
    print(f"    JetBrains: pycharm {dir_rel}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()
    print("Useful commands (inside the activated shell):")
    print("  odoo run         # Start Odoo server")
    print("  odoo test        # Run tests")
    print("  goto community   # cd to community worktree")
    print()

    launch_shell(env)


def profile_completer(prefix, **kwargs):
    """Return profile names from odoo-env.toml matching prefix (for argcomplete)."""
    import oo as _pkg
    import tomllib
    toml_path = _pkg.ROOT_DIR / "odoo-env.toml"
    if not toml_path.exists():
        return []
    try:
        with open(toml_path, "rb") as f:
            data = tomllib.load(f)
        return [
            p["name"] for p in data.get("profile", [])
            if p.get("name", "").startswith(prefix)
        ]
    except Exception:
        return []


def main() -> None:
    """Main entry point for the oo CLI."""
    SUBCOMMANDS = {"list", "ls", "activate", "status", "rebase", "remove", "rm", "gen"}

    # Shortcut: oo <profile> → oo activate <profile>
    # Also handles: oo community=master enterprise=master-fix (ad-hoc)
    if len(sys.argv) > 1 and sys.argv[1] not in SUBCOMMANDS and not sys.argv[1].startswith("-"):
        sys.argv.insert(1, "activate")

    parser = argparse.ArgumentParser(
        prog="oo",
        description="Manage Odoo development environments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  oo master                          # Activate 'master' profile
  oo community=master enterprise=master-fix  # Ad-hoc profile
  oo ls                              # List profiles
  oo status                          # Git status (current profile or all)
  oo rebase                          # Fetch + rebase
  oo gen vscode my-feature           # Regenerate VS Code workspace
  oo rm my-feature                   # Remove profile worktrees
        """,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    subparsers.add_parser("list", aliases=["ls"], help="List profiles from odoo-env.toml")

    sp_activate = subparsers.add_parser("activate", help="Set up worktrees and launch shell")
    sp_activate.add_argument(
        "profile_args", nargs="+",
        help="Profile name or key=value branch specs (e.g. community=master)",
    ).completer = profile_completer

    sp_status = subparsers.add_parser("status", help="Show git status (current profile, or all)")
    sp_status.add_argument("profile_name", nargs="?", help="Profile name (optional)")

    sp_rebase = subparsers.add_parser("rebase", help="Fetch and rebase (current profile, or all)")
    sp_rebase.add_argument("profile_name", nargs="?", help="Profile name (optional)")

    sp_remove = subparsers.add_parser("remove", aliases=["rm"], help="Remove worktrees for a profile")
    sp_remove.add_argument("profile_name", help="Profile name").completer = profile_completer
    sp_remove.add_argument("--force", action="store_true", help="Remove even if worktrees are dirty")

    sp_gen = subparsers.add_parser("gen", help="Regenerate IDE workspace files without activating")
    sp_gen.add_argument("ide", choices=["vscode", "zed", "jetbrains", "all"],
                        help="IDE target")
    sp_gen.add_argument("profile_name", nargs="?", help="Profile name (defaults to current)")

    if argcomplete:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    config = load_config()

    if args.command in ("list", "ls"):
        cmd_list(config)

    elif args.command == "activate":
        profile_args = args.profile_args
        if any("=" in arg for arg in profile_args):
            branch_specs: dict[str, str] = {}
            name_arg: str | None = None
            for arg in profile_args:
                if "=" in arg:
                    repo, branch = arg.split("=", 1)
                    branch_specs[repo.strip()] = branch.strip()
                else:
                    name_arg = arg
            if not branch_specs:
                log_error("No branch specs provided.")
                sys.exit(1)
            adhoc_cfg, adhoc_name = adhoc_profile(branch_specs)
            if name_arg:
                adhoc_cfg.profiles[0].name = name_arg
                adhoc_name = name_arg
            adhoc_cfg.odoorc = config.odoorc
            adhoc_cfg.remotes = config.remotes
            adhoc_cfg.options = config.options
            cmd_activate(adhoc_name, adhoc_cfg)
        else:
            cmd_activate(profile_args[0], config)

    elif args.command == "status":
        profile_name = getattr(args, "profile_name", None) or os.environ.get("ODOO_ENV_NAME")
        profile_names = [profile_name] if profile_name else list_profiles(config)
        cmd_status(profile_names, config)

    elif args.command == "rebase":
        profile_name = getattr(args, "profile_name", None) or os.environ.get("ODOO_ENV_NAME")
        profile_names = [profile_name] if profile_name else list_profiles(config)
        cmd_rebase(profile_names, config)

    elif args.command in ("remove", "rm"):
        cmd_remove(args.profile_name, config, force=args.force)

    elif args.command == "gen":
        profile_name = args.profile_name or os.environ.get("ODOO_ENV_NAME")
        if not profile_name:
            log_error("No profile name specified and not in an active profile shell.")
            sys.exit(1)
        cmd_gen(profile_name, config, args.ide)
