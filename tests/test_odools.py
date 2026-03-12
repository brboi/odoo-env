"""Tests for generate_odools_config."""
from pathlib import Path
from oo.config import Config, Profile, BranchSpec


def _make_config(*profile_specs: tuple[str, dict[str, str]]) -> Config:
    """Helper: build a Config from (name, {repo: branch}) tuples."""
    profiles = [
        Profile(
            name=name,
            branch_specs={repo: BranchSpec.parse(b) for repo, b in branches.items()},
            odoorc={},
            options={},
        )
        for name, branches in profile_specs
    ]
    return Config(profiles=profiles, odoorc={}, remotes={}, options={})


class TestGenerateOdoolsConfig:
    def test_generates_file(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "18.0"
        community.mkdir(parents=True)

        out = mod.generate_odools_config(
            "my-env",
            {"community": community},
            str(tmp_path / ".venv" / "bin" / "python3"),
        )

        assert out == tmp_path / "odools.toml"
        assert out.exists()

    def test_contains_required_fields(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "18.0"
        community.mkdir(parents=True)

        mod.generate_odools_config(
            "my-env",
            {"community": community},
            "/path/to/python3",
        )

        content = (tmp_path / "odools.toml").read_text()
        assert "[[config]]" in content
        assert 'name = "Odoo Dev — my-env"' in content
        assert f'odoo_path = "{community}"' in content
        assert "/path/to/python3" in content
        assert str(community / "addons") in content
        assert str(community / "odoo" / "addons") in content

    def test_enterprise_before_community_addons(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "18.0"
        enterprise = tmp_path / "src" / "enterprise" / "18.0"
        community.mkdir(parents=True)
        enterprise.mkdir(parents=True)

        mod.generate_odools_config(
            "my-env",
            {"community": community, "enterprise": enterprise},
            "/path/to/python3",
        )

        content = (tmp_path / "odools.toml").read_text()
        enterprise_pos = content.index(str(enterprise))
        community_addons_pos = content.index(str(community / "addons"))
        assert enterprise_pos < community_addons_pos

    def test_custom_repo_included(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "18.0"
        custom = tmp_path / "src" / "my-addons" / "main"
        community.mkdir(parents=True)
        custom.mkdir(parents=True)

        mod.generate_odools_config(
            "my-env",
            {"community": community, "my-addons": custom},
            "/path/to/python3",
        )

        content = (tmp_path / "odools.toml").read_text()
        assert str(custom) in content

    def test_auto_generated_comment(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "18.0"
        community.mkdir(parents=True)

        mod.generate_odools_config("my-env", {"community": community}, "/py")

        content = (tmp_path / "odools.toml").read_text()
        assert "Auto-generated" in content
        assert "do not edit" in content


class TestGenerateOdoolsConfigMultiEnv:
    def _make_config(self, envs: dict[str, str]) -> Config:
        """Build a Config from {env_name: community_branch} mapping."""
        return _make_config(*((name, {"community": branch}) for name, branch in envs.items()))

    def test_active_env_appears_first(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path / "src")
        community_active = tmp_path / "src" / "community" / "18.0"
        community_other = tmp_path / "src" / "community" / "master"
        community_active.mkdir(parents=True)
        community_other.mkdir(parents=True)

        config = self._make_config({"prod": "18.0", "dev": "master"})
        mod.generate_odools_config(
            "prod", {"community": community_active}, "/py", config
        )

        content = (tmp_path / "odools.toml").read_text()
        assert content.index('name = "Odoo Dev — prod"') < content.index('name = "Odoo Dev — dev"')

    def test_secondary_env_included_when_worktree_exists(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path / "src")
        community_active = tmp_path / "src" / "community" / "18.0"
        community_other = tmp_path / "src" / "community" / "master"
        community_active.mkdir(parents=True)
        community_other.mkdir(parents=True)

        config = self._make_config({"prod": "18.0", "dev": "master"})
        mod.generate_odools_config(
            "prod", {"community": community_active}, "/py", config
        )

        content = (tmp_path / "odools.toml").read_text()
        assert content.count("[[config]]") == 2
        assert 'name = "Odoo Dev — dev"' in content

    def test_secondary_env_skipped_when_community_missing(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path / "src")
        community_active = tmp_path / "src" / "community" / "18.0"
        community_active.mkdir(parents=True)
        # community/master intentionally NOT created

        config = self._make_config({"prod": "18.0", "dev": "master"})
        mod.generate_odools_config(
            "prod", {"community": community_active}, "/py", config
        )

        content = (tmp_path / "odools.toml").read_text()
        assert content.count("[[config]]") == 1
        assert 'name = "Odoo Dev — dev"' not in content

    def test_no_config_produces_single_section(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "18.0"
        community.mkdir(parents=True)

        mod.generate_odools_config("my-env", {"community": community}, "/py")

        content = (tmp_path / "odools.toml").read_text()
        assert content.count("[[config]]") == 1

    def test_active_env_not_duplicated(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        monkeypatch.setattr(mod, "SRC_DIR", tmp_path / "src")
        community_active = tmp_path / "src" / "community" / "18.0"
        community_other = tmp_path / "src" / "community" / "master"
        community_active.mkdir(parents=True)
        community_other.mkdir(parents=True)

        config = self._make_config({"prod": "18.0", "dev": "master"})
        mod.generate_odools_config(
            "prod", {"community": community_active}, "/py", config
        )

        content = (tmp_path / "odools.toml").read_text()
        assert content.count('name = "Odoo Dev — prod"') == 1
