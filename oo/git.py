"""Git operations: bare repos, worktrees, PR resolution."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import oo as _pkg

# Maps local alias → GitHub repo name (only non-identity mappings)
REVERSE_ALIAS = {"community": "odoo"}

RUNBOT_BASE_URL = "https://runbot.odoo.com"


def git(bare_path: Path, *args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", f"--git-dir={bare_path}", *args],
        check=check,
        capture_output=capture,
    )


def git_wt(worktree_path: Path, *args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a git command inside a (non-bare) worktree directory."""
    return subprocess.run(
        ["git", "-C", str(worktree_path), *args],
        check=check,
        capture_output=capture,
    )


def stable_base(branch: str) -> str | None:
    """Return the stable base of a feature branch, or None if already stable.

    'master-parrot' -> 'master'
    '17.0-fix'      -> '17.0'
    'master'        -> None
    '18.0'          -> None
    """
    if re.match(r'^\d+\.\d+$', branch) or branch == "master":
        return None
    if branch.startswith("master-"):
        return "master"
    m = re.match(r'^(\d+\.\d+)-', branch)
    if m:
        return m.group(1)
    return None


def parse_pr(branch: str) -> dict | None:
    """Parse a PR branch spec into a dict, or None if not a PR spec.

    Supported formats:
      pr/1261                                    → origin PR
      odoo-dev/enterprise#1261                   → fork PR shorthand
      https://github.com/odoo-dev/enterprise/pull/1261  → fork PR full URL
    """
    m = re.match(r'^pr/(\d+)$', branch)
    if m:
        number = m.group(1)
        return {"number": number, "remote_url": None, "github_org_repo": None, "dir_slug": f"pr-{number}"}

    m = re.match(r'^([\w.-]+/[\w.-]+)#(\d+)$', branch)
    if m:
        org_repo = m.group(1)
        number = m.group(2)
        org = org_repo.split("/")[0]
        return {
            "number": number,
            "remote_url": f"git@github.com:{org_repo}.git",
            "github_org_repo": org_repo,
            "dir_slug": f"{org}-pr-{number}",
        }

    m = re.match(r'^https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)$', branch)
    if m:
        org_repo = m.group(1)
        number = m.group(2)
        org = org_repo.split("/")[0]
        return {
            "number": number,
            "remote_url": f"git@github.com:{org_repo}.git",
            "github_org_repo": org_repo,
            "dir_slug": f"{org}-pr-{number}",
        }

    return None


def branch_to_dir(branch: str) -> str:
    """Convert a branch name to a filesystem-safe directory name.

    For PR specs, returns the canonical dir_slug (e.g. 'pr-1261', 'odoo-dev-pr-1261').
    For regular branches, replaces '/' with '-'.
    """
    spec = parse_pr(branch)
    if spec:
        return spec["dir_slug"]
    return branch.replace("/", "-")


def remotes(bare_path: Path) -> list[str]:
    """Return remotes ordered: origin first, then others alphabetically."""
    result = git(bare_path, "remote", check=False, capture=True)
    if result.returncode != 0:
        return []
    all_remotes = result.stdout.decode().split()
    return sorted(all_remotes, key=lambda r: (0 if r == "origin" else 1, r))


def dev_remote_exists(repo: str) -> bool:
    result = subprocess.run(
        ["git", "ls-remote", f"git@github.com:odoo-dev/{repo}.git"],
        capture_output=True, check=False,
    )
    return result.returncode == 0


