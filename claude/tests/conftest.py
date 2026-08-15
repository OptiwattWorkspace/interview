"""Shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from taskbot.config import Config  # noqa: E402
from taskbot.store import Store  # noqa: E402


@pytest.fixture
def cfg() -> Config:
    return Config(
        me="casey",
        handles={"5551234567": "michelle"},
        trigger="/",
    )


@pytest.fixture
def store(tmp_path) -> Store:
    with Store(tmp_path / "tasks.db") as s:
        yield s
