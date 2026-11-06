# SPDX-License-Identifier: MIT
"""Release gates: golden previews, license scan, skill entry, HTML-only."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("ats-classic", "campus", "modern-sidebar", "editorial", "executive")


def test_golden_previews_are_stable():
    for folder in ("cn", "en"):
        for template_id in TEMPLATES:
            preview = ROOT / "templates" / folder / template_id / "preview.html"
            expected = (ROOT / "tests" / "golden" / f"{folder}-{template_id}.sha256").read_text(encoding="utf-8").strip()
            actual = hashlib.sha256(preview.read_bytes()).hexdigest()
            assert actual == expected, f"{folder}/{template_id} preview changed; regenerate with scripts/build_previews.py --update-golden"


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
    assert "self-contained A4 HTML" in text
    assert "localize" in text
    assert "Never invent facts" in text
    assert "framework" in text.lower()


def test_skill_requires_continuous_interactive_questions():
    """Guard the host-agent contract; this does not execute a host question UI."""
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "## Mandatory continuous interaction" in text
    protocol = text.split("## Mandatory continuous interaction", 1)[1].split("\n## ", 1)[0]
    for requirement in (
        "MUST call the host's interactive question tool",
        "AskUserQuestion",
        "MUST NOT end the task with a final-answer question",
        "same conversation and task",
        "free-text",
        "--id",
        "--summary",
        "complete: true",
        "summary.confirmed: true",
        "never skip confirmation",
        "pause",
        "interaction.tool_unavailable",
        "Do not start a new chat",
        "Do not use a blocking terminal prompt",
    ):
        assert requirement in protocol, f"Missing interaction rule: {requirement}"
    assert len(text.splitlines()) < 500
    assert "TODO:" not in text


def test_skill_asks_template_choice_and_preview_location():
    """Guard the create-flow contract: ask which layout and show where to preview it."""
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    create = text.split("### Create from zero", 1)[1].split("\n### ", 1)[0]
    for requirement in (
        "Choose the template with the user before rendering.",
        "interactive tool",
        "resume templates",
        "preview.html",
        "--template",
        "the default is used only after the user confirms it",
    ):
        assert requirement in create, f"Missing template-choice rule: {requirement}"
    optimize = text.split("### Optimize an existing resume", 1)[1].split("\n### ", 1)[0]
    assert "choose a library layout with the interactive tool" in optimize
    assert "preview.html" in optimize


def test_templates_avoid_italic_and_variant_typography():
    """Resume designs use standard sans glyphs: no italic/serif or alternate forms."""
    css_files = sorted((ROOT / "templates").glob("*/*/styles.css"))
    assert len(css_files) == 10
    for path in css_files:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        assert "font-style: italic" not in lowered, path
        assert "font-style: oblique" not in lowered, path
        assert "--font-heading" not in text, path
        assert re.search(r"(?<!sans-)serif\b", text) is None, path
        for banned in ("Georgia", "Times New Roman", "Songti", "SimSun"):
            assert banned not in text, f"{path}: {banned}"
        for required in (
            "font-synthesis: none;",
            "font-variant-ligatures: none;",
            "font-variant-numeric: lining-nums",
            "font-variant-east-asian: normal;",
        ):
            assert required in text, f"{path}: missing {required}"
    for path in sorted((ROOT / "templates").rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"<(?:em|i)(?:\s|>)", text, re.IGNORECASE), path
        assert "font-style: italic" not in text.lower(), path


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
