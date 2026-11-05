# SPDX-License-Identifier: MIT
"""Seven-dimension template audit tests."""

from __future__ import annotations

from resume_pro.ingest import ingest_file
from resume_pro.template_audit import (
    VERDICT_EXCELLENT,
    VERDICT_GOOD,
    VERDICT_REPLACE,
    VERDICT_UNMAINTAINABLE,
    audit_template,
    recommend_templates,
)
from tests.ingest_fixtures import (
    BAD_HTML,
    STRONG_HTML,
    write_docx,
    write_html,
    write_pdf,
    write_scanned_pdf,
)


def test_strong_html_is_excellent(tmp_path):
    result = ingest_file(write_html(tmp_path / "resume.html"))
    audit = audit_template(result, market="intl_en", persona="experienced")
    assert audit.verdict == VERDICT_EXCELLENT
    assert audit.keep_allowed
    assert not audit.hard_fails
    assert audit.metrics["visual_identity"] >= 2
    assert audit.recommendations == []


def test_strong_docx_is_keepable(tmp_path):
    result = ingest_file(write_docx(tmp_path / "resume.docx"))
    audit = audit_template(result, market="intl_en", persona="experienced")
    assert audit.keep_allowed
    assert audit.verdict in {VERDICT_EXCELLENT, VERDICT_GOOD}
    assert not audit.hard_fails


def test_strong_pdf_is_keepable(tmp_path):
    result = ingest_file(write_pdf(tmp_path / "resume.pdf"))
    audit = audit_template(result, market="intl_en", persona="experienced")
    assert audit.keep_allowed
    assert not audit.hard_fails
    assert audit.metrics["editable_source"] is False


def test_bad_html_is_replace(tmp_path):
    result = ingest_file(write_html(tmp_path / "bad.html", BAD_HTML))
    audit = audit_template(result, market="intl_en", persona="experienced")
    assert audit.verdict == VERDICT_REPLACE
    assert not audit.keep_allowed
    hard = {d.id for d in audit.hard_fails}
    assert {"structure", "typography", "layout", "market_fit", "print_safety"} <= hard
    assert audit.recommendations


def test_scanned_pdf_is_unmaintainable(tmp_path):
    result = ingest_file(write_scanned_pdf(tmp_path / "scan.pdf"))
    audit = audit_template(result, market="intl_en", persona="experienced")
    assert audit.verdict == VERDICT_UNMAINTAINABLE
    assert not audit.keep_allowed
    assert any(d.id == "parseability" and d.hard_fail for d in audit.dimensions)


def test_cn_campus_does_not_require_job_intent(tmp_path):
    result = ingest_file(write_html(tmp_path / "resume.html", STRONG_HTML))
    audit = audit_template(result, market="cn_internet", persona="student_with_internship")
    market = next(d for d in audit.dimensions if d.id == "market_fit")
    assert market.status == "pass"
    assert "求职意向" not in market.detail


def test_recommendations_by_market():
    assert recommend_templates("cn_internet", "student_with_internship", VERDICT_REPLACE)[0] == "campus"
    assert "executive" in recommend_templates("intl_en", "experienced", VERDICT_REPLACE)
