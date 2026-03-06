"""Tests for workflow subcommands: status, sync, cleanup."""
from pathlib import Path
import subprocess


class TestRepoUrls:
    def test_default_repos_merged(self, mod):
        toml_data = {
            "_": {"repos": {"utils": "git@github.com:myco/utils.git"}},
            "my-env": {"branches": {"community": "18.0"}},
        }
        urls = mod._repo_urls_for_env(toml_data, "my-env")
        assert urls["utils"] == "git@github.com:myco/utils.git"

    def test_env_repos_override_default(self, mod):
        toml_data = {
            "_": {"repos": {"addons": "git@github.com:default/addons.git"}},
            "my-env": {
                "branches": {"community": "18.0"},
                "repos": {"addons": "git@github.com:override/addons.git"},
            },
        }
        urls = mod._repo_urls_for_env(toml_data, "my-env")
        assert urls["addons"] == "git@github.com:override/addons.git"

    def test_no_repos_section_returns_empty(self, mod):
        toml_data = {"my-env": {"branches": {"community": "18.0"}}}
        urls = mod._repo_urls_for_env(toml_data, "my-env")
        assert urls == {}


class TestRepoBranches:
    def test_default_branches_merged(self, mod):
        toml_data = {
            "_": {"branches": {"community": "18.0", "enterprise": "18.0"}},
            "my-env": {},
        }
        branches = mod._repo_branches_for_env(toml_data, "my-env")
        assert branches["community"] == "18.0"
        assert branches["enterprise"] == "18.0"

    def test_env_branches_override_default(self, mod):
        toml_data = {
            "_": {"branches": {"community": "18.0"}},
            "my-env": {"branches": {"community": "17.0"}},
        }
        branches = mod._repo_branches_for_env(toml_data, "my-env")
        assert branches["community"] == "17.0"


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
        toml_data = {
            "my-env": {"branches": {"community": "18.0"}},
        }
        mod.cmd_status(["my-env"], toml_data)
        out = capsys.readouterr().out
        assert "not created" in out
        assert "community" in out


class TestCmdCleanupDirtyCheck:
    def _make_bare(self, tmp_path: "Path", repo: str) -> "Path":
        """Create a minimal bare repo in CACHE_DIR."""
        bare = tmp_path / "cache" / f"{repo}.git"
        bare.mkdir(parents=True)
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        return bare

    def test_dirty_worktree_is_skipped(self, mod, tmp_path, monkeypatch):
        """cleanup skips a worktree that has staged (dirty) changes."""
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path)
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")
        self._make_bare(tmp_path, "community")

        worktree = tmp_path / "community" / "18.0"
        worktree.mkdir(parents=True)
        subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True)
        (worktree / "dirty.txt").write_text("staged but uncommitted")
        subprocess.run(["git", "-C", str(worktree), "add", "dirty.txt"],
                       check=True, capture_output=True)

        toml_data = {"my-env": {"branches": {"community": "18.0"}}}

        mod.cmd_cleanup(["my-env"], toml_data)
        # Dirty worktree must survive — cleanup refused to remove it
        assert worktree.is_dir()

    def test_clean_worktree_removal_is_attempted(self, mod, tmp_path, monkeypatch):
        """For a clean worktree, git worktree remove is called (not skipped)."""
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path)
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")
        self._make_bare(tmp_path, "community")

        worktree = tmp_path / "community" / "18.0"
        worktree.mkdir(parents=True)
        subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True)

        git_calls: list[tuple] = []
        original_git = mod.git

        def tracking_git(bare_path, *args, check=True, capture=False):
            git_calls.append(args)
            return original_git(bare_path, *args, check=False, capture=capture)

        monkeypatch.setattr(mod, "git", tracking_git)
        toml_data = {"my-env": {"branches": {"community": "18.0"}}}
        mod.cmd_cleanup(["my-env"], toml_data)

        # Assert that git worktree remove was called (not skipped due to dirty check)
        remove_calls = [c for c in git_calls if c[:2] == ("worktree", "remove")]
        assert len(remove_calls) == 1
        assert str(worktree) in remove_calls[0]
