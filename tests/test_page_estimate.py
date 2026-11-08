# SPDX-License-Identifier: MIT
"""Lint and layout must agree on page count: one estimator, owned by layout.

lint used to estimate the whole vault with its own coefficients while layout
estimated the selected render model, so `resume lint`/`resume build` could fail
with a page_count error for content that renders within the page budget.
"""

from __future__ import annotations

import copy

import pytest

from resume_pro.application import create_application, page_budget
from resume_pro.layout import check_layout
from resume_pro.lint import lint
from resume_pro.render import build_render_model, load_template
from resume_pro.select import select_facts


def _application(vault, market, persona, role):
    budget = page_budget(market, persona)
    selection = select_facts(vault, market=market, persona=persona, target_role=role, page_max=budget["max"])
    return create_application(
        vault=vault,
        selection=selection,
        role=role,
        market=market,
        persona=persona,
        framework="result_first",
    )


def _layout_pages(vault, application):
    model = build_render_model(vault, application)
    template = load_template(application["template"]["id"], language=application["writing"]["locale"])
    return check_layout(model, template["manifest"], application).pages


def test_lint_does_not_overcount_dropped_roles(experienced_vault):
    """Roles dropped by selection must not push lint over the page budget."""
    vault = copy.deepcopy(experienced_vault)
    for index in range(3):
        extra = copy.deepcopy(vault["experience"][1])
        extra["id"] = f"exp_old_{index}"
        extra["company"] = f"Old Co {index}"
        extra["start"] = "2012-01"
        extra["end"] = "2015-01"
        for b_index, bullet in enumerate(extra["bullets"]):
            bullet["id"] = f"bul_old_{index}_{b_index}"
        vault["experience"].append(extra)
    application = _application(vault, "intl_en", "experienced", "Senior Backend Engineer")
    kept = [fact_id for fact_id in application["selection"]["fact_ids"] if fact_id.startswith("exp_")]
    assert kept == ["exp_001", "exp_002"]  # the older roles are dropped by the budget

    report = lint(vault, market="intl_en", persona="experienced", application=application)
    assert report.page_estimate == _layout_pages(vault, application) == 1
    assert not any(issue.code == "lint.page_count" for issue in report.errors)


@pytest.mark.parametrize(
    "fixture_name,market,persona,role",
    [
        ("student_vault", "cn_internet", "student_with_internship", "Backend Engineer"),
        ("student_vault", "intl_en", "student_with_internship", "Backend Engineer"),
        ("student_projects_vault", "intl_en", "student_with_projects", "Backend Engineer"),
        ("experienced_vault", "intl_en", "experienced", "Senior Backend Engineer"),
        ("experienced_vault", "cn_internet", "experienced", "高级后端工程师"),
    ],
)
def test_lint_and_layout_estimate_the_same_pages(request, fixture_name, market, persona, role):
    vault = request.getfixturevalue(fixture_name)
    application = _application(vault, market, persona, role)
    report = lint(vault, market=market, persona=persona, application=application)
    assert report.page_estimate == _layout_pages(vault, application)