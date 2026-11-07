# SPDX-License-Identifier: MIT
"""Guided intake engine tests."""

from __future__ import annotations

import pytest

from resume_pro.errors import IntakeError
from resume_pro.intake import (
    IntakeEngine,
    load_session,
    new_session,
    parse_answer,
    save_session,
    summary,
)
from resume_pro.sufficiency import evaluate
from resume_pro.vault import empty_vault, validate_vault

FULL_ANSWERS = {
    "target.market": "cn_internet",
    "target.persona": "student_with_internship",
    "preferences.application_mode": "no",
    "target.role": "Backend Engineer (new grad)",
    "identity.full_name": "Li Ming",
    "identity.email": "liming@example.com",
    "identity.city": "Hangzhou",
    "education.0.school": "Example University",
    "education.0.degree": "B.Eng.",
    "education.0.major": "Computer Science",
    "education.0.start": "2023-09",
    "education.0.end": "2027-06",
    "education.0.gpa": "3.7/4.0",
    "education.0.coursework": "Operating Systems, Networks, Data Structures, Databases",
    "education.more": "no",
    "experience.has": "yes",
    "experience.0.company": "Acme Cloud",
    "experience.0.title": "Backend Intern",
    "experience.0.start": "2026-06",
    "experience.0.end": "2026-09",
    "experience.0.type": "internship",
    "experience.0.bullet.0": "Cut P95 latency from 480ms to 190ms across 300K daily requests.",
    "experience.0.bullet.1": "Shipped bulk export, saving 6 hours per week.",
    "experience.0.roles": "backend, platform",
    "experience.more": "no",
    "projects.has": "yes",
    "projects.0.name": "Course QA with RAG",
    "projects.0.context": "course",
    "projects.0.role": "Retrieval lead",
    "projects.0.tech": "Python, BM25, FAISS",
    "projects.0.own_contribution": "Owned retrieval and evaluation for the course QA tool.",
    "projects.0.optimization": "Replaced fixed chunking with heading-aware chunking.",
    "projects.0.outcome": "Raised Recall@5 from 62% to 81% on 120 questions.",
    "projects.0.link": "https://github.com/example/course-qa",
    "projects.0.roles": "backend, ai",
    "projects.more": "no",
    "skills.languages": "Java, Python, SQL",
    "skills.frameworks": "Spring Boot",
    "skills.cs_fundamentals": "Operating Systems, Computer Networks, Data Structures, Algorithms, Databases",
    "skills.ai": "RAG, FAISS",
    "skills.tools": "Git",
    "preferences.preferred_role": "Backend Engineer",
    "preferences.locations": "Hangzhou",
    "preferences.remote": "no",
    "confirm.summary": "yes",
}


def _engine_with_target(market="cn_internet", persona="student_with_internship"):
    vault = empty_vault()
    session = new_session()
    engine = IntakeEngine(vault, session)
    engine.answer(engine.current(), market)
    engine.answer(engine.current(), persona)
    return vault, session, engine


def _drive_full(skip_optional=True):
    vault = empty_vault()
    session = new_session()
    engine = IntakeEngine(vault, session)
    for _ in range(200):
        question = engine.current()
        if question is None:
            break
        if question.id in FULL_ANSWERS:
            engine.answer(question, FULL_ANSWERS[question.id])
        elif question.optional and skip_optional:
            engine.skip(question)
        else:
            raise AssertionError(f"missing answer for required question {question.id}")
    return vault, session, engine


def test_question_order_starts_with_application_mode():
    _, _, engine = _engine_with_target()
    assert engine.current().id == "preferences.application_mode"


def test_branching_no_experience_skips_group():
    vault, session, engine = _engine_with_target(market="cn_internet", persona="student_with_projects")
    engine.answer(engine.current(), "no")  # targeted, not mass
    engine.answer(engine.current(), "Backend Engineer")
    engine.skip(engine.current())  # target.company
    engine.answer(engine.current(), "Zhao Lin")
    engine.skip(engine.current())  # email
    engine.answer(engine.current(), "+86 137 0000 0000")
    engine.answer(engine.current(), "Wuhan")
    engine.skip(engine.current())  # links
    for answer in ("Example University", "B.Eng.", "Software Engineering", "2023-09", "2027-06"):
        engine.answer(engine.current(), answer)
    engine.skip(engine.current())  # gpa
    engine.skip(engine.current())  # coursework
    engine.answer(engine.current(), "no")  # education.more
    assert engine.current().id == "experience.has"
    engine.answer(engine.current(), "no")
    assert engine.current().id == "projects.has"


