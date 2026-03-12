"""Tests for workflow subcommands: status, sync, cleanup."""
from pathlib import Path
import subprocess
import os

from oo.config import Config, Profile, BranchSpec


def _make_config(profiles_spec: dict[str, dict[str, str]],
                 remotes: dict | None = None) -> Config:
    """Helper: {env_name: {repo: branch_spec_str}} → Config."""
    profiles = [
        Profile(
            name=name,
            branch_specs={repo: BranchSpec.parse(b) for repo, b in branches.items()},
            odoorc={},
            options={},
        )
        for name, branches in profiles_spec.items()
    ]
    return Config(profiles=profiles, odoorc={}, remotes=remotes or {}, options={})


def _make_bare(tmp_path: Path, repo: str) -> Path:
    """Create a minimal bare repo with an initial commit."""
    bare = tmp_path / f"{repo}.git"
    bare.mkdir(parents=True)
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)

    empty_tree = subprocess.run(
        ["git", "--git-dir", str(bare), "hash-object", "-t", "tree", "-w", "--stdin"],
        input=b"", check=True, capture_output=True,
    ).stdout.decode().strip()

    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t.com",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t.com",
    }
    commit = subprocess.run(
        ["git", "--git-dir", str(bare), "commit-tree", empty_tree, "-m", "init"],
        input=b"", check=True, capture_output=True, env=git_env,
    ).stdout.decode().strip()

    subprocess.run(
        ["git", "--git-dir", str(bare), "update-ref", "refs/heads/main", commit],
        check=True, capture_output=True,
    )
    return bare


class TestGithubPrUrl:
    def test_fork_pr_url_from_spec(self, mod, tmp_path):
        """Fork PR URL is built directly from github_org_repo, no git call needed."""
        bare = _make_bare(tmp_path, "enterprise")
        spec = {
            "number": "1261",
            "remote_url": "git@github.com:odoo-dev/enterprise.git",
            "github_org_repo": "odoo-dev/enterprise",
            "dir_slug": "odoo-dev-pr-1261",
        }
        url = mod.github_pr_url(bare, spec)
        assert url == "https://github.com/odoo-dev/enterprise/pull/1261"

    def test_origin_pr_url_from_remote(self, mod, tmp_path):
        """Origin PR URL is derived from the origin remote URL."""
        bare = _make_bare(tmp_path, "enterprise")
        subprocess.run(
            ["git", "--git-dir", str(bare), "remote", "add", "origin",
             "git@github.com:odoo/enterprise.git"],
            check=True, capture_output=True,
        )
        spec = {
            "number": "1370",
            "remote_url": None,
            "github_org_repo": None,
            "dir_slug": "pr-1370",
        }
        url = mod.github_pr_url(bare, spec)
        assert url == "https://github.com/odoo/enterprise/pull/1370"

    def test_origin_pr_url_https_remote(self, mod, tmp_path):
        """Works with https:// origin URLs too."""
        bare = _make_bare(tmp_path, "enterprise")
        subprocess.run(
            ["git", "--git-dir", str(bare), "remote", "add", "origin",
             "https://github.com/odoo/enterprise.git"],
            check=True, capture_output=True,
        )
        spec = {"number": "42", "remote_url": None, "github_org_repo": None, "dir_slug": "pr-42"}
        url = mod.github_pr_url(bare, spec)
        assert url == "https://github.com/odoo/enterprise/pull/42"

    def test_returns_none_when_no_origin(self, mod, tmp_path):
        """Returns None when origin remote is missing and no org_repo in spec."""
        bare = _make_bare(tmp_path, "enterprise")
        spec = {"number": "1", "remote_url": None, "github_org_repo": None, "dir_slug": "pr-1"}
        url = mod.github_pr_url(bare, spec)
        assert url is None


