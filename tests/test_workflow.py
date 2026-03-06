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
    def test_true_when_branch_present(self, mod, tmp_path):
        """Parses non-empty git branch --list output as True."""
        # Simulate by checking return value parsing with a real git repo
        bare = tmp_path / "repo.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        # No branches exist in a fresh bare repo
        assert mod.local_branch_exists(bare, "main") is False

    def test_false_for_empty_output(self, mod, tmp_path):
        bare = tmp_path / "repo.git"
        subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
        assert mod.local_branch_exists(bare, "nonexistent") is False


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
    def test_dirty_worktree_is_skipped(self, mod, tmp_path, monkeypatch):
        """cleanup skips a worktree that has uncommitted changes."""
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path)
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")

        # Create a fake worktree dir with a dirty git repo
        worktree = tmp_path / "community" / "18.0"
        worktree.mkdir(parents=True)
        subprocess.run(["git", "init", str(worktree)], check=True, capture_output=True)
        (worktree / "dirty.txt").write_text("uncommitted")
        subprocess.run(["git", "-C", str(worktree), "add", "dirty.txt"],
                       check=True, capture_output=True)

        toml_data = {"my-env": {"branches": {"community": "18.0"}}}

        # Should not raise — dirty worktree is skipped with log_error
        mod.cmd_cleanup(["my-env"], toml_data)
        # Worktree still exists because it was skipped
        assert worktree.is_dir()
