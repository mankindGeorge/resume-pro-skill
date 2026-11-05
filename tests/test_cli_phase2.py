# SPDX-License-Identifier: MIT
"""CLI tests for Phase 2: new, lint, match, tailor, and recommend."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from resume_pro.cli import cli
from resume_pro.paths import vault_path
from tests.ingest_fixtures import BAD_HTML, write_docx, write_html

JD = """# Backend Engineer (New Grad)

Requirements
- Must have Java or Python experience
- Experience with MySQL and Redis
- Familiar with distributed systems

Preferred
- Experience with RAG or LLM applications
"""


def _setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_docx(tmp_path / "resume.docx")
    (tmp_path / "jd.md").write_text(JD, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "optimize",
            "resume.docx",
            "--market",
            "cn_internet",
            "--persona",
            "student_with_internship",
            "--role",
            "Backend Engineer",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    return runner


def test_new_creates_application_without_rendering(tmp_path, monkeypatch):
    runner = _setup(tmp_path, monkeypatch)
    result = runner.invoke(
        cli,
        [
            "new",
            "--role",
            "Backend Engineer",
            "--market",
            "cn_internet",
            "--persona",
            "student_with_internship",
            "--framework",
            "result_first",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    app_dir = tmp_path / ".resume" / "applications" / payload["slug"]
    assert (app_dir / "application.yaml").is_file()
    assert not list(app_dir.glob("*.pdf"))
    assert not list(app_dir.glob("*.docx"))
    assert not list(app_dir.glob("*.html"))


def test_new_requires_framework(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["new", "--role", "Backend Engineer", "--market", "cn_internet", "--persona", "student_with_internship"],
    )
    assert result.exit_code == 2


def test_lint_match_tailor_and_recommend(tmp_path, monkeypatch):
    runner = _setup(tmp_path, monkeypatch)
    created = runner.invoke(
        cli,
        [
            "new",
            "--role",
            "Backend Engineer",
            "--market",
            "cn_internet",
            "--persona",
            "student_with_internship",
            "--framework",
            "result_first",
            "--json",
        ],
    )
    slug = json.loads(created.output)["slug"]

    linted = runner.invoke(cli, ["lint", "--app", slug, "--json"])
    assert linted.exit_code == 0, linted.output
    assert "lint" in json.loads(linted.output)

    matched = runner.invoke(cli, ["match", "--app", slug, "--jd", "jd.md", "--json"])
    assert matched.exit_code == 0, matched.output
    match_payload = json.loads(matched.output)
    assert match_payload["match"]["score_range"][1] - match_payload["match"]["score_range"][0] == 10

    tailored = runner.invoke(
        cli,
        ["tailor", "--app", slug, "--jd", "jd.md", "--framework", "result_first", "--json"],
    )
    assert tailored.exit_code == 0, tailored.output
    tailored_payload = json.loads(tailored.output)
    assert tailored_payload["match_report"].endswith("match.json")

    recommended = runner.invoke(cli, ["recommend", "--app", slug, "--json"])
    assert recommended.exit_code == 0, recommended.output
    assert json.loads(recommended.output)["recommendation"]["families"]


def test_tailor_requires_framework_consent(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "tailor",
            "--jd",
            "jd.md",
            "--market",
            "cn_internet",
            "--persona",
            "student_with_internship",
            "--role",
            "Backend Engineer",
            "--json",
        ],
    )
    assert result.exit_code == 3
    assert json.loads(result.output)["error"]["code"] == "writing.framework_missing"


def test_lint_errors_exit_4(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "bad.html", BAD_HTML)
    runner = CliRunner()
    optimized = runner.invoke(
        cli,
        ["optimize", "bad.html", "--market", "intl_en", "--persona", "experienced", "--json"],
    )
    assert optimized.exit_code == 0, optimized.output
    result = runner.invoke(cli, ["lint", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert result.exit_code == 4
    payload = json.loads(result.output)
    assert payload["lint"]["errors"]
    apps = tmp_path / ".resume" / "applications"
    if apps.exists():
        assert not list(apps.rglob("*.pdf"))


def test_tailor_from_file_creates_application(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_docx(tmp_path / "resume.docx")
    (tmp_path / "jd.md").write_text(JD, encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(cli, ["init"]).exit_code == 0
    result = runner.invoke(
        cli,
        [
            "tailor",
            "resume.docx",
            "--jd",
            "jd.md",
            "--market",
            "cn_internet",
            "--persona",
            "student_with_internship",
            "--role",
            "Backend Engineer",
            "--framework",
            "result_first",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    app_dir = tmp_path / ".resume" / "applications" / payload["slug"]
    assert (app_dir / "application.yaml").is_file()
    assert (app_dir / "match.json").is_file()
    assert vault_path(tmp_path).is_file()
    assert not list(app_dir.glob("*.pdf"))
    assert not list(app_dir.glob("*.docx"))