class TestResolvePrBranch:
    def _make_bare_with_pr_refs(self, tmp_path: Path) -> tuple[Path, str]:
        """Bare repo with refs/remotes/origin/pr/1 pointing to same SHA as origin/18.0-feature."""
        bare = _make_bare(tmp_path, "repo")

        empty_tree = subprocess.run(
            ["git", "--git-dir", str(bare), "hash-object", "-t", "tree", "-w", "--stdin"],
            input=b"", check=True, capture_output=True,
        ).stdout.decode().strip()

        git_env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t.com",
            "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t.com",
        }
        commit = subprocess.run(
            ["git", "--git-dir", str(bare), "commit-tree", empty_tree, "-m", "feature"],
            input=b"", check=True, capture_output=True, env=git_env,
        ).stdout.decode().strip()

        # Create the PR ref and the named branch ref pointing to same SHA
        subprocess.run(
            ["git", "--git-dir", str(bare), "update-ref",
             "refs/remotes/origin/pr/1", commit],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "--git-dir", str(bare), "update-ref",
             "refs/remotes/origin/18.0-feature", commit],
            check=True, capture_output=True,
        )
        return bare, commit

    def test_resolves_branch_from_sha(self, mod, tmp_path):
        bare, _ = self._make_bare_with_pr_refs(tmp_path)
        branch = mod.resolve_pr_branch(bare, "origin", "1")
        assert branch == "18.0-feature"

    def test_fallback_when_pr_ref_missing(self, mod, tmp_path):
        bare = _make_bare(tmp_path, "repo")
        branch = mod.resolve_pr_branch(bare, "origin", "999")
        assert branch == "pr-999"


class TestCmdStatusPrBranch:
    def test_origin_pr_shows_not_created_with_url(self, mod, tmp_path, monkeypatch, capsys):
        """cmd_status for a pr/NNNN branch shows the GitHub URL when worktree missing."""
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path / "src")
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")

        bare = _make_bare(tmp_path / "cache", "enterprise")
        subprocess.run(
            ["git", "--git-dir", str(bare), "remote", "add", "origin",
             "git@github.com:odoo/enterprise.git"],
            check=True, capture_output=True,
        )

        config = _make_config({"my-env": {"enterprise": "pr/1261"}})
        mod.cmd_status(["my-env"], config)
        out = capsys.readouterr().out
        assert "not created" in out
        assert "https://github.com/odoo/enterprise/pull/1261" in out

    def test_fork_pr_shows_not_created_with_url(self, mod, tmp_path, monkeypatch, capsys):
        """cmd_status for a fork PR spec shows the fork GitHub URL."""
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path / "src")
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")

        _make_bare(tmp_path / "cache", "enterprise")

        config = _make_config({"my-env": {"enterprise": "odoo-dev/enterprise#1261"}})
        mod.cmd_status(["my-env"], config)
        out = capsys.readouterr().out
        assert "not created" in out
        assert "https://github.com/odoo-dev/enterprise/pull/1261" in out

    def test_non_pr_branch_shows_no_url(self, mod, tmp_path, monkeypatch, capsys):
        """cmd_status for a normal branch shows no PR URL."""
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path / "src")
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")

        config = _make_config({"my-env": {"community": "18.0"}})
        mod.cmd_status(["my-env"], config)
        out = capsys.readouterr().out
        assert "github.com" not in out
        assert "not created" in out


class TestRepoUrls:
    def test_remote_url_returned_for_repo_in_profile(self, mod):
        config = _make_config(
            {"my-env": {"community": "18.0", "utils": "main"}},
            remotes={"utils": {"origin": "git@github.com:myco/utils.git"}},
        )
        urls = mod.profile_remote_urls(config, "my-env")
        assert urls["utils"] == "git@github.com:myco/utils.git"

    def test_remote_url_from_config_remotes(self, mod):
        config = _make_config(
            {"my-env": {"community": "18.0", "addons": "main"}},
            remotes={"addons": {"origin": "git@github.com:override/addons.git"}},
        )
        urls = mod.profile_remote_urls(config, "my-env")
        assert urls["addons"] == "git@github.com:override/addons.git"

    def test_no_remotes_returns_empty(self, mod):
        config = _make_config({"my-env": {"community": "18.0"}})
        urls = mod.profile_remote_urls(config, "my-env")
        assert urls == {}


class TestRepoBranches:
    def test_profile_returns_its_own_branches(self, mod):
        config = _make_config({"my-env": {"community": "18.0", "enterprise": "18.0"}})
        specs = mod.profile_branch_specs(config, "my-env")
        assert specs["community"].branch == "18.0"
        assert specs["enterprise"].branch == "18.0"

    def test_profiles_branches_are_independent(self, mod):
        config = _make_config({
            "profile-a": {"community": "18.0"},
            "profile-b": {"community": "17.0"},
        })
        assert mod.profile_branch_specs(config, "profile-a")["community"].branch == "18.0"
        assert mod.profile_branch_specs(config, "profile-b")["community"].branch == "17.0"