def setup_bare_repo(alias: str, url: str | None = None) -> None:
    from oo.ui import log_info, log_ok
    if url is None:
        github_repo = REVERSE_ALIAS.get(alias, alias)
        url = f"git@github.com:odoo/{github_repo}.git"
        check_dev_remote = True
    else:
        github_repo = alias
        check_dev_remote = False

    bare_path = _pkg.CACHE_DIR / f"{alias}.git"
    _pkg.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    log_info(f"Cloning bare repository: {url} -> {bare_path}")
    subprocess.run(["git", "clone", "--bare", url, str(bare_path)], check=True)

    git(bare_path, "config", "--replace-all", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    git(bare_path, "config", "--add", "remote.origin.fetch", "+refs/pull/*/head:refs/remotes/origin/pr/*")

    if check_dev_remote:
        log_info(f"Checking for dev remote (github.com/odoo-dev/{github_repo})...")
        if dev_remote_exists(github_repo):
            dev_url = f"git@github.com:odoo-dev/{github_repo}.git"
            git(bare_path, "remote", "add", "dev", dev_url)
            git(bare_path, "config", "--replace-all", "remote.dev.fetch", "+refs/heads/*:refs/remotes/dev/*")
            log_ok(f"Dev remote added: {dev_url}")

    log_ok(f"Repository ready: {bare_path.relative_to(_pkg.ROOT_DIR)}")


def fetch_repo(repo: str, url: str | None = None) -> None:
    from oo.ui import log_info, log_warn
    bare_path = _pkg.CACHE_DIR / f"{repo}.git"
    if not bare_path.is_dir():
        log_info(f"Bare repo not found for '{repo}', setting it up automatically...")
        setup_bare_repo(repo, url=url)
    git(bare_path, "pack-refs", "--all", check=False)
    for remote in remotes(bare_path):
        log_info(f"Fetching {repo} ({remote})...")
        result = git(bare_path, "fetch", remote, "--prune", check=False)
        if result.returncode != 0:
            log_warn(f"Could not fetch {repo} from {remote}")


def find_ref(bare_path: Path, branch: str) -> str | None:
    """Return the full remote ref (e.g. 'origin/branch') if it exists, else None."""
    for remote in remotes(bare_path):
        result = git(bare_path, "rev-parse", "--verify", f"{remote}/{branch}", check=False, capture=True)
        if result.returncode == 0:
            return f"{remote}/{branch}"
    return None


def local_branch_exists(bare_path: Path, branch: str) -> bool:
    """Return True if a local branch exists in the bare repo."""
    result = git(bare_path, "branch", "--list", branch, check=False, capture=True)
    return result.returncode == 0 and result.stdout.decode().strip() != ""


def resolve_pr_branch(bare_path: Path, remote_name: str, pr_number: str) -> str:
    """Find the actual head branch name for a PR by SHA lookup.

    Returns the real branch name or falls back to 'pr-{number}'.
    """
    result = git(bare_path, "rev-parse", f"{remote_name}/pr/{pr_number}", check=False, capture=True)
    if result.returncode != 0:
        return f"pr-{pr_number}"
    sha = result.stdout.decode().strip()

    result = git(bare_path, "for-each-ref",
                 "--format=%(objectname) %(refname:short)",
                 "refs/remotes/", check=False, capture=True)
    if result.returncode != 0:
        return f"pr-{pr_number}"

    prefix = f"{remote_name}/"
    for line in result.stdout.decode().splitlines():
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        ref_sha, refname = parts
        if ref_sha == sha and "/pr/" not in refname and refname.startswith(prefix):
            return refname[len(prefix):]

    return f"pr-{pr_number}"


def find_or_add_remote(bare_path: Path, url: str, preferred_name: str) -> str:
    """Return the name of an existing remote with the given URL, or add one."""
    for remote_name in remotes(bare_path):
        result = git(bare_path, "remote", "get-url", remote_name, check=False, capture=True)
        if result.returncode == 0 and result.stdout.decode().strip() == url:
            return remote_name

    git(bare_path, "remote", "add", preferred_name, url)
    git(bare_path, "config", "--add", f"remote.{preferred_name}.fetch",
        f"+refs/pull/*/head:refs/remotes/{preferred_name}/pr/*")
    return preferred_name


def ensure_worktree(repo: str, branch: str) -> Path | None:
    from oo.ui import log_info, log_ok, log_error
    bare_path = _pkg.CACHE_DIR / f"{repo}.git"

    if not bare_path.is_dir():
        log_error(f"Bare repo not found: {bare_path}")
        return None

    branch_dir = branch_to_dir(branch)
    worktree_path = _pkg.SRC_DIR / repo / branch_dir

    if worktree_path.is_dir():
        log_ok(f"Worktree exists: {worktree_path}")
        return worktree_path

    pr_spec = parse_pr(branch)
    if pr_spec:
        number = pr_spec["number"]
        if pr_spec["remote_url"]:
            org = pr_spec["github_org_repo"].split("/")[0]
            remote_name = find_or_add_remote(bare_path, pr_spec["remote_url"], org)
            log_info(f"Fetching PR #{number} from {remote_name}...")
            result = git(bare_path, "fetch", remote_name,
                         f"refs/pull/{number}/head:refs/remotes/{remote_name}/pr/{number}",
                         check=False)
            if result.returncode != 0:
                log_error(f"Failed to fetch PR #{number} from {remote_name}")
                return None
        else:
            remote_name = "origin"

        local_branch = resolve_pr_branch(bare_path, remote_name, number)
        pr_ref = f"{remote_name}/pr/{number}"

        if not local_branch_exists(bare_path, local_branch):
            git(bare_path, "branch", "--track", local_branch, pr_ref)

        worktree_path.parent.mkdir(parents=True, exist_ok=True)
        log_info(f"Creating PR worktree: {repo} PR#{number} -> {worktree_path} (branch: {local_branch})")
        result = git(bare_path, "worktree", "add", str(worktree_path), local_branch, check=False)
        if result.returncode != 0:
            log_error(f"Failed to create worktree for {repo} PR #{number}")
            return None
        log_ok(f"Created worktree: {worktree_path}")
        return worktree_path

    ref = find_ref(bare_path, branch)
    if ref is None:
        log_error(f"Branch/ref not found: {branch} in {repo}")
        log_info("Available branches:")
        git(bare_path, "branch", "-r", check=False)
        return None

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    log_info(f"Creating worktree: {repo}@{branch} -> {worktree_path} (from {ref})")

    if not local_branch_exists(bare_path, branch):
        git(bare_path, "branch", "--track", branch, ref)

    result = git(bare_path, "worktree", "add", str(worktree_path), branch, check=False)
    if result.returncode != 0:
        log_error(f"Failed to create worktree for {repo}@{branch}")
        return None

    log_ok(f"Created worktree: {worktree_path}")
    return worktree_path


def setup_js_tooling(worktree_paths: dict[str, Path], skip_repos: set[str] | None = None) -> None:
    import os
    from oo.ui import log_info, log_ok
    community_path = worktree_paths.get("community")
    if community_path is None:
        return
    tooling_dir = community_path / "addons" / "web" / "tooling"
    if not tooling_dir.is_dir():
        return

    src_names = ["_eslintignore", "_eslintrc.json", "_jsconfig.json", "_package.json"]
    dst_names = [".eslintignore",  ".eslintrc.json",  "jsconfig.json",  "package.json"]

    for repo, repo_path in worktree_paths.items():
        if skip_repos and repo in skip_repos:
            continue
        if (repo_path / "jsconfig.json").exists():
            log_ok(f"JS tooling already present: {repo}")
        else:
            log_info(f"Setting up JS tooling for {repo}...")
            for src, dst in zip(src_names, dst_names):
                shutil.copy2(tooling_dir / src, repo_path / dst)
            if repo != "community":
                jsconfig = repo_path / "jsconfig.json"
                rel = os.path.relpath(community_path / "addons", repo_path)
                jsconfig.write_text(jsconfig.read_text().replace('"addons/', f'"{rel}/'))
            log_ok(f"JS tooling config installed: {repo_path.relative_to(_pkg.ROOT_DIR)}")

        if repo == "community":
            if not (repo_path / "node_modules").exists():
                log_info("Running npm install in community (first time)...")
                subprocess.run(["npm", "install"], cwd=repo_path, check=False)
        else:
            nm = repo_path / "node_modules"
            if not nm.exists() and not nm.is_symlink():
                nm.symlink_to(community_path / "node_modules")
                log_ok(f"node_modules symlinked: {repo}")


def deduce_runbot_bundles(
    repo_branches: dict[str, str],
    resolved_pr_branches: dict[str, str] | None = None,
) -> list[str]:
    """Deduce runbot bundle name(s) from a repo→branch mapping."""
    candidates: list[str] = []
    stable_version: str | None = None

    for repo, branch in repo_branches.items():
        pr_spec = parse_pr(branch)
        if pr_spec:
            resolved = (resolved_pr_branches or {}).get(branch)
            if resolved and stable_base(resolved) is not None:
                if resolved not in candidates:
                    candidates.append(resolved)
            continue

        base = stable_base(branch)
        if base is None:
            if stable_version is None:
                stable_version = branch
        else:
            if branch not in candidates:
                candidates.append(branch)

    if not candidates and stable_version:
        return [stable_version]
    return candidates


def runbot_bundle_urls(bundles: list[str]) -> list[str]:
    """Return runbot URLs for a list of bundle names."""
    return [f"{RUNBOT_BASE_URL}/runbot/bundle/{b}" for b in bundles]


def github_pr_url(bare_path: Path, pr_spec: dict) -> str | None:
    """Return the GitHub PR URL for a given PR spec dict."""
    number = pr_spec["number"]
    if pr_spec.get("github_org_repo"):
        return f"https://github.com/{pr_spec['github_org_repo']}/pull/{number}"

    result = git(bare_path, "remote", "get-url", "origin", check=False, capture=True)
    if result.returncode != 0:
        return None
    url = result.stdout.decode().strip()
    m = re.match(r'git@github\.com:(.+?)(?:\.git)?$', url)
    if not m:
        m = re.match(r'https://github\.com/(.+?)(?:\.git)?$', url)
    if m:
        return f"https://github.com/{m.group(1)}/pull/{number}"
    return None


def fetch_pr_title(org_repo: str, pr_number: str) -> str | None:
    """Fetch PR title using the gh CLI. Returns None if unavailable or on error."""
    if not shutil.which("gh"):
        return None
    result = subprocess.run(
        ["gh", "pr", "view", pr_number, "--repo", org_repo, "--json", "title", "-q", ".title"],
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.decode().strip() or None
    return None


def _pr_annotation(bare_path: Path, pr_spec: dict) -> str:
    """Return a string with PR title (if fetchable) and URL for display in status."""
    from oo.ui import BLUE, NC, hyperlink
    url = github_pr_url(bare_path, pr_spec)
    if not url:
        return ""
    org_repo = pr_spec.get("github_org_repo")
    if not org_repo:
        result = git(bare_path, "remote", "get-url", "origin", check=False, capture=True)
        if result.returncode == 0:
            m = re.match(r'git@github\.com:(.+?)(?:\.git)?$', result.stdout.decode().strip())
            if m:
                org_repo = m.group(1)
    title = fetch_pr_title(org_repo, pr_spec["number"]) if org_repo else None
    if title:
        return f"  {BLUE}{hyperlink(title, url)}{NC}"
    return f"  {BLUE}{hyperlink(url, url)}{NC}"
