# SPDX-License-Identifier: MIT
"""Non-editable install support: resources travel with the wheel.

`pip install .` must leave `resume templates`, schema validation, and profile
loading working from any directory. The wheel therefore bundles templates/,
schema/, and profiles/ inside the resume_pro package, and the resource
locators find them in site-packages while preserving env overrides and the
source-checkout layout.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from resume_pro import paths, profile
from resume_pro.errors import VaultError

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("ats-classic", "campus", "compact", "modern-sidebar", "editorial", "executive")


def test_wheel_bundles_templates_schema_profiles(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--wheel-dir", str(tmp_path), str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    wheels = list(tmp_path.glob("*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as bundle:
        names = set(bundle.namelist())
    for folder in ("cn", "en"):
        for template_id in TEMPLATES:
            for filename in ("template.html", "styles.css", "manifest.json"):
                assert f"resume_pro/templates/{folder}/{template_id}/{filename}" in names
    for schema in ("vault.schema.json", "application.schema.json", "template.schema.json"):
        assert f"resume_pro/schema/{schema}" in names
    assert "resume_pro/profiles/markets/cn_internet.yaml" in names
    assert "resume_pro/profiles/personas/student_with_internship.yaml" in names
    assert not any("templates/user-" in name for name in names)


def _fake_site_packages(tmp_path: Path) -> Path:
    package = tmp_path / "site-packages" / "resume_pro"
    (package / "templates" / "cn" / "ats-classic").mkdir(parents=True)
    (package / "templates" / "en" / "ats-classic").mkdir(parents=True)
    (package / "schema").mkdir()
    (package / "schema" / "vault.schema.json").write_text("{}", encoding="utf-8")
    (package / "profiles" / "markets").mkdir(parents=True)
    (package / "profiles" / "personas").mkdir(parents=True)
    return package


def test_installed_package_layout_is_discovered(tmp_path, monkeypatch):
    package = _fake_site_packages(tmp_path)
    monkeypatch.setattr(paths, "__file__", str(package / "paths.py"))
    monkeypatch.setattr(profile, "__file__", str(package / "profile.py"))
    assert paths.templates_dir() == package / "templates"
    assert paths.schema_dir() == package / "schema"
    assert profile.profiles_dir() == package / "profiles"


def test_env_overrides_still_win(tmp_path, monkeypatch):
    package = _fake_site_packages(tmp_path)
    monkeypatch.setattr(paths, "__file__", str(package / "paths.py"))
    monkeypatch.setattr(profile, "__file__", str(package / "profile.py"))
    override = tmp_path / "elsewhere"
    (override / "templates" / "cn").mkdir(parents=True)
    (override / "schema").mkdir()
    (override / "schema" / "vault.schema.json").write_text("{}", encoding="utf-8")
    (override / "profiles" / "markets").mkdir(parents=True)
    monkeypatch.setenv("RESUME_PRO_TEMPLATES_DIR", str(override / "templates"))
    monkeypatch.setenv("RESUME_PRO_SCHEMA_DIR", str(override / "schema"))
    monkeypatch.setenv("RESUME_PRO_PROFILES_DIR", str(override / "profiles"))
    assert paths.templates_dir() == override / "templates"
    assert paths.schema_dir() == override / "schema"
    assert profile.profiles_dir() == override / "profiles"
    monkeypatch.setenv("RESUME_PRO_TEMPLATES_DIR", str(tmp_path / "missing"))
    with pytest.raises(VaultError):
        paths.templates_dir()


def test_source_checkout_still_resolves_repository_resources():
    assert paths.templates_dir() == ROOT / "templates"
    assert paths.schema_dir() == ROOT / "schema"
    assert profile.profiles_dir() == ROOT / "profiles"