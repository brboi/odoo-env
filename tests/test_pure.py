"""Tests for pure functions: stable_base, build_paths."""
from pathlib import Path

import pytest


class TestStableBase:
    def test_master_is_stable(self, mod):
        assert mod.stable_base("master") is None

    def test_version_branch_is_stable(self, mod):
        assert mod.stable_base("18.0") is None
        assert mod.stable_base("17.0") is None

    def test_master_feature_branch(self, mod):
        assert mod.stable_base("master-parrot") == "master"
        assert mod.stable_base("master-my-feature") == "master"

    def test_version_feature_branch(self, mod):
        assert mod.stable_base("18.0-fix") == "18.0"
        assert mod.stable_base("17.0-my-feature") == "17.0"

    def test_arbitrary_branch_without_version_prefix(self, mod):
        assert mod.stable_base("my-random-branch") is None
        assert mod.stable_base("fix-invoice") is None


class TestBuildPaths:
    def test_community_only(self, mod, tmp_path):
        community = tmp_path / "community" / "master"
        python_path, addons_path = mod.build_paths(community, {})

        assert python_path == str(community)
        assert str(community / "addons") in addons_path
        assert str(community / "odoo" / "addons") in addons_path

    def test_community_plus_enterprise(self, mod, tmp_path):
        community = tmp_path / "community" / "18.0"
        enterprise = tmp_path / "enterprise" / "18.0"
        _, addons_path = mod.build_paths(community, {"enterprise": enterprise})

        parts = addons_path.split(",")
        # enterprise addons should come before community addons
        assert parts[0] == str(enterprise)
        assert str(community / "addons") in addons_path

    def test_multiple_extras_all_present(self, mod, tmp_path):
        community = tmp_path / "community" / "18.0"
        extra1 = tmp_path / "repo1" / "18.0"
        extra2 = tmp_path / "repo2" / "18.0"
        _, addons_path = mod.build_paths(community, {"repo1": extra1, "repo2": extra2})

        parts = addons_path.split(",")
        # extras come before community paths
        assert str(community / "addons") not in parts[:2]
        assert str(extra1) in addons_path
        assert str(extra2) in addons_path
