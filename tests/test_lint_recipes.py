# SPDX-License-Identifier: MIT
"""Hard checks for framework packaging recipes, bullet length, and result data.

The recipes live in references/writing-engine.md §2. When an application
declares a writing framework, labeled points must use that recipe's label set
and order, result points must carry a number, and per-locale bullet length
limits (EN 240 / ZH 140) are errors, not warnings.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from resume_pro.cli import cli
from resume_pro.lint import lint
from resume_pro.vault import save_vault
from tests.conftest import load_example

FRAMEWORK_CODES = {"lint.framework_label", "lint.framework_order", "lint.result_no_data"}


def _app(framework: str | None = "result_first", *, locale: str = "zh", bullet_ids: list[str] | None = None):
    selection: dict = {"sections": [], "fact_ids": []}
    if bullet_ids is not None:
        selection["bullet_ids"] = bullet_ids
    writing: dict = {"consent": True, "locale": locale}
    if framework is not None:
        writing["framework"] = framework
    return {
        "market": "cn_internet" if locale == "zh" else "intl_en",
        "page_budget": {"size": "a4", "target": 2, "max": 2},
        "selection": selection,
        "writing": writing,
    }


def _vault(texts: list[dict], *, collection: str = "projects") -> dict:
    bullets = [
        {"id": f"bul_{collection[:4]}_{index:03d}", "text": text, "evidence": ["ev_proj"]}
        for index, text in enumerate(texts)
    ]
    item = {
        "id": f"{collection[:4]}_001",
        "name": "Course QA with RAG",
        "context": "course",
        "own_contribution": {"zh": "负责检索链路和评估。"},
        "bullets": bullets,
    }
    vault = {
        "identity": {"full_name": "Li Ming"},
        "education": [{"id": "edu_001", "school": "Example University"}],
        "experience": [],
        "projects": [],
        "skills": [],
        "evidence": {"ev_proj": {"status": "verified"}},
    }
    vault[collection] = [item]
    return vault


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def _lint(vault, application):
    locale = (application or {}).get("writing", {}).get("locale", "zh")
    return lint(
        vault,
        market="cn_internet" if locale == "zh" else "intl_en",
        persona="student_with_internship",
        application=application,
    )


RESULT_FIRST_ZH = [
    {"zh": "核心成果：在 120 条回归问题上把 Recall@5 从 62% 提升到 81%。"},
    {"zh": "解决方案：按标题层级分块并调整混合检索权重，解决上下文断裂的痛点。"},
    {"zh": "项目背景：课程资料分散在 1200 份 PDF 和讲义里，找答案要翻很久。"},
]

STAR_ZH = [
    {"zh": "项目背景：课程资料分散在 1200 份 PDF 和讲义里，找答案要翻很久。"},
    {"zh": "核心框架：选用 BM25 与向量混合检索，兼顾关键词命中和语义召回。"},
    {"zh": "解决方案：按标题层级分块并调权重，解决上下文断裂的痛点。"},
    {"zh": "核心成果：在 120 条回归问题上把 Recall@5 从 62% 提升到 81%。"},
]


def test_result_first_rejects_star_order_and_mixed_labels():
    """The real drift: result_first declared, STAR order plus an off-recipe label."""
    drift = [
        STAR_ZH[0],
        {"zh": "核心框架与解决方案：采用 BM25 混合检索，搭了 120 条人工标注回归集。"},
        STAR_ZH[3],
    ]
    report = _lint(_vault(drift), _app("result_first"))
    errors = {issue.code for issue in report.errors}
    assert "lint.framework_label" in errors
    assert "lint.framework_order" in errors
    assert not report.ok


def test_result_first_accepts_recipe_order():
    report = _lint(_vault(RESULT_FIRST_ZH), _app("result_first"))
    assert not (_codes(report) & FRAMEWORK_CODES)


def test_star_recipe_labels_and_order():
    report = _lint(_vault(STAR_ZH), _app("star"))
    assert not (_codes(report) & FRAMEWORK_CODES)
    reversed_report = _lint(_vault(list(reversed(STAR_ZH))), _app("star"))
    assert "lint.framework_order" in {issue.code for issue in reversed_report.errors}


def test_star_allows_challenge_label_for_the_action_slot():
    texts = [STAR_ZH[0], STAR_ZH[1], {"zh": "难点：分块策略断裂上下文，改用标题层级分块并回归验证。"}, STAR_ZH[3]]
    report = _lint(_vault(texts), _app("star"))
    assert not (_codes(report) & FRAMEWORK_CODES)


def test_xyz_recipe_and_result_data():
    texts = [
        {"zh": "核心成果：把 Recall@5 从 62% 提升到 81%。"},
        {"zh": "衡量口径：120 条人工标注问题的回归集。"},
        {"zh": "实现做法：标题感知分块加 BM25 混合检索。"},
    ]
    report = _lint(_vault(texts), _app("xyz"))
    assert not (_codes(report) & FRAMEWORK_CODES)
    texts[0] = {"zh": "核心成果：检索质量明显提升，同学找答案更快了。"}
    report = _lint(_vault(texts), _app("xyz"))
    assert "lint.result_no_data" in {issue.code for issue in report.errors}


def test_fab_recipe_benefit_is_the_result_point():
    texts = [
        {"zh": "核心能力：课程问答检索服务，覆盖 1200 份资料。"},
        {"zh": "技术优势：混合检索比纯向量召回更稳，评估集可复验。"},
        {"zh": "实际收益：同学找答案的时间缩短了一半。"},
    ]
    report = _lint(_vault(texts), _app("fab"))
    assert "lint.result_no_data" in {issue.code for issue in report.errors}
    texts[2] = {"zh": "实际收益：找答案时间从 10 分钟降到 2 分钟。"}
    report = _lint(_vault(texts), _app("fab"))
    assert not (_codes(report) & FRAMEWORK_CODES)


def test_car_recipe():
    texts = [
        {"zh": "难点：1200 份资料分散，关键词检索召回不稳。"},
        {"zh": "解决方案：标题感知分块加混合排序，用回归集调权重。"},
        {"zh": "核心成果：Recall@5 从 62% 提升到 81%。"},
    ]
    report = _lint(_vault(texts), _app("car"))
    assert not (_codes(report) & FRAMEWORK_CODES)


def test_english_labels_follow_the_same_recipes():
    texts = [
        {"en": "Outcome: Raised Recall@5 from 62% to 81% on 120 labeled questions."},
        {"en": "Solution: Heading-aware chunking plus hybrid ranking fixed broken context."},
        {"en": "Background: Course material was spread across 1,200 PDFs and handouts."},
    ]
    report = _lint(_vault(texts), _app("result_first", locale="en"))
    assert not (_codes(report) & FRAMEWORK_CODES)
    zh_report = _lint(_vault(RESULT_FIRST_ZH), _app("result_first", locale="en"))
    assert "lint.framework_label" in {issue.code for issue in zh_report.errors}


def test_user_voice_keeps_custom_labels_but_not_empty_points():
    texts = [{"zh": "我的打法：先把评估集搭起来，再调检索权重，Recall@5 从 62% 到 81%。"}]
    report = _lint(_vault(texts), _app("user_voice"))
    assert not (_codes(report) & FRAMEWORK_CODES)
    bare = _lint(_vault([{"zh": "我的打法："}]), _app("user_voice"))
    assert "lint.framework_label" in {issue.code for issue in bare.errors}


def test_bare_recipe_label_is_an_error():
    texts = [RESULT_FIRST_ZH[0], {"zh": "解决方案："}, RESULT_FIRST_ZH[2]]
    report = _lint(_vault(texts), _app("result_first"))
    assert "lint.framework_label" in {issue.code for issue in report.errors}


def test_no_framework_declaration_skips_label_checks():
    drift = [{"zh": "随便什么标签：内容里有个 1 数字。"}]
    for application in (_app(framework=None), None):
        report = _lint(_vault(drift), application)
        assert not (_codes(report) & FRAMEWORK_CODES), application


def test_only_selected_bullets_are_checked():
    texts = [{"zh": "杂项标签：不在选择里的分点 1。"}, RESULT_FIRST_ZH[0], RESULT_FIRST_ZH[1]]
    vault = _vault(texts)
    kept = ["bul_proj_001", "bul_proj_002"]
    report = _lint(vault, _app("result_first", bullet_ids=kept))
    assert not (_codes(report) & FRAMEWORK_CODES)
    report = _lint(vault, _app("result_first", bullet_ids=["bul_proj_000", *kept]))
    assert "lint.framework_label" in {issue.code for issue in report.errors}


def test_order_follows_the_selection_order_not_vault_order():
    texts = [RESULT_FIRST_ZH[2], RESULT_FIRST_ZH[0]]  # background first in the vault
    vault = _vault(texts)
    good = _lint(vault, _app("result_first", bullet_ids=["bul_proj_001", "bul_proj_000"]))
    assert not (_codes(good) & FRAMEWORK_CODES)
    bad = _lint(vault, _app("result_first", bullet_ids=["bul_proj_000", "bul_proj_001"]))
    assert "lint.framework_order" in {issue.code for issue in bad.errors}


def test_result_point_requires_a_number_but_action_points_do_not():
    texts = [
        {"zh": "核心成果：检索质量明显提升，同学反馈更好。"},
        {"zh": "解决方案：按标题层级分块并调整混合检索权重。"},
    ]
    report = _lint(_vault(texts), _app("result_first"))
    codes = {issue.code for issue in report.errors}
    assert "lint.result_no_data" in codes
    assert sum(issue.code == "lint.result_no_data" for issue in report.errors) == 1


def test_experience_points_are_checked_too():
    texts = [{"zh": "项目背景：订单查询接口很慢。"}, {"zh": "核心成果：P95 从 480ms 降到 190ms。"}]
    report = _lint(_vault(texts, collection="experience"), _app("result_first"))
    assert "lint.framework_order" in {issue.code for issue in report.errors}


def test_zh_bullet_over_140_characters_is_an_error():
    vault = _vault([{"zh": "甲" * 141}])
    report = _lint(vault, _app("result_first"))
    issues = [issue for issue in report.errors if issue.code == "lint.bullet_too_long"]
    assert issues and issues[0].fix


def test_zh_bullet_at_140_characters_is_allowed():
    report = _lint(_vault([{"zh": "甲" * 140}]), _app("result_first"))
    assert "lint.bullet_too_long" not in _codes(report)


def test_en_bullet_over_240_characters_is_an_error():
    vault = _vault([{"en": "a" * 241}])
    report = _lint(vault, _app("result_first", locale="en"))
    assert "lint.bullet_too_long" in {issue.code for issue in report.errors}


def test_en_bullet_at_240_characters_is_allowed():
    report = _lint(_vault([{"en": "a" * 240}]), _app("result_first", locale="en"))
    assert "lint.bullet_too_long" not in _codes(report)


def test_bilingual_bullet_is_measured_per_locale():
    text = {"zh": "乙" * 100, "en": "b" * 200}
    report = _lint(_vault([text]), _app("result_first"))
    assert "lint.bullet_too_long" not in _codes(report)


def test_length_limit_applies_without_an_application():
    report = lint(_vault([{"zh": "丙" * 141}]), market="cn_internet", persona="student_with_internship")
    assert "lint.bullet_too_long" in {issue.code for issue in report.errors}


def _drift_cli_setup(tmp_path, monkeypatch, texts):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--market", "cn_internet", "--persona", "student_with_internship"]).exit_code == 0
    vault = load_example("vault-student.yaml")
    vault["projects"][0]["bullets"] = [
        {"id": f"bul_proj_drift_{index}", "text": text, "evidence": ["ev_proj_eval"], "skill_ids": ["skl_ai"]}
        for index, text in enumerate(texts)
    ]
    save_vault(vault, root=tmp_path, validate=False)
    created = runner.invoke(
        cli,
        ["new", "--role", "Backend Engineer", "--market", "cn_internet", "--persona", "student_with_internship", "--framework", "result_first", "--json"],
    )
    assert created.exit_code == 0, created.output
    slug = json.loads(created.output)["slug"]
    app_path = tmp_path / ".resume" / "applications" / slug / "application.yaml"
    application = yaml.safe_load(app_path.read_text(encoding="utf-8"))
    application["selection"]["bullet_ids"] = [f"bul_proj_drift_{index}" for index in range(len(texts))]
    app_path.write_text(yaml.safe_dump(application, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return runner, slug


def test_cli_lint_exits_4_on_framework_drift(tmp_path, monkeypatch):
    drift = [
        STAR_ZH[0],
        {"zh": "核心框架与解决方案：采用 BM25 混合检索，搭了 120 条人工标注回归集。"},
        STAR_ZH[3],
    ]
    runner, slug = _drift_cli_setup(tmp_path, monkeypatch, drift)
    result = runner.invoke(cli, ["lint", "--app", slug, "--json"])
    assert result.exit_code == 4, result.output
    codes = {issue["code"] for issue in json.loads(result.output)["lint"]["errors"]}
    assert {"lint.framework_label", "lint.framework_order"} <= codes


def test_cli_build_exits_4_on_framework_drift(tmp_path, monkeypatch):
    drift = [STAR_ZH[0], STAR_ZH[3]]
    runner, slug = _drift_cli_setup(tmp_path, monkeypatch, drift)
    result = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert result.exit_code == 4, result.output
    payload = json.loads(result.output)
    codes = {issue["code"] for issue in payload["lint"]["errors"]}
    assert "lint.framework_order" in codes


def test_cli_lint_passes_with_recipe_points(tmp_path, monkeypatch):
    runner, slug = _drift_cli_setup(tmp_path, monkeypatch, RESULT_FIRST_ZH)
    result = runner.invoke(cli, ["lint", "--app", slug, "--json"])
    assert result.exit_code == 0, result.output
    built = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert built.exit_code == 0, built.output