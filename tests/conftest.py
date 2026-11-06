# SPDX-License-Identifier: MIT
"""Shared fixtures for the Phase 1 test suite."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "schema" / "examples"


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("RESUME_PRO_WORKSPACE_DIR", str(tmp_path / "workspace"))


def load_example(name: str) -> dict[str, Any]:
    with (EXAMPLES / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def student_vault() -> dict[str, Any]:
    return load_example("vault-student.yaml")


@pytest.fixture
def student_projects_vault() -> dict[str, Any]:
    return load_example("vault-student-projects.yaml")


@pytest.fixture
def experienced_vault() -> dict[str, Any]:
    return load_example("vault-experienced.yaml")


@pytest.fixture
def incomplete_vault() -> dict[str, Any]:
    return load_example("vault-incomplete.yaml")


@pytest.fixture
def clone():
    def _clone(value):
        return copy.deepcopy(value)

    return _clone
