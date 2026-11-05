# SPDX-License-Identifier: MIT
"""Release gates: golden previews, license scan, skill entry, HTML-only."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("ats-classic", "campus", "modern-sidebar", "editorial", "executive", "zh-professional")


def _template_dir(template_id: str) -> Path:
    for folder in ("cn", "en"):
        candidate = ROOT / "templates" / folder / template_id
        if candidate.is_dir():
            return candidate
    return ROOT / "templates" / template_id


def test_golden_previews_are_stable():
    for template_id in TEMPLATES:
        preview = _template_dir(template_id) / "preview.html"
        expected = (ROOT / "tests" / "golden" / f"{template_id}.sha256").read_text(encoding="utf-8").strip()
        actual = hashlib.sha256(preview.read_bytes()).hexdigest()
        assert actual == expected, f"{template_id} preview changed; regenerate with scripts/build_previews.py"


def test_license_scan_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "license_scan.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "LICENSE SCAN: PASS" in result.stdout


def test_skill_entrypoint_exists():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "HTML only" in text
    assert "localize" in text
    assert "Never invent facts" in text
    assert "framework" in text.lower()


def test_no_pdf_or_docx_resume_writer():
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"write_(?:text|bytes)\([^\n]*\.(pdf|docx)", text, re.IGNORECASE), path


def test_examples_and_docs_exist():
    for path in (
        "schema/examples/vault-student.yaml",
        "schema/examples/vault-student-projects.yaml",
        "schema/examples/vault-experienced.yaml",
        "schema/examples/vault-incomplete.yaml",
        "docs/install.md",
        "docs/walkthrough.md",
        "docs/evaluation.md",
        "CHANGELOG.md",
    ):
        assert (ROOT / path).is_file(), path
