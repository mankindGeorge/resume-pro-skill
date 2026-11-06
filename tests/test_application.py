# SPDX-License-Identifier: MIT
"""Application model, page budgets, slugs, and framework consent."""

from __future__ import annotations

import copy

import pytest

from resume_pro.application import (
    ApplicationError,
    create_application,
    default_template,
    load_application,
    page_budget,
    save_application,
    slugify,
    validate_application,
)
from resume_pro.select import select_facts
from resume_pro.writing import FRAMEWORK_IDS, WritingError, get_framework, require_consent


def _application(vault, role="Backend Engineer"):
    budget = page_budget("cn_internet", "student_with_internship")
    selection = select_facts(
        vault,
        market="cn_internet",
        persona="student_with_internship",
        target_role=role,
        page_max=budget["max"],
    )
    return create_application(
        vault=vault,
        selection=selection,
        role=role,
        market="cn_internet",
        persona="student_with_internship",
        framework="result_first",
        company="Example Co",
    )


def test_create_and_roundtrip_application(student_vault, tmp_path):
    application = _application(student_vault)
    assert validate_application(application).ok
    path = save_application(tmp_path, application)
    assert path.is_file()
    loaded = load_application(tmp_path, application["slug"])
    assert loaded["target"]["role"] == "Backend Engineer"
    assert loaded["writing"]["framework"] == "result_first"
    assert loaded["writing"]["consent"] is True
    assert loaded["output"]["html"] == "resume-backend-engineer.html"
    assert loaded["output"]["editable_html"] == "resume-backend-engineer-editable.html"
    assert loaded["output"]["draft"] is False


def test_page_budget_by_market():
    assert page_budget("cn_internet", "student_with_internship")["max"] == 2
    assert page_budget("cn_internet", "experienced")["max"] == 3
    assert page_budget("intl_en", "experienced")["max"] == 1
    assert page_budget("intl_en", "senior_manager")["max"] == 2
    assert page_budget("intl_en", "experienced")["size"] == "a4"
    assert page_budget("cn_internet", "experienced")["size"] == "a4"


def test_default_templates():
    assert default_template("cn_internet", "student_with_internship") == "campus"
    assert default_template("intl_en", "senior_manager") == "executive"
    assert default_template("intl_en", "experienced") == "ats-classic"
    assert default_template("cn_internet", "experienced") == "modern-sidebar"
    assert default_template("cn_internet", "senior_manager") == "modern-sidebar"


def test_slug_for_non_ascii_role_is_unique():
    slug = slugify("后端开发工程师（校招）")
    assert slug.startswith("application-")
    assert len(slug) <= 60
    assert slugify("Backend Engineer") == "backend-engineer"


def test_framework_consent_is_required():
    assert get_framework("star").label == "STAR"
    with pytest.raises(WritingError) as error:
        require_consent(None, True)
    assert error.value.code == "writing.framework_missing"
    with pytest.raises(WritingError) as error:
        require_consent("xyz", False)
    assert error.value.code == "writing.consent_missing"
    with pytest.raises(WritingError):
        get_framework("unknown")
    assert "star" in FRAMEWORK_IDS


def test_invalid_page_budget_is_rejected(student_vault):
    application = _application(student_vault)
    application["page_budget"]["target"] = 4
    application["page_budget"]["max"] = 2
    result = validate_application(application)
    assert not result.ok
    assert any(issue.code == "application.page_budget" for issue in result.errors)


def test_mass_application_uses_plain_filename(student_vault):
    vault = copy.deepcopy(student_vault)
    vault.setdefault("preferences", {})["application_mode"] = "mass"
    budget = page_budget("cn_internet", "student_with_internship")
    selection = select_facts(vault, market="cn_internet", persona="student_with_internship", page_max=budget["max"])
    application = create_application(
        vault=vault,
        selection=selection,
        role="Backend Engineer",
        market="cn_internet",
        persona="student_with_internship",
        framework="result_first",
    )
    assert application["output"]["html"] == "resume.html"
    assert application["output"]["editable_html"] == "resume-editable.html"


def test_role_can_be_excluded_from_filename(student_vault):
    budget = page_budget("cn_internet", "student_with_internship")
    selection = select_facts(student_vault, market="cn_internet", persona="student_with_internship", page_max=budget["max"])
    application = create_application(
        vault=student_vault,
        selection=selection,
        role="Backend Engineer",
        market="cn_internet",
        persona="student_with_internship",
        framework="result_first",
        role_in_filename=False,
    )
    assert application["output"]["html"] == "resume.html"


def test_unknown_template_is_rejected(student_vault):
    budget = page_budget("cn_internet", "student_with_internship")
    selection = select_facts(student_vault, market="cn_internet", persona="student_with_internship", page_max=2)
    with pytest.raises(ApplicationError):
        create_application(
            vault=student_vault,
            selection=selection,
            role="Backend Engineer",
            market="cn_internet",
            persona="student_with_internship",
            framework="result_first",
            template_id="not-a-template",
        )
