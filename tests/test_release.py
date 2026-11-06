# SPDX-License-Identifier: MIT
"""Release gates: golden previews, license scan, skill entry, HTML-only."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ("ats-classic", "campus", "compact", "modern-sidebar", "editorial", "executive")


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
    assert len(css_files) == 12
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


def test_templates_use_plain_labeled_lines_without_lists():
    for path in sorted((ROOT / "templates").glob("*/*")):
        if path.suffix not in {".html", ".css"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"<(?:ul|ol|li)(?:\s|>)", text, re.IGNORECASE), path
        assert "list-style" not in text, path
    for path in sorted((ROOT / "src" / "resume_pro").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"<(?:ul|ol|li)(?:\s|>)", text, re.IGNORECASE), path


def test_readme_embeds_template_previews():
    readmes = {
        name: (ROOT / name).read_text(encoding="utf-8")
        for name in ("README.md", "README.en.md")
    }
    assert "| 版式 |" not in readmes["README.md"]
    assert "| Layout |" not in readmes["README.en.md"]
    for template_id in TEMPLATES:
        image = ROOT / "docs" / "images" / "templates" / f"en-{template_id}.png"
        assert image.is_file(), image
        assert image.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert image.stat().st_size > 10_000
        for name, text in readmes.items():
            assert f"docs/images/templates/en-{template_id}.png" in text, name
            assert 'width="480"' in text, name


def test_chinese_previews_use_chinese_content():
    for path in sorted((ROOT / "templates" / "cn").glob("*/preview.html")):
        text = path.read_text(encoding="utf-8")
        for marker in ("Example University", "Zhao Lin", "Course QA with RAG", "Operating Systems"):
            assert marker not in text, f"{path}: {marker}"


def test_skill_requires_prioritized_diagnosis_followup():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("### After a diagnosis", 1)[1].split("\n### ", 1)[0]
    for requirement in (
        "whether to start fixing",
        "multi-select",
        "`P0`",
        "`P1`",
        "`P2`",
        "writing framework",
        "exactly like Create from zero",
        "one question at a time",
        "same conversation and task",
        "optimize",
    ):
        assert requirement in section, f"Missing diagnosis follow-up rule: {requirement}"


def test_skill_requires_content_sufficiency_and_packaging():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    section = text.split("## Content sufficiency", 1)[1].split("\n## ", 1)[0]
    for requirement in (
        "background or problem",
        "the user's role",
        "the user's action",
        "and the result",
        "Technical stack alone is not a result",
        "合格项目的充分性标准",
        "背景/问题、角色分工、方案与取舍",
        "too thin to present a project well",
        "may not have thought to mention",
        "can you supply it",
        "Ask only for the slots that are missing",
        "项目包装",
        "ask whether to package the existing work",
        "Never let a bare label render alone",
        "concrete end month",
        "labeled points",
        "删掉，还是补齐框架、方案和结果做扎实",
        "提出合理的技术点请用户确认",
        "Ask the user for the real data first",
        "propose one or two plausible candidate values",
        "merge them into one integrated project",
        "open-sourced",
        "references/writing-engine.md",
    ):
        assert requirement in section, f"Missing content-sufficiency rule: {requirement}"


def test_frameworks_and_packaging_share_one_document():
    """Every writing framework carries its own packaging recipe in one document."""
    doc = (ROOT / "references" / "writing-engine.md").read_text(encoding="utf-8")
    packaging = doc.split("## 2. Packaging under each framework", 1)[1].split("\n## ", 1)[0]
    for framework_id in ("star", "xyz", "fab", "car", "result_first", "user_voice"):
        assert f"`{framework_id}`" in packaging, f"Missing packaging recipe: {framework_id}"
    assert packaging.count("Labeled points:") >= 6
    assert "never tied to one framework" in doc


def test_short_line_rule_is_documented():
    """Project/experience intros must fill every line to at least 2/5 width."""
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    section = skill.split("## Content sufficiency", 1)[1].split("\n## ", 1)[0]
    assert "至少占可打印宽度的 2/5" in section
    assert "优先扩句" in section
    engine = (ROOT / "references" / "writing-engine.md").read_text(encoding="utf-8")
    shared = engine.split("Shared rules for every recipe:", 1)[1].split("\n## ", 1)[0]
    assert "at least 2/5 of the printable width" in shared
    assert "expand the sentence with real detail (preferred)" in shared
    install = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
    assert "qa.layout.short_line" in install


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
