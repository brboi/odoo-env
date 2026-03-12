"""Configuration loading and resolution for odoo-env.toml (new [[profile]] format)."""
from __future__ import annotations

import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BranchSpec:
    """A branch specification, optionally with a rebase base."""

    branch: str
    rebase_base: str | None = None

    @classmethod
    def parse(cls, spec: str) -> "BranchSpec":
        """Parse 'branch -> base' or just 'branch'."""
        if " -> " in spec:
            branch, base = spec.split(" -> ", 1)
            return cls(branch.strip(), base.strip())
        return cls(spec.strip())

    def __str__(self) -> str:
        if self.rebase_base:
            return f"{self.branch} -> {self.rebase_base}"
        return self.branch


@dataclass
class Profile:
    """A named development profile."""

    name: str
    branch_specs: dict[str, BranchSpec] = field(default_factory=dict)
    odoorc: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Config:
    """Loaded odoo-env.toml configuration."""

    profiles: list[Profile]
    odoorc: dict[str, Any] = field(default_factory=dict)      # global [odoorc]
    remotes: dict[str, dict] = field(default_factory=dict)    # {name: {origin: url}} from [remote.X]
    options: dict[str, Any] = field(default_factory=dict)     # global [options]


def parse_branch_spec(spec: str) -> BranchSpec:
    """Parse a branch spec string into a BranchSpec."""
    return BranchSpec.parse(spec)


def load_config() -> Config:
    """Load odoo-env.toml from ROOT_DIR (new [[profile]] format).

    If missing, copy from .example and exit with instructions.
    """
    import oo as _pkg
    root_dir = _pkg.ROOT_DIR
    toml_path = root_dir / "odoo-env.toml"
    example_path = root_dir / "odoo-env.toml.example"

    if not toml_path.exists():
        if example_path.exists():
            shutil.copy2(example_path, toml_path)
            from oo.ui import log_ok
            log_ok("Created odoo-env.toml from example.")
            print("  Edit odoo-env.toml to configure your profiles, then re-run.", file=sys.stderr)
        else:
            from oo.ui import log_error
            log_error("odoo-env.toml not found (and no odoo-env.toml.example to copy from).")
        sys.exit(1)

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    return _parse_config(data)


def _parse_config(data: dict) -> Config:
    """Parse raw TOML dict into a Config object."""
    global_odoorc = dict(data.get("odoorc", {}))
    remotes = {name: dict(spec) for name, spec in data.get("remote", {}).items()}
    global_options = dict(data.get("options", {}))

    profiles: list[Profile] = []
    for p in data.get("profile", []):
        name = p.get("name", "")
        if not name:
            from oo.ui import log_warn
            log_warn("Profile missing 'name' field, skipping.")
            continue

        branch_dict = p.get("branch", {})
        branch_specs = {repo: BranchSpec.parse(spec) for repo, spec in branch_dict.items()}
        profile_odoorc_dict = dict(p.get("odoorc", {}))
        profile_options_dict = dict(p.get("options", {}))

        profiles.append(Profile(
            name=name,
            branch_specs=branch_specs,
            odoorc=profile_odoorc_dict,
            options=profile_options_dict,
        ))

    return Config(
        profiles=profiles,
        odoorc=global_odoorc,
        remotes=remotes,
        options=global_options,
    )


def list_profiles(config: Config) -> list[str]:
    """Return profile names in declaration order."""
    return [p.name for p in config.profiles]


def get_profile(config: Config, name: str) -> Profile:
    """Return a profile by name. sys.exit(1) if not found or has no branches."""
    for profile in config.profiles:
        if profile.name == name:
            if not profile.branch_specs:
                from oo.ui import log_error
                log_error(f"Profile '{name}' has no branches configured.")
                sys.exit(1)
            return profile

    from oo.ui import log_error
    log_error(f"Profile '{name}' not found in odoo-env.toml")
    names = list_profiles(config)
    if names:
        print(f"  Available: {', '.join(names)}", file=sys.stderr)
    sys.exit(1)


def profile_branch_specs(config: Config, name: str) -> dict[str, BranchSpec]:
    """Return {repo: BranchSpec} for a profile."""
    profile = get_profile(config, name)
    return profile.branch_specs


def profile_remote_urls(config: Config, name: str) -> dict[str, str]:
    """Return {repo: url} for repos in this profile that have a [remote.X] entry."""
    profile = get_profile(config, name)
    return {
        repo: config.remotes[repo]["origin"]
        for repo in profile.branch_specs
        if repo in config.remotes
    }


def profile_odoorc(config: Config, name: str) -> dict[str, Any]:
    """Return effective odoorc: global [odoorc] merged with profile overrides."""
    profile = get_profile(config, name)
    return {**config.odoorc, **profile.odoorc}


def profile_options(config: Config, name: str) -> dict[str, Any]:
    """Return effective options: global merged with profile overrides."""
    profile = get_profile(config, name)
    global_skip = set(config.options.get("skip_js_tooling", []))
    local_skip = set(profile.options.get("skip_js_tooling", []))
    return {"skip_js_tooling": list(global_skip | local_skip)}


def adhoc_profile(branch_specs: dict[str, str]) -> tuple[Config, str]:
    """Create an ad-hoc Config+profile from CLI key=value branch specs.

    Returns (Config, profile_name). Profile name derived from community branch.
    """
    community_branch = branch_specs.get("community", next(iter(branch_specs.values()), "adhoc"))
    profile_name = BranchSpec.parse(community_branch).branch.replace("/", "-")

    profile = Profile(
        name=profile_name,
        branch_specs={repo: BranchSpec.parse(spec) for repo, spec in branch_specs.items()},
        odoorc={},
        options={},
    )
    return Config(profiles=[profile], odoorc={}, remotes={}, options={}), profile_name
