"""Tests for IDE workspace generation: VS Code, Zed."""
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

        assert out == tmp_path / "workspaces" / "master" / "master.code-workspace"
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
                "COMMUNITY": str(community),
                "PATH": "/usr/bin:/bin",
            },
        )

    def test_generates_zed_settings(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "settings.json"
        assert settings_path.exists()

    def test_settings_content(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "settings.json"
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

        zed_dir = tmp_path / "workspaces" / "master" / "zed"
        community_link = zed_dir / "community"
        enterprise_link = zed_dir / "enterprise"
        assert community_link.is_symlink()
        assert enterprise_link.is_symlink()
        assert community_link.resolve() == community.resolve()
        assert enterprise_link.resolve() == enterprise.resolve()

    def test_symlinks_are_relative(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        link = tmp_path / "workspaces" / "master" / "zed" / "community"
        assert link.is_symlink()
        # readlink should be a relative path, not absolute
        assert not Path(link.readlink()).is_absolute()

    def test_symlink_odoo_env(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        link = tmp_path / "workspaces" / "master" / "zed" / "odoo-env"
        assert link.is_symlink()
        assert link.resolve() == tmp_path.resolve()

    def test_symlink_odools_toml(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)
        (tmp_path / "odools.toml").write_text("# dummy")

        self._call(mod, tmp_path, {"community": community})

        zed_dir = tmp_path / "workspaces" / "master" / "zed"
        link = zed_dir / "odools.toml"
        assert link.is_symlink()
        assert link.resolve() == (tmp_path / "odools.toml").resolve()
        assert not Path(link.readlink()).is_absolute()

    def test_file_scan_exclusions(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        assert "file_scan_exclusions" in data
        assert "**/__pycache__" in data["file_scan_exclusions"]
        assert "**/node_modules" in data["file_scan_exclusions"]

    def test_pyright_python_path(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        venv_python = data["lsp"]["basedpyright"]["settings"]["python.pythonPath"]
        assert ".venv" in venv_python

    def test_terminal_env_virtual_env(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        assert "VIRTUAL_ENV" in data["terminal"]["env"]
        assert ".venv" in data["terminal"]["env"]["VIRTUAL_ENV"]

    def test_terminal_env_path_includes_venv(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        path_val = data["terminal"]["env"]["PATH"]
        assert ".venv/bin" in path_val

    def test_odools_lsp_configured(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        settings_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        assert "odoo-ls" in data["lsp"]
        assert "binary" in data["lsp"]["odoo-ls"]

    def test_odools_selected_profile(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community}, name="my-env")

        settings_path = tmp_path / "workspaces" / "my-env" / "zed" / ".zed" / "settings.json"
        data = json.loads(settings_path.read_text())
        selected = data["lsp"]["odoo-ls"]["settings"]["Odoo.selectedProfile"]
        assert selected == "Odoo Dev \u2014 my-env"

    def test_generates_tasks_json(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        tasks_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "tasks.json"
        assert tasks_path.exists()
        tasks = json.loads(tasks_path.read_text())
        labels = [t["label"] for t in tasks]
        assert "Start Odoo" in labels
        assert "Start Debug Shell" in labels
        assert "Run Console Tests" in labels

    def test_generates_launch_json(self, mod, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "ROOT_DIR", tmp_path)
        community = tmp_path / "src" / "community" / "master"
        community.mkdir(parents=True)

        self._call(mod, tmp_path, {"community": community})

        launch_path = tmp_path / "workspaces" / "master" / "zed" / ".zed" / "launch.json"
        assert launch_path.exists()
        data = json.loads(launch_path.read_text())
        assert "configurations" in data
        names = [c["name"] for c in data["configurations"]]
        assert "Debug Odoo" in names
        assert "Debug Shell" in names
        assert all(c["type"] == "debugpy" for c in data["configurations"])
