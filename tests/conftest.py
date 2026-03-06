"""Load scripts/odoo-env (no .py extension) as a module."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest


def load_odoo_env():
    script = str(Path(__file__).resolve().parent.parent / "scripts" / "odoo-env")
    loader = SourceFileLoader("odoo_env", script)
    spec = spec_from_loader("odoo_env", loader)
    mod = module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def mod():
    return load_odoo_env()
