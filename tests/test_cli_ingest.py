# SPDX-License-Identifier: MIT
"""CLI tests for ingestion, audit, learning, and restyling."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from resume_pro.cli import cli
from resume_pro.paths import vault_path
from resume_pro.vault import load_vault
from tests.ingest_fixtures import BAD_HTML, write_docx, write_html, write_scanned_pdf


def _run(runner: CliRunner, args: list[str]):
    result = runner.invoke(cli, args)
    return result


def test_review_writes_report_without_vault(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "resume.html")
    runner = CliRunner()
    result = _run(runner, ["review", "resume.html", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert Path(payload["report"]).is_file()
    workspace = Path(payload["workspace"])
    assert workspace.parent == tmp_path / "workspace"
    assert (workspace / "review.json").is_file()
    assert not vault_path(tmp_path).exists()


def test_review_bad_template_exits_4(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "bad.html", BAD_HTML)
    runner = CliRunner()
    result = _run(runner, ["review", "bad.html", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert result.exit_code == 4
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["audit"]["verdict"] == "replace"


def test_review_requires_target(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "resume.html")
    runner = CliRunner()
    result = _run(runner, ["review", "resume.html", "--json"])
    assert result.exit_code == 3
    assert json.loads(result.output)["error"]["code"] == "ingest.target_missing"


def test_review_scanned_pdf_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_scanned_pdf(tmp_path / "scan.pdf")
    runner = CliRunner()
    result = _run(runner, ["review", "scan.pdf", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert result.exit_code == 5
    assert json.loads(result.output)["error"]["code"] == "ingest.scanned"


def test_unsupported_format_exits_5(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resume.png").write_bytes(b"not an image")
    runner = CliRunner()
    result = _run(runner, ["review", "resume.png", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert result.exit_code == 5
    assert json.loads(result.output)["error"]["code"] == "ingest.unsupported_format"


def test_template_import_learns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "resume.html")
    runner = CliRunner()
    result = _run(runner, ["template-import", "resume.html", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["learned"]["template_id"].startswith("user-")
    assert (tmp_path / "templates" / payload["learned"]["template_id"] / "manifest.json").is_file()


def test_template_import_failing_exits_4(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "bad.html", BAD_HTML)
    runner = CliRunner()
    result = _run(runner, ["template-import", "bad.html", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert result.exit_code == 4
    assert json.loads(result.output)["ok"] is False
    assert not (tmp_path / "templates").exists()


def test_optimize_merges_vault_and_learns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_docx(tmp_path / "resume.docx")
    runner = CliRunner()
    result = _run(
        runner,
        [
            "optimize",
            "resume.docx",
            "--market",
            "cn_internet",
            "--persona",
            "student_with_internship",
            "--role",
            "后端开发工程师（校招）",
            "--keep-template",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["vault_saved"] is True
    assert payload["decision"]["decision"] == "keep"
    vault = load_vault(root=tmp_path)
    assert vault["identity"]["full_name"] == "Li Ming"
    assert vault["status"] == "collecting"
    assert vault["preferences"]["target_roles"] == ["后端开发工程师（校招）"]
    assert (tmp_path / "templates" / payload["decision"]["template"]["template_id"]).is_dir()


def test_optimize_rejecting_failing_template_does_not_write_vault(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "bad.html", BAD_HTML)
    runner = CliRunner()
    result = _run(
        runner,
        ["optimize", "bad.html", "--market", "intl_en", "--persona", "experienced", "--keep-template", "--json"],
    )
    assert result.exit_code == 4
    payload = json.loads(result.output)
    assert payload["vault_saved"] is False
    assert not vault_path(tmp_path).exists()


def test_optimize_override_allows_failed_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "bad.html", BAD_HTML)
    runner = CliRunner()
    result = _run(
        runner,
        [
            "optimize",
            "bad.html",
            "--market",
            "intl_en",
            "--persona",
            "experienced",
            "--keep-template",
            "--override",
            "legacy internal design",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["vault_saved"] is True
    assert payload["decision"]["override"] == "legacy internal design"
    assert (tmp_path / "templates" / payload["decision"]["template"]["template_id"]).is_dir()


def test_optimize_replaces_vault_for_a_different_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_docx(tmp_path / "li.docx")
    write_html(tmp_path / "jane.html", BAD_HTML)
    runner = CliRunner()
    first = _run(runner, ["optimize", "li.docx", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert first.exit_code == 0, first.output
    second = _run(runner, ["optimize", "jane.html", "--market", "intl_en", "--persona", "experienced", "--json"])
    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)
    assert payload["vault_replaced"] is True
    vault = load_vault(root=tmp_path)
    assert vault["identity"]["full_name"] == "Jane Doe"


def test_restyle_generates_preview_without_vault(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write_html(tmp_path / "resume.html")
    write_docx(tmp_path / "resume.docx")
    runner = CliRunner()
    imported = _run(
        runner,
        ["template-import", "resume.html", "--market", "intl_en", "--persona", "experienced", "--json"],
    )
    assert imported.exit_code == 0, imported.output
    template_id = json.loads(imported.output)["learned"]["template_id"]
    restyled = _run(
        runner,
        [
            "restyle",
            "resume.docx",
            "--template",
            template_id,
            "--market",
            "intl_en",
            "--persona",
            "experienced",
            "--json",
        ],
    )
    assert restyled.exit_code == 0, restyled.output
    payload = json.loads(restyled.output)
    assert Path(payload["preview"]).is_file()
    assert not vault_path(tmp_path).exists()
