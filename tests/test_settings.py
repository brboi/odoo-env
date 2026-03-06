"""Tests for odoo-env.toml loading: list_envs, get_env."""
import pytest


class TestListEnvs:
    def test_excludes_reserved_key(self, mod):
        toml_data = {"_": {"odoorc": {}}, "my-env": {"branches": {"community": "master"}}}
        assert "_" not in mod.list_envs(toml_data)

    def test_returns_sorted_names(self, mod):
        toml_data = {
            "zebra": {"branches": {"community": "master"}},
            "alpha": {"branches": {"community": "18.0"}},
            "my-project": {"branches": {"community": "17.0"}},
        }
        assert mod.list_envs(toml_data) == ["alpha", "my-project", "zebra"]

    def test_empty_dict_returns_empty_list(self, mod):
        assert mod.list_envs({}) == []

    def test_only_reserved_key_returns_empty(self, mod):
        assert mod.list_envs({"_": {"odoorc": {}}}) == []


class TestGetEnv:
    def test_found_env_returns_dict(self, mod):
        toml_data = {"my-env": {"branches": {"community": "master"}}}
        result = mod.get_env(toml_data, "my-env")
        assert result == {"branches": {"community": "master"}}

    def test_missing_env_raises_system_exit(self, mod):
        with pytest.raises(SystemExit):
            mod.get_env({"other": {"branches": {"community": "master"}}}, "nonexistent")

    def test_reserved_name_raises_system_exit(self, mod):
        with pytest.raises(SystemExit):
            mod.get_env({"_": {"odoorc": {}}}, "_")

    def test_env_without_branches_and_no_defaults_raises(self, mod):
        toml_data = {"my-env": {"odoorc": {"port": 8069}}}
        with pytest.raises(SystemExit):
            mod.get_env(toml_data, "my-env")

    def test_env_without_branches_but_default_branches_ok(self, mod):
        toml_data = {
            "_": {"branches": {"upgrade": "master"}},
            "my-env": {"odoorc": {"port": 8069}},
        }
        # No branches in env but _.branches has content — should not raise
        result = mod.get_env(toml_data, "my-env")
        assert result == {"odoorc": {"port": 8069}}

    def test_env_branches_override_defaults(self, mod):
        """Caller merges branches; get_env just validates and returns raw section."""
        toml_data = {
            "_": {"branches": {"upgrade": "master", "community": "17.0"}},
            "my-env": {"branches": {"community": "18.0"}},
        }
        result = mod.get_env(toml_data, "my-env")
        assert result["branches"]["community"] == "18.0"
