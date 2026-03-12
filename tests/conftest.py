"""Test fixtures for the oo package."""
import sys
from pathlib import Path

import pytest

# Ensure repo root is on sys.path so `import oo` works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def mod():
    """Return the oo package as a module (backward-compatible test fixture)."""
    import oo
    return oo
