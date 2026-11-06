# SPDX-License-Identifier: MIT
"""Packaging gates: private-safe archive, determinism, and bootstrap readiness."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("ats-classic", "campus", "modern-sidebar", "editorial", "executive", "zh-professional")
LIBRARY = {(template_id, language) for template_id in TEMPLATES for language in ("zh", "en")}
PRIVATE_MARKERS = (
    "docs/local/",
    "templates/user-",
    "/designs/",
    "/__pycache__/",
    "/.git/",
    "/.resume/",
    "/applications/",
)


def run(args: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=300,
    )


def build(tmp_path: Path, name: str, *extra: str) -> tuple[Path, dict[str, object]]:
    archive = tmp_path / name
    result = run([str(ROOT / "scripts" / "package_skill.py"), "--output", str(archive), "--json", *extra])
    assert result.returncode == 0, result.stdout + result.stderr
    return archive, json.loads(result.stdout)


def names(archive: Path) -> list[str]:
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.namelist()
    assert entries
    for entry in entries:
        assert entry.startswith("resume-pro-skill/"), entry
    return [entry.split("/", 1)[1] for entry in entries]


def assert_private_safe(relative_names: list[str]) -> None:
    for name in relative_names:
        padded = f"/{name}"
        for marker in PRIVATE_MARKERS:
            assert marker not in padded, f"private path in archive: {name}"
        assert not name.endswith((".env", ".local.json", ".local.html", ".pem", ".key")), name


def test_archive_is_complete_private_safe_and_deterministic(tmp_path):
    first, report = build(tmp_path, "first.zip")
    assert report["ok"] is True
    assert report["runtime_check"] == {"ok": True, "templates": 12, "errors": []}
    assert Path(report["archive"]) == first
    assert report["files"] > 100
    assert report["sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()

    relative_names = names(first)
    assert_private_safe(relative_names)
    for required in (
        "SKILL.md",
        "LICENSE",
        "ATTRIBUTIONS.md",
        "bootstrap.py",
        "resume.py",
        "requirements.txt",
        "src/resume_pro/cli.py",
        "schema/vault.schema.json",
        "profiles/markets/intl_en.yaml",
        "docs/install.md",
        "docs/quickstart.md",
    ):
        assert required in relative_names, required
    for folder in ("cn", "en"):
        for template_id in TEMPLATES:
            for filename in ("manifest.json", "template.html", "styles.css", "preview.html"):
                assert f"templates/{folder}/{template_id}/{filename}" in relative_names
    assert not any(name.startswith("tests/") for name in relative_names)

    second, second_report = build(tmp_path, "second.zip", "--skip-runtime-check")
    assert second_report["sha256"] == report["sha256"]
    assert first.read_bytes() == second.read_bytes()


def test_archive_can_include_tests_without_private_material(tmp_path):
    archive, report = build(tmp_path, "with-tests.zip", "--include-tests", "--skip-runtime-check")
    assert report["ok"] is True
    relative_names = names(archive)
    assert_private_safe(relative_names)
    assert "tests/test_render.py" in relative_names
    assert "tests/golden/en-campus.sha256" in relative_names


def test_bootstrap_reports_runtime_ready():
    result = run([str(ROOT / "bootstrap.py"), "--check", "--json"])
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"] is True
    assert report["python_ok"] is True
    assert report["missing_dependencies"] == []
    assert report["library_templates"] == 12
    assert set(report["template_variants"]) == {f"{template_id}:{language}" for template_id, language in LIBRARY}


def test_skill_and_install_docs_explain_packaging():
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert len(skill.splitlines()) < 500
    for token in ("package_skill.py", "bootstrap.py", "resume.py", "--install", "--deps-only"):
        assert token in skill, token
    install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
    for token in ("package_skill.py", "bootstrap.py", "resume.py", "--include-tests", "SHA-256", "docs/local"):
        assert token in install, token
    for readme in ("README.md", "README.en.md"):
        assert "package_skill.py" in (ROOT / readme).read_text(encoding="utf-8")
