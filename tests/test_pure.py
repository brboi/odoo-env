"""Tests for pure functions: stable_base, build_paths, parse_pr, branch_to_dir."""
from pathlib import Path

import pytest


class TestParsePr:
    def test_none_for_regular_branch(self, mod):
        assert mod.parse_pr("18.0") is None
        assert mod.parse_pr("18.0-fix") is None
        assert mod.parse_pr("master") is None
        assert mod.parse_pr("master-parrot") is None

    def test_origin_pr(self, mod):
        spec = mod.parse_pr("pr/1261")
        assert spec is not None
        assert spec["number"] == "1261"
        assert spec["remote_url"] is None
        assert spec["github_org_repo"] is None
        assert spec["dir_slug"] == "pr-1261"

    def test_origin_pr_large_number(self, mod):
        spec = mod.parse_pr("pr/99999")
        assert spec["number"] == "99999"
        assert spec["dir_slug"] == "pr-99999"

    def test_fork_pr_shorthand(self, mod):
        spec = mod.parse_pr("odoo-dev/enterprise#1261")
        assert spec is not None
        assert spec["number"] == "1261"
        assert spec["remote_url"] == "git@github.com:odoo-dev/enterprise.git"
        assert spec["github_org_repo"] == "odoo-dev/enterprise"
        assert spec["dir_slug"] == "odoo-dev-pr-1261"

    def test_fork_pr_full_url(self, mod):
        spec = mod.parse_pr("https://github.com/odoo-dev/enterprise/pull/1261")
        assert spec is not None
        assert spec["number"] == "1261"
        assert spec["remote_url"] == "git@github.com:odoo-dev/enterprise.git"
        assert spec["github_org_repo"] == "odoo-dev/enterprise"
        assert spec["dir_slug"] == "odoo-dev-pr-1261"

    def test_fork_pr_shorthand_and_url_are_equivalent(self, mod):
        shorthand = mod.parse_pr("odoo-dev/enterprise#1261")
        full_url = mod.parse_pr("https://github.com/odoo-dev/enterprise/pull/1261")
        assert shorthand == full_url

    def test_pr_slash_must_be_numeric(self, mod):
        assert mod.parse_pr("pr/not-a-number") is None
        assert mod.parse_pr("pr/") is None


class TestBranchToDir:
    def test_regular_branch_unchanged(self, mod):
        assert mod.branch_to_dir("18.0") == "18.0"
        assert mod.branch_to_dir("master") == "master"

    def test_regular_branch_replaces_slash(self, mod):
        assert mod.branch_to_dir("my/feature") == "my-feature"
        assert mod.branch_to_dir("origin/18.0") == "origin-18.0"

    def test_origin_pr(self, mod):
        assert mod.branch_to_dir("pr/1261") == "pr-1261"

    def test_fork_pr_shorthand(self, mod):
        assert mod.branch_to_dir("odoo-dev/enterprise#1261") == "odoo-dev-pr-1261"

    def test_fork_pr_full_url(self, mod):
        assert mod.branch_to_dir("https://github.com/odoo-dev/enterprise/pull/1261") == "odoo-dev-pr-1261"


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
