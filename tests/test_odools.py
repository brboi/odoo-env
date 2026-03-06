"""Tests for generate_odools_config."""
from pathlib import Path


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
