# SPDX-License-Identifier: MIT
"""JD parsing, match scoring, gaps, and risks."""

from __future__ import annotations

import copy

from resume_pro.match import GATE, MUST, NICE, match_vault, parse_jd

JD = """# Backend Engineer (New Grad)

Requirements
- Must have Java or Python experience
- Experience with MySQL and Redis
- Familiar with distributed systems
- Must be authorized to work in China

Preferred
- Experience with RAG or LLM applications
- Open-source contributions

Responsibilities
- Build backend services and APIs
"""


def test_parse_jd_kinds_and_keywords():
    requirements, keywords, signals, title, location, _ = parse_jd(JD)
    kinds = [r.kind for r in requirements]
    assert kinds.count(MUST) == 3
    assert kinds.count(NICE) == 2
    assert kinds.count(GATE) == 1
    assert "java" in keywords and "python" in keywords
    assert title is not None


def test_match_is_reproducible(student_vault):
    first = match_vault(student_vault, JD, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    second = match_vault(student_vault, JD, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert first.to_dict() == second.to_dict()
    assert first.score_range[1] - first.score_range[0] == 10
    assert first.score_range[0] <= first.score <= first.score_range[1]


def test_authorization_risk_not_gate_cap(student_vault):
    report = match_vault(student_vault, JD, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert report.gate_missing is False
    assert any(risk["type"] == "authorization" for risk in report.risks)


def test_work_authorization_removes_risk(student_vault):
    vault = copy.deepcopy(student_vault)
    vault.setdefault("preferences", {})["work_authorization"] = "CN citizen"
    report = match_vault(vault, JD, market="cn_internet", persona="student_with_internship", target_role="Backend Engineer")
    assert not any(risk["type"] == "authorization" for risk in report.risks)


def test_credential_gate_caps_score(student_vault):
    jd = """Requirements
- Must have a CPA license
- Must have 5+ years of audit experience
"""
    report = match_vault(student_vault, jd, market="cn_internet", persona="student_with_internship")
    assert report.gate_missing is True
    assert report.score <= 30


def test_hard_and_fixable_gaps(student_vault):
    jd = """Requirements
- Must have 5+ years of Kubernetes experience
- Must have Terraform experience
"""
    report = match_vault(student_vault, jd, market="intl_en", persona="student_with_internship")
    classes = {gap.classification for gap in report.gaps}
    assert "hard" in classes
    assert "fixable" in classes


def test_hidden_signal_fit(student_vault):
    jd = """Requirements
- Own the backend roadmap and drive cross-functional alignment in a fast-paced environment
"""
    report = match_vault(student_vault, jd, market="intl_en", persona="student_with_internship")
    assert report.hidden_signals
    assert any(value > 0 for value in report.hidden_signals.values())


def test_missing_two_must_has_a_cap():
    vault = {
        "identity": {"full_name": "A", "email": "a@example.com"},
        "education": [{"id": "edu_001", "school": "X", "degree": {"en": "BSc"}, "start": "2020-01"}],
        "experience": [],
        "projects": [],
        "skills": [],
        "evidence": {},
    }
    jd = """Requirements
- Must have COBOL experience
- Must have mainframe experience
"""
    report = match_vault(vault, jd, market="intl_en", persona="experienced")
    assert report.score <= 55
