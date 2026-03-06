"""Tests for settings persistence: TOML I/O, list_envs, detect_available_repos."""
import pytest


class TestSaveLoadRoundtrip:
    def test_roundtrip(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ENVS_DIR", tmp_path)

        settings = {"community": "18.0", "enterprise": "18.0-fix", "port": 8069}
        mod.save_env_settings("my-project", settings)
        loaded = mod.load_env_settings("my-project")

        assert loaded == settings

    def test_load_missing_returns_none(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ENVS_DIR", tmp_path)

        assert mod.load_env_settings("nonexistent") is None

    def test_toml_file_is_human_readable(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ENVS_DIR", tmp_path)

        mod.save_env_settings("dev", {"community": "master", "port": 8069})
        content = (tmp_path / "dev.toml").read_text()

        assert 'community = "master"' in content
        assert "port = 8069" in content


class TestListEnvs:
    def test_empty_when_dir_missing(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ENVS_DIR", tmp_path / "nonexistent")

        assert mod.list_envs() == []

    def test_returns_sorted_names(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ENVS_DIR", tmp_path)
        for name in ("zebra", "alpha", "my-project"):
            (tmp_path / f"{name}.toml").write_text('community = "master"\nport = 8069\n')

        assert mod.list_envs() == ["alpha", "my-project", "zebra"]

    def test_ignores_non_toml_files(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ENVS_DIR", tmp_path)
        (tmp_path / "env.toml").write_text('community = "master"\nport = 8069\n')
        (tmp_path / "README.md").write_text("ignored")
        (tmp_path / "env.json").write_text("{}")

        assert mod.list_envs() == ["env"]


class TestDetectAvailableRepos:
    def test_no_cache_dir_returns_community(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "nonexistent")

        assert mod.detect_available_repos() == ["community"]

    def test_community_comes_first(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
        for repo in ("enterprise", "community", "design-themes"):
            (tmp_path / f"{repo}.git").mkdir()

        repos = mod.detect_available_repos()
        assert repos[0] == "community"
        assert set(repos) == {"community", "enterprise", "design-themes"}

    def test_empty_cache_returns_community(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)

        assert mod.detect_available_repos() == ["community"]

    def test_only_directories_counted(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "CACHE_DIR", tmp_path)
        (tmp_path / "community.git").mkdir()
        (tmp_path / "stale.git").write_text("not a dir")  # file, should be ignored

        repos = mod.detect_available_repos()
        assert "stale" not in repos