def test_skip_required_records_blocker():
    vault, session, engine = _engine_with_target()
    question = engine.current()
    engine.skip(question)
    assert question.id in session["skipped"]
    unresolved = [n for n in vault["needs_confirmation"] if not n.get("resolved")]
    assert unresolved
    assert unresolved[0]["severity"] == "blocker"


def test_fabrication_is_refused():
    _, _, engine = _engine_with_target()
    question = engine.current()
    with pytest.raises(IntakeError) as error:
        engine.answer(question, "just make something up")
    assert error.value.code == "intake.fabrication_refused"


def test_invalid_choice_is_rejected():
    vault = empty_vault()
    engine = IntakeEngine(vault, new_session())
    with pytest.raises(IntakeError) as error:
        engine.answer(engine.current(), "mars")
    assert error.value.code == "intake.invalid_choice"


def test_session_roundtrip(tmp_path):
    session = new_session(lang="zh")
    session["answered"].append("target.market")
    path = tmp_path / "session.json"
    save_session(session, path)
    loaded = load_session(path)
    assert loaded["lang"] == "zh"
    assert "target.market" in loaded["answered"]


def test_parse_date_normalizes():
    question = type("Q", (), {"kind": "date", "optional": False, "choices": (), "aliases": {}})()
    assert parse_answer(question, "2025.09") == "2025-09"
    assert parse_answer(question, "至今") == "present"
    with pytest.raises(IntakeError):
        parse_answer(question, "September 2025")


def test_full_intake_reaches_strong_gate():
    vault, session, engine = _drive_full()
    assert session["confirmed"] is True
    assert vault["status"] == "ready"
    assert not validate_vault(vault).errors
    assert len(vault["experience"][0]["bullets"]) == 2
    assert len(vault["projects"][0]["bullets"]) == 3
    assert all(b["id"].startswith("bul_proj_") for b in vault["projects"][0]["bullets"])
    assert vault["experience"][0]["target_roles"] == ["backend", "platform"]
    assert vault["projects"][0]["target_roles"] == ["backend", "ai"]
    assert vault["preferences"]["application_mode"] == "targeted"
    assert vault["preferences"]["preferred_role"] == "Backend Engineer"
    report = evaluate(vault, market="cn_internet", persona="student_with_internship", target_role=session["role"])
    assert report.status == "strong"


def test_reanswer_after_confirm_reopens_vault():
    vault, session, engine = _drive_full()
    question = engine.by_id("identity.full_name")
    engine.answer(question, "Li Ming Updated")
    assert vault["status"] == "collecting"
    assert session["confirmed"] is False
    assert "confirm.summary" not in session["answered"]
    assert vault["identity"]["full_name"] == "Li Ming Updated"


def test_summary_reports_counts():
    vault, session, _ = _drive_full()
    data = summary(vault, session)
    assert data["counts"]["experience"] == 1
    assert data["counts"]["projects"] == 1
    assert data["counts"]["bullets"] == 5
    assert data["target"]["market"] == "cn_internet"


def _drive_to_confirm():
    vault = empty_vault()
    session = new_session()
    engine = IntakeEngine(vault, session)
    for _ in range(200):
        question = engine.current()
        if question is None:
            break
        if question.id == "confirm.summary":
            break
        if question.id in FULL_ANSWERS:
            engine.answer(question, FULL_ANSWERS[question.id])
        elif question.optional:
            engine.skip(question)
        else:
            raise AssertionError(f"missing answer for required question {question.id}")
    assert engine.current().id == "confirm.summary"
    return vault, session, engine


def test_second_decline_keeps_confirmation_reachable():
    vault, session, engine = _drive_to_confirm()
    engine.answer(engine.current(), "no")
    assert engine.current().id == "confirm.note"
    engine.answer(engine.current(), "The name is wrong.")
    assert engine.current().id == "confirm.summary"

    engine.answer(engine.current(), "no")  # second decline must not deadlock
    nxt = engine.current()
    assert nxt is not None, "second decline left no question while unconfirmed"
    assert session["confirmed"] is False
    assert session["completed"] is False
    assert nxt.id == "confirm.note"

    engine.answer(nxt, "Actually keep the name.")
    assert engine.current().id == "confirm.summary"
    engine.answer(engine.current(), "yes")
    assert session["confirmed"] is True
    assert vault["status"] == "ready"
