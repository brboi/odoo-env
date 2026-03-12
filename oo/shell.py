"""Shell activation: build odoorc, make env vars, launch subshell."""
from __future__ import annotations

import configparser
import os
import sys
from pathlib import Path
from typing import Any


def build_odoo_conf(
    root_dir: Path,
    addons_path: str,
    port: int,
    name: str,
    defaults: dict,
    odoorc_overrides: dict,
) -> Path:
    """Write .cache/envs/<name>/odoorc from merged defaults + overrides."""
    out = root_dir / ".cache" / "envs" / name / "odoorc"

    cfg = configparser.ConfigParser()
    cfg.add_section("options")

    for key, value in defaults.items():
        if key != "port":
            cfg["options"][key] = str(value)
    for key, value in odoorc_overrides.items():
        if key != "port":
            cfg["options"][key] = str(value)

    cfg["options"]["addons_path"] = addons_path
    cfg["options"]["http_port"] = str(port)

    if "db_name" not in cfg["options"]:
        cfg["options"]["db_name"] = name

    if "dbfilter" not in cfg["options"]:
        cfg["options"]["dbfilter"] = f"^{cfg['options']['db_name']}$"

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        cfg.write(f)
    return out


def launch_shell(env: dict[str, str]) -> None:
    """Detect the parent shell and exec into it with the given env vars."""
    from oo.ui import log_info
    os.environ.update(env)
    try:
        shell = os.readlink(f"/proc/{os.getppid()}/exe")
    except OSError:
        shell = os.environ.get("SHELL", "/bin/sh")
    log_info("Launching subshell (exit to return)...")
    os.execv(shell, [shell, "-i"])
