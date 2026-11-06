# SPDX-License-Identifier: MIT
"""CLI build, draft, templates, and restyle tests."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from resume_pro.application import load_application
from resume_pro.cli import cli
from resume_pro.vault import load_vault, save_vault
from tests.conftest import load_example


def _cn_app(tmp_path, monkeypatch, *, minimum=False):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--market", "cn_internet", "--persona", "student_with_internship"]).exit_code == 0
    vault = load_example("vault-student.yaml")
    if minimum:
        vault["projects"][0]["tech"] = []
    save_vault(vault, root=tmp_path, validate=False)
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
    assert created.exit_code == 0, created.output
    return runner, json.loads(created.output)["slug"]


def test_build_renders_html_and_editable(tmp_path, monkeypatch):
    runner, slug = _cn_app(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["render"]["format"] == "html"
    app_dir = tmp_path / ".resume" / "applications" / slug
    html_path = Path(payload["render"]["html"])
    editable_path = Path(payload["render"]["editable_html"])
    assert html_path.is_file()
    assert editable_path.is_file()
    assert html_path.name.startswith("resume-")
    assert not list(app_dir.glob("*.pdf"))
    assert not list(app_dir.glob("*.docx"))


def test_build_minimum_requires_yes(tmp_path, monkeypatch):
    runner, slug = _cn_app(tmp_path, monkeypatch, minimum=True)
    result = runner.invoke(cli, ["build", slug, "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["gate"]["status"] == "minimum"


def test_build_draft_has_banner(tmp_path, monkeypatch):
    runner, slug = _cn_app(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["build", slug, "--yes", "--draft", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    html = Path(payload["render"]["html"]).read_text(encoding="utf-8")
    assert "DRAFT — NOT FOR SUBMISSION" in html


def test_build_blocked_vault_exits_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init", "--market", "intl_en", "--persona", "experienced"])
    created = runner.invoke(
        cli,
        [
            "new",
            "--role",
            "Backend Engineer",
            "--market",
            "intl_en",
            "--persona",
            "experienced",
            "--framework",
            "result_first",
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    slug = json.loads(created.output)["slug"]
    result = runner.invoke(cli, ["build", slug, "--json"])
    assert result.exit_code == 2
    assert json.loads(result.output)["gate"]["status"] == "blocked"


def test_templates_lists_library(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["templates", "--json"])
    assert result.exit_code == 0, result.output
    ids = {item["id"] for item in json.loads(result.output)["templates"]}
    assert {"ats-classic", "campus", "compact", "modern-sidebar", "editorial", "executive"} <= ids
    items = json.loads(result.output)["templates"]
    assert len(items) == 12
    assert {(item["id"], item["language"]) for item in items} == {(name, language) for name in ids for language in ("zh", "en")}
    for item in items:
        assert "error" not in item
        assert Path(item["path"]).parent.name == ("cn" if item["language"] == "zh" else "en")
        assert item["preview"] and Path(item["preview"]).is_file()
        assert Path(item["preview"]).name == "preview.html"


def test_templates_human_output_shows_preview_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli, ["templates"])
    assert result.exit_code == 0, result.output
    assert "preview:" in result.output
    assert result.output.count("preview:") == 12
    assert "preview.html" in result.output


def test_restyle_app_rebuilds_with_new_template(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init", "--market", "intl_en", "--persona", "experienced"])
    vault = load_example("vault-experienced.yaml")
    save_vault(vault, root=tmp_path, validate=False)
    created = runner.invoke(
        cli,
        [
            "new",
            "--role",
            "Senior Backend Engineer",
            "--market",
            "intl_en",
            "--persona",
            "experienced",
            "--framework",
            "result_first",
            "--template",
            "ats-classic",
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    slug = json.loads(created.output)["slug"]
    built = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert built.exit_code == 0, built.output

    restyled = runner.invoke(
        cli,
        ["restyle", "--app", slug, "--template", "modern-sidebar", "--yes", "--json"],
    )
    assert restyled.exit_code == 0, restyled.output
    application = yaml.safe_load((tmp_path / ".resume" / "applications" / slug / "application.yaml").read_text(encoding="utf-8"))
    assert application["template"]["id"] == "modern-sidebar"
    output_name = application["output"]["html"]
    html = (tmp_path / ".resume" / "applications" / slug / output_name).read_text(encoding="utf-8")
    assert 'class="layout"' in html


def test_localize_cn_to_en(tmp_path, monkeypatch):
    runner, slug = _cn_app(tmp_path, monkeypatch)
    built = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert built.exit_code == 0, built.output
    source_path = tmp_path / ".resume" / "applications" / slug / "application.yaml"
    before = source_path.read_text(encoding="utf-8")
    result = runner.invoke(
        cli,
        ["localize", slug, "--to", "en", "--role", "Backend Engineering Intern", "--yes", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    localize = payload["localize"]
    assert localize["parity"]["status"] == "pass"
    assert localize["target_market"] == "intl_en"
    assert payload["build"]["render"]["template_id"] == "campus"
    assert Path(payload["build"]["render"]["html"]).is_file()
    html = Path(payload["build"]["render"]["html"]).read_text(encoding="utf-8")
    assert "Education" in html
    assert "教育经历" not in html
    assert source_path.read_text(encoding="utf-8") == before


def test_localize_gap_blocks_or_marks_draft(tmp_path, monkeypatch):
    runner, slug = _cn_app(tmp_path, monkeypatch)
    built = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert built.exit_code == 0, built.output
    vault = load_vault(root=tmp_path)
    vault["experience"][0]["bullets"][0]["text"].pop("en", None)
    save_vault(vault, root=tmp_path, validate=False)

    blocked = runner.invoke(cli, ["localize", slug, "--to", "en", "--role", "Backend Intern", "--yes", "--json"])
    assert blocked.exit_code == 3
    assert json.loads(blocked.output)["error"]["code"] == "localize.locale_gaps"

    draft = runner.invoke(
        cli,
        ["localize", slug, "--to", "en", "--role", "Backend Intern", "--yes", "--draft", "--json"],
    )
    assert draft.exit_code == 4
    payload = json.loads(draft.output)
    assert payload["localize"]["parity"]["status"] == "fail"
    html = Path(payload["build"]["render"]["html"]).read_text(encoding="utf-8")
    assert "[NEEDS EN]" in html
    assert "DRAFT — NOT FOR SUBMISSION" in html


def test_audit_clean_and_tampered(tmp_path, monkeypatch):
    runner, slug = _cn_app(tmp_path, monkeypatch)
    built = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert built.exit_code == 0, built.output
    clean = runner.invoke(cli, ["audit", slug, "--json"])
    assert clean.exit_code == 0, clean.output
    assert json.loads(clean.output)["qa"]["status"] in {"pass", "warn"}

    application = load_application(tmp_path, slug)
    html_path = tmp_path / ".resume" / "applications" / slug / application["output"]["html"]
    html = html_path.read_text(encoding="utf-8")
    html_path.write_text(html.replace("--size-body: 10.5pt", "--size-body: 7pt", 1), encoding="utf-8")
    tampered = runner.invoke(cli, ["audit", slug, "--json"])
    assert tampered.exit_code == 4
    assert json.loads(tampered.output)["qa"]["status"] == "fail"


def test_audit_requires_rendered_output(tmp_path, monkeypatch):
    runner, slug = _cn_app(tmp_path, monkeypatch)
    result = runner.invoke(cli, ["audit", slug, "--json"])
    assert result.exit_code == 4
    assert json.loads(result.output)["qa"]["status"] == "fail"


def test_diff_reports_template_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(cli, ["init", "--market", "intl_en", "--persona", "experienced"])
    vault = load_example("vault-experienced.yaml")
    save_vault(vault, root=tmp_path, validate=False)
    created = runner.invoke(
        cli,
        [
            "new",
            "--role",
            "Senior Backend Engineer",
            "--market",
            "intl_en",
            "--persona",
            "experienced",
            "--framework",
            "result_first",
            "--template",
            "ats-classic",
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    slug = json.loads(created.output)["slug"]
    assert runner.invoke(cli, ["build", slug, "--yes", "--json"]).exit_code == 0
    restyled = runner.invoke(
        cli,
        ["restyle", "--app", slug, "--template", "modern-sidebar", "--yes", "--json"],
    )
    assert restyled.exit_code == 0, restyled.output
    versions = sorted((tmp_path / ".resume" / "applications" / slug / "versions").iterdir())
    assert versions
    result = runner.invoke(cli, ["diff", slug, versions[0].name, "current", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["template_from"] == "ats-classic"
    assert payload["template_to"] == "modern-sidebar"
    assert payload["facts_added"] == []
    assert payload["facts_removed"] == []


def test_photo_command_embeds_and_clears(tmp_path, monkeypatch):
    runner, slug = _cn_app(tmp_path, monkeypatch)
    image = tmp_path / "photo.png"
    image.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
        )
    )
    added = runner.invoke(cli, ["photo", str(image), "--app", slug, "--json"])
    assert added.exit_code == 0, added.output
    built = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert built.exit_code == 0, built.output
    html = Path(json.loads(built.output)["render"]["html"]).read_text(encoding="utf-8")
    assert "data:image/png;base64," in html

    cleared = runner.invoke(cli, ["photo", "--clear", "--json"])
    assert cleared.exit_code == 0, cleared.output
    rebuilt = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert rebuilt.exit_code == 0, rebuilt.output
    html = Path(json.loads(rebuilt.output)["render"]["html"]).read_text(encoding="utf-8")
    assert "<img" not in html
