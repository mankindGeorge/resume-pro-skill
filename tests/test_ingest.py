# SPDX-License-Identifier: MIT
"""Ingestion tests across HTML, DOCX, PDF, text, and scanned PDF."""

from __future__ import annotations

import pytest

from resume_pro.ingest import IngestError, detect_lang, ingest_file, to_vault
from resume_pro.template_audit import VERDICT_REPLACE, VERDICT_UNMAINTAINABLE, audit_template
from tests.ingest_fixtures import (
    BAD_HTML,
    TWO_COLUMN_HTML,
    write_docx,
    write_html,
    write_pdf,
    write_scanned_pdf,
)


def test_html_extraction(tmp_path):
    path = write_html(tmp_path / "resume.html")
    result = ingest_file(path)
    assert result.format == "html"
    assert result.fields["name"] == "Li Ming"
    assert result.fields["email"] == "liming@example.com"
    assert result.fields["phone"].startswith("+86")
    assert result.fields["links"][0]["kind"] == "github"
    education = result.fields["education"][0]
    assert education["school"] == "Example University"
    assert education["degree"] == "B.Eng"
    assert education["major"] == "Computer Science"
    assert education["start"] == "2023-09"
    assert education["end"] == "2027-06"
    experience = result.fields["experience"][0]
    assert experience["company"] == "Acme Cloud"
    assert experience["title"] == "Backend Intern"
    assert experience["type"] == "internship"
    assert len(experience["bullets"]) == 2
    assert result.fields["projects"][0]["name"] == "Course QA with RAG"
    assert len(result.fields["projects"][0]["bullets"]) == 2
    assert "Java" in result.fields["skills"]
    assert result.layout.page_size == "a4"
    assert result.layout.columns == 1
    assert result.layout.body_font_size_pt == 10.5
    assert result.layout.margins_mm["left"] == 18.0
    assert not result.scanned


def test_docx_extraction(tmp_path):
    path = write_docx(tmp_path / "resume.docx")
    result = ingest_file(path)
    assert result.format == "docx"
    assert result.fields["name"] == "Li Ming"
    assert result.fields["education"][0]["school"] == "Example University"
    assert result.fields["experience"][0]["company"] == "Acme Cloud"
    assert result.fields["experience"][0]["type"] == "internship"
    assert len(result.fields["experience"][0]["bullets"]) == 2
    assert len(result.fields["projects"][0]["bullets"]) == 2
    assert result.layout.page_size == "letter"
    assert result.layout.columns == 1
    assert result.layout.editable_source is True


def test_pdf_extraction(tmp_path):
    path = write_pdf(tmp_path / "resume.pdf")
    result = ingest_file(path)
    assert result.format == "pdf"
    assert not result.scanned
    assert result.page_count == 1
    assert result.fields["name"] == "Li Ming"
    assert result.fields["education"][0]["school"] == "Example University"
    assert result.fields["experience"][0]["title"] == "Backend Intern"
    assert result.layout.page_size == "letter"
    assert result.layout.text_outside_page == 0
    assert result.layout.editable_source is False


def test_scanned_pdf_is_flagged(tmp_path):
    path = write_scanned_pdf(tmp_path / "scan.pdf")
    result = ingest_file(path)
    assert result.scanned is True
    assert result.fields == {}
    audit = audit_template(result, market="intl_en", persona="experienced")
    assert audit.verdict == VERDICT_UNMAINTAINABLE


def test_unsupported_format(tmp_path):
    path = tmp_path / "resume.png"
    path.write_bytes(b"not an image")
    with pytest.raises(IngestError) as error:
        ingest_file(path)
    assert error.value.code == "ingest.unsupported_format"


def test_text_has_no_layout(tmp_path):
    path = tmp_path / "resume.txt"
    path.write_text(
        "Li Ming\nliming@example.com\n\nEducation\nExample University, B.Eng. in Computer Science, 2023-09 - 2027-06\n\n"
        "Skills\nJava, Python, SQL\n",
        encoding="utf-8",
    )
    result = ingest_file(path)
    assert result.format == "txt"
    assert result.layout.page_size is None
    assert any("layout" in warning.lower() for warning in result.warnings)


def test_bad_html_is_replace(tmp_path):
    path = write_html(tmp_path / "bad.html", BAD_HTML)
    result = ingest_file(path)
    audit = audit_template(result, market="intl_en", persona="experienced")
    assert audit.verdict == VERDICT_REPLACE
    hard = {d.id for d in audit.hard_fails}
    assert {"structure", "typography", "layout", "market_fit", "print_safety"} <= hard
    assert not audit.keep_allowed


def test_two_column_html_is_detected(tmp_path):
    path = write_html(tmp_path / "two.html", TWO_COLUMN_HTML)
    result = ingest_file(path)
    assert result.layout.columns == 2
    audit = audit_template(result, market="intl_en", persona="experienced")
    assert audit.verdict in {"good_with_fixes", "replace"}
    assert audit.metrics["columns"] == 2


def test_to_vault_builds_evidence_and_needs(tmp_path):
    path = write_html(tmp_path / "resume.html")
    result = ingest_file(path)
    fragment, needs = to_vault(result)
    assert fragment["status"] == "collecting"
    assert fragment["identity"]["full_name"] == "Li Ming"
    assert fragment["education"][0]["id"] == "edu_001"
    assert fragment["experience"][0]["id"] == "exp_001"
    assert len(fragment["experience"][0]["bullets"]) == 2
    for bullet in fragment["experience"][0]["bullets"]:
        evidence_id = bullet["evidence"][0]
        assert evidence_id in fragment["evidence"]
        assert fragment["evidence"][evidence_id]["source"] == "document"
    assert "projects[0].context" in needs
    assert any(item["path"] == "projects[0].context" for item in fragment["needs_confirmation"])


def test_detect_lang():
    assert detect_lang("计算机科学与技术专业，负责后端开发与检索优化。") == "zh"
    assert detect_lang("Computer science student with backend experience.") == "en"


def test_multiline_education_is_one_entry(tmp_path):
    content = """<html><body>
<h1>Li Ming</h1>
<p>liming@example.com</p>
<h2>Education</h2>
<p>Example University</p>
<p>B.Eng. in Computer Science</p>
<p>2023-09 - 2027-06</p>
<h2>Experience</h2>
<p>Acme Cloud | Backend Intern | 2026-06 - 2026-09</p>
<p>Cut P95 latency from 480ms to 190ms for 300K daily requests.</p>
<h2>Skills</h2>
<p>Java, Python, SQL</p>
</body></html>"""
    path = write_html(tmp_path / "multi.html", content)
    result = ingest_file(path)
    assert len(result.fields["education"]) == 1
    entry = result.fields["education"][0]
    assert entry["school"] == "Example University"
    assert entry["degree"] == "B.Eng"
    assert entry["major"] == "Computer Science"
