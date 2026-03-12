"""Tests for config loading: list_profiles, get_profile (new [[profile]] format)."""
import sys
import pytest
from oo.config import Config, Profile, BranchSpec, list_profiles, get_profile, _parse_config


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


class TestListProfiles:
    def test_returns_names_in_order(self):
        config = _make_config(
            ("master", {"community": "master"}),
            ("dev", {"community": "18.0"}),
        )
        assert list_profiles(config) == ["master", "dev"]

    def test_empty_config_returns_empty(self):
        config = Config(profiles=[])
        assert list_profiles(config) == []

    def test_single_profile(self):
        config = _make_config(("my-env", {"community": "master"}))
        assert list_profiles(config) == ["my-env"]


class TestGetProfile:
    def test_found_profile_returns_it(self):
        config = _make_config(("my-env", {"community": "master"}))
        profile = get_profile(config, "my-env")
        assert profile.name == "my-env"
        assert profile.branch_specs["community"].branch == "master"

    def test_missing_profile_raises_system_exit(self):
        config = _make_config(("other", {"community": "master"}))
        with pytest.raises(SystemExit):
            get_profile(config, "nonexistent")

    def test_profile_without_branches_raises_system_exit(self):
        config = Config(
            profiles=[Profile(name="empty", branch_specs={}, odoorc={}, options={})],
            odoorc={}, remotes={}, options={},
        )
        with pytest.raises(SystemExit):
            get_profile(config, "empty")

    def test_profile_branch_spec_with_arrow(self):
        config = _make_config(
            ("my-feature", {"community": "dev/fix -> origin/master", "enterprise": "master"})
        )
        profile = get_profile(config, "my-feature")
        community = profile.branch_specs["community"]
        assert community.branch == "dev/fix"
        assert community.rebase_base == "origin/master"
        assert profile.branch_specs["enterprise"].branch == "master"


class TestParseConfig:
    def test_profiles_order_preserved(self):
        data = {
            "profile": [
                {"name": "zebra", "branch": {"community": "master"}},
                {"name": "alpha", "branch": {"community": "18.0"}},
            ]
        }
        config = _parse_config(data)
        assert [p.name for p in config.profiles] == ["zebra", "alpha"]

    def test_global_odoorc_loaded(self):
        data = {
            "odoorc": {"port": 8069, "db_host": "postgres"},
            "profile": [{"name": "master", "branch": {"community": "master"}}],
        }
        config = _parse_config(data)
        assert config.odoorc["port"] == 8069
        assert config.odoorc["db_host"] == "postgres"

    def test_remote_loaded(self):
        data = {
            "remote": {"my-addons": {"origin": "git@github.com:user/addons.git"}},
            "profile": [{"name": "master", "branch": {"community": "master"}}],
        }
        config = _parse_config(data)
        assert "my-addons" in config.remotes
        assert config.remotes["my-addons"]["origin"] == "git@github.com:user/addons.git"

    def test_profile_odoorc_override(self):
        data = {
            "odoorc": {"port": 8069},
            "profile": [
                {"name": "dev", "branch": {"community": "master"}, "odoorc": {"port": 8070}},
            ],
        }
        config = _parse_config(data)
        profile = config.profiles[0]
        assert profile.odoorc["port"] == 8070

    def test_profile_missing_name_skipped(self):
        data = {
            "profile": [
                {"branch": {"community": "master"}},  # no 'name'
                {"name": "valid", "branch": {"community": "18.0"}},
            ]
        }
        config = _parse_config(data)
        assert len(config.profiles) == 1
        assert config.profiles[0].name == "valid"