class TestLocalBranchExists:
    def test_false_for_fresh_bare_repo(self, mod, tmp_path):
        """A fresh bare repo has no local branches."""
        bare = tmp_path / "repo.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        assert mod.local_branch_exists(bare, "main") is False

    def test_false_for_nonexistent_branch(self, mod, tmp_path):
        """A named branch that was never created returns False."""
        bare = tmp_path / "repo.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        assert mod.local_branch_exists(bare, "18.0-fix") is False

    def test_true_when_branch_exists(self, mod, tmp_path):
        """Returns True for a branch that exists in the bare repo."""
        bare = tmp_path / "bare.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)

        # Create a branch ref directly via low-level git plumbing (no commits, no hooks)
        empty_tree = subprocess.run(
            ["git", "--git-dir", str(bare), "hash-object", "-t", "tree", "-w", "--stdin"],
            input=b"", check=True, capture_output=True,
        ).stdout.decode().strip()

        commit = subprocess.run(
            ["git", "--git-dir", str(bare), "commit-tree", empty_tree, "-m", "init"],
            input=b"", check=True, capture_output=True,
            env={
                **{k: v for k, v in __import__("os").environ.items()},
                "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t.com",
                "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t.com",
            },
        ).stdout.decode().strip()

        subprocess.run(
            ["git", "--git-dir", str(bare), "update-ref", "refs/heads/18.0", commit],
            check=True, capture_output=True,
        )

        assert mod.local_branch_exists(bare, "18.0") is True
        assert mod.local_branch_exists(bare, "no-such-branch") is False


class TestCmdStatusMissingWorktree:
    def test_missing_worktree_shows_not_created(self, mod, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path)
        config = _make_config({"my-env": {"community": "18.0"}})
        mod.cmd_status(["my-env"], config)
        out = capsys.readouterr().out
        assert "not created" in out
        assert "community" in out


class TestCmdRemoveDirtyCheck:
    def _make_bare(self, tmp_path: "Path", repo: str) -> "Path":
        """Create a minimal bare repo in CACHE_DIR."""
        bare = tmp_path / "cache" / f"{repo}.git"
        bare.mkdir(parents=True)
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        return bare

    def test_dirty_worktree_is_skipped(self, mod, tmp_path, monkeypatch):
        """remove skips a worktree that has staged (dirty) changes."""
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path)
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")
        self._make_bare(tmp_path, "community")

        worktree = tmp_path / "community" / "18.0"
        worktree.mkdir(parents=True)
        subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True)
        (worktree / "dirty.txt").write_text("staged but uncommitted")
        subprocess.run(["git", "-C", str(worktree), "add", "dirty.txt"],
                       check=True, capture_output=True)

        config = _make_config({"my-env": {"community": "18.0"}})

        mod.cmd_remove("my-env", config)
        # Dirty worktree must survive — remove refused to delete it
        assert worktree.is_dir()

    def test_clean_worktree_removal_is_attempted(self, mod, tmp_path, monkeypatch):
        """For a clean worktree, git worktree remove is called (not skipped)."""
        import oo.git as git_mod

        monkeypatch.setattr(mod, "SRC_DIR", tmp_path)
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")
        self._make_bare(tmp_path, "community")

        worktree = tmp_path / "community" / "18.0"
        worktree.mkdir(parents=True)
        subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True)

        git_calls: list[tuple] = []
        original_git = git_mod.git

        def tracking_git(bare_path, *args, check=True, capture=False):
            git_calls.append(args)
            return original_git(bare_path, *args, check=False, capture=capture)

        monkeypatch.setattr(git_mod, "git", tracking_git)
        config = _make_config({"my-env": {"community": "18.0"}})
        mod.cmd_remove("my-env", config)

        # Assert that git worktree remove was called (not skipped due to dirty check)
        remove_calls = [c for c in git_calls if c[:2] == ("worktree", "remove")]
        assert len(remove_calls) == 1
        assert str(worktree) in remove_calls[0]
