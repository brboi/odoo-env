"""Tests for IDE workspace generation: VS Code, Zed, JetBrains."""
import json
from pathlib import Path


class TestGenerateVscodeWorkspace:
    def _call(self, mod, tmp_path, worktree_paths, name="master", env=None, odoo_rc=None):
        return mod.generate_vscode_workspace(
            name,
            worktree_paths,
            env or {"ODOO_ENV_NAME": name},
            odoo_rc or "/tmp/odoorc",
        )

    def test_generates_file(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        out = self._call(mod, tmp_path, {"community": community})

        assert out == tmp_path / ".cache" / "envs" / "master" / "master.code-workspace"
        assert out.exists()

    def test_json_structure(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        enterprise = tmp_path / "src" / "enterprise" / "master"
        community.mkdir(parents=True)
        enterprise.mkdir(parents=True)

        out = self._call(mod, tmp_path, {"community": community, "enterprise": enterprise})

        data = json.loads(out.read_text())
        assert "folders" in data
        assert "settings" in data
        assert "launch" in data

    def test_folders_names_and_relative_paths(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        enterprise = tmp_path / "src" / "enterprise" / "master"
        community.mkdir(parents=True)
        enterprise.mkdir(parents=True)

        out = self._call(mod, tmp_path, {"community": community, "enterprise": enterprise})

        data = json.loads(out.read_text())
        names = [f["name"] for f in data["folders"]]
        assert "community" in names
        assert "enterprise" in names
        # All paths must be relative (not absolute)
        for folder in data["folders"]:
            assert not Path(folder["path"]).is_absolute()

    def test_settings_python_interpreter(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        out = self._call(mod, tmp_path, {"community": community})

        data = json.loads(out.read_text())
        assert "python.defaultInterpreterPath" in data["settings"]
        # Should point to .venv inside ROOT_DIR
        assert ".venv" in data["settings"]["python.defaultInterpreterPath"]

    def test_odools_selected_configuration(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        out = self._call(mod, tmp_path, {"community": community}, name="my-env")

        data = json.loads(out.read_text())
        assert data["settings"]["Odoo.selectedProfile"] == "Odoo Dev \u2014 my-env"

    def test_launch_configuration(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        out = self._call(mod, tmp_path, {"community": community}, odoo_rc="/path/to/my-odoorc")

        data = json.loads(out.read_text())
        configs = data["launch"]["configurations"]
        assert len(configs) == 3
        names = [c["name"] for c in configs]
        assert "Start Odoo" in names
        assert "Start Debug Shell" in names
        assert "Run Console Tests" in names
        assert all(c["type"] == "debugpy" for c in configs)
        assert all(any("/path/to/my-odoorc" in a for a in c["args"]) for c in configs)

    def test_terminal_env_vars(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        env = {
            "ODOO_ENV_NAME": "master",
            "ODOO_RC": "/path/to/odoorc",
            "PYTHONPATH": str(community),
        }
        out = self._call(mod, tmp_path, {"community": community}, env=env)

        data = json.loads(out.read_text())
        linux_env = data["settings"]["terminal.integrated.env.linux"]
        osx_env = data["settings"]["terminal.integrated.env.osx"]
        assert linux_env.get("ODOO_ENV_NAME") == "master"
        assert linux_env.get("ODOO_RC") == "/path/to/odoorc"
        assert osx_env.get("ODOO_ENV_NAME") == "master"

    def test_search_and_files_exclude(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        out = self._call(mod, tmp_path, {"community": community})

        data = json.loads(out.read_text())
        assert data["settings"]["search.useIgnoreFiles"] is False
        assert data["settings"]["search.exclude"]["**/__pycache__"] is True
        assert data["settings"]["files.exclude"]["**/__pycache__"] is True


class TestGenerateZedWorkspace:
    def _call(self, mod, tmp_path, worktree_paths, name="master", env=None):
        community = worktree_paths.get("community")
        return mod.generate_zed_workspace(
            name,
            worktree_paths,
            env or {
                "ODOO_ENV_NAME": name,
                "ODOO_RC": "/tmp/odoorc",
                "PYTHONPATH": str(community),
                "ODOO_PATH": str(community),
            },
        )

    def test_generates_zed_settings(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / ".cache" / "envs" / "master" / ".zed" / "settings.json"
        assert settings_path.exists()

    def test_settings_content(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / ".cache" / "envs" / "master" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        assert "lsp" in data
        assert "terminal" in data
        assert data["terminal"]["env"]["ODOO_ENV_NAME"] == "master"

    def test_creates_symlinks(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        enterprise = tmp_path / "src" / "enterprise" / "master"
        community.mkdir(parents=True)
        enterprise.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community, "enterprise": enterprise})

        env_dir = tmp_path / ".cache" / "envs" / "master"
        community_link = env_dir / "community"
        enterprise_link = env_dir / "enterprise"
        assert community_link.is_symlink()
        assert enterprise_link.is_symlink()
        assert community_link.resolve() == community.resolve()
        assert enterprise_link.resolve() == enterprise.resolve()

    def test_symlinks_are_relative(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        link = tmp_path / ".cache" / "envs" / "master" / "community"
        assert link.is_symlink()
        # readlink should be a relative path, not absolute
        assert not Path(link.readlink()).is_absolute()

    def test_file_scan_exclusions(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / ".cache" / "envs" / "master" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        assert "file_scan_exclusions" in data
        assert "**/__pycache__" in data["file_scan_exclusions"]
        assert "**/node_modules" in data["file_scan_exclusions"]

    def test_pyright_python_path(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / ".cache" / "envs" / "master" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        venv_python = data["lsp"]["basedpyright"]["settings"]["python.pythonPath"]
        assert ".venv" in venv_python


class TestGenerateIdeaProject:
    def _call(self, mod, tmp_path, worktree_paths, name="master", env=None):
        return mod.generate_idea_project(name, worktree_paths, env or {})

    def test_generates_modules_xml(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        modules_xml = tmp_path / ".cache" / "envs" / "master" / ".idea" / "modules.xml"
        assert modules_xml.exists()

    def test_generates_iml_file(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        iml = tmp_path / ".cache" / "envs" / "master" / ".idea" / "odoo-master.iml"
        assert iml.exists()

    def test_generates_misc_xml(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        misc_xml = tmp_path / ".cache" / "envs" / "master" / ".idea" / "misc.xml"
        assert misc_xml.exists()
        content = misc_xml.read_text()
        assert "ProjectRootManager" in content
        assert "Python SDK" in content

    def test_project_name_file(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community}, name="my-env")

        name_file = tmp_path / ".cache" / "envs" / "my-env" / ".idea" / ".name"
        assert name_file.exists()
        assert name_file.read_text() == "odoo-my-env"

    def test_iml_contains_content_roots(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        enterprise = tmp_path / "src" / "enterprise" / "master"
        community.mkdir(parents=True)
        enterprise.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community, "enterprise": enterprise})

        iml = tmp_path / ".cache" / "envs" / "master" / ".idea" / "odoo-master.iml"
        content = iml.read_text()
        assert str(community) in content
        assert str(enterprise) in content

    def test_modules_xml_references_iml(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community}, name="my-env")

        modules_xml = tmp_path / ".cache" / "envs" / "my-env" / ".idea" / "modules.xml"
        content = modules_xml.read_text()
        assert "odoo-my-env.iml" in content

    def test_iml_exclude_folders(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        iml = tmp_path / ".cache" / "envs" / "master" / ".idea" / "odoo-master.iml"
        content = iml.read_text()
        assert "node_modules" in content
        assert "__pycache__" in content
        assert "excludeFolder" in content
