# SPDX-License-Identifier: MIT
"""CLI contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from resume_pro.cli import cli
from resume_pro.vault import load_vault, save_vault
from tests.conftest import load_example
from tests.ingest_fixtures import write_html
from tests.test_intake import FULL_ANSWERS


def test_init_creates_vault_and_is_idempotent():
    runner = CliRunner()
    with runner.isolated_filesystem():
        first = runner.invoke(cli, ["--json", "init"])
        assert first.exit_code == 0
        data = json.loads(first.output)
        assert data["created"] is True
        second = runner.invoke(cli, ["--json", "init"])
        assert second.exit_code == 0
        assert json.loads(second.output)["created"] is False


def test_check_without_target_errors():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "check"])
        assert result.exit_code == 3
        assert json.loads(result.output)["error"]["code"] == "gate.context_missing"


def test_check_blocks_empty_vault():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--market", "cn_internet", "--persona", "student_with_internship"])
        result = runner.invoke(cli, ["--json", "check"])
        assert result.exit_code == 2
        payload = json.loads(result.output)
        assert payload["gate"]["status"] == "blocked"
        assert payload["gate"]["blockers"]
        assert payload["report"].endswith("sufficiency.json")


def test_intake_json_returns_first_question():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "intake"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["question"]["id"] == "target.market"
        assert "choices" in payload["question"]


def test_intake_accepts_answer_and_advances():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "intake", "--answer", "cn_internet"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["answered"] == "target.market"
        assert payload["question"]["id"] == "target.persona"


def test_invalid_choice_exits_3():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "intake", "--answer", "mars"])
        assert result.exit_code == 3
        assert json.loads(result.output)["error"]["code"] == "intake.invalid_choice"


def test_profile_json():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--market", "cn_internet", "--persona", "student_with_internship"])
        result = runner.invoke(cli, ["--json", "profile"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["summary"]["target"]["market"] == "cn_internet"
        assert payload["gate"]["status"] == "blocked"


def test_summary_json():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--market", "cn_internet", "--persona", "student_with_internship"])
        result = runner.invoke(cli, ["--json", "intake", "--summary"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["summary"]["counts"]["experience"] == 0


def test_build_refuses_blocked_vault():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init", "--market", "cn_internet", "--persona", "student_with_internship"])
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 2


def test_lang_zh_returns_chinese_prompt():
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ["init"])
        result = runner.invoke(cli, ["--json", "--lang", "zh", "intake"])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["question"]["prompt"]["zh"]


def _agent_step(runner, *args):
    """Run one non-TTY state operation, not a real host question-tool call."""
    result = runner.invoke(cli, ["--json", "--lang", "zh", *args])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _saved_intake():
    return {
        name: Path(".resume", name).read_bytes()
        for name in ("vault.yaml", "intake-session.json")
    }


def test_agent_intake_rounds_save_answers_and_retry_invalid_input():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _agent_step(runner, "init", "--market", "cn_internet", "--persona", "student_with_internship")
        pending = _agent_step(runner, "intake")
        assert pending["question"]["id"] == "preferences.application_mode"
        saved = _saved_intake()
        invalid = runner.invoke(cli, ["--json", "intake", "--id", pending["question"]["id"], "--answer", "maybe"])
        assert invalid.exit_code == 3
        assert json.loads(invalid.output)["error"]["code"] == "intake.invalid_bool"
        assert _saved_intake() == saved
        assert _agent_step(runner, "intake")["question"] == pending["question"]

        for qid, answer, next_id in (
            ("preferences.application_mode", "no", "target.role"),
            ("target.role", "后端工程师", "target.company"),
            ("target.company", "示例科技", "identity.full_name"),
        ):
            result = _agent_step(runner, "intake", "--id", qid, "--answer", answer)
            assert result["answered"] == qid
            assert result["question"]["id"] == next_id
            assert result["complete"] is False
            assert _agent_step(runner, "intake")["question"] == result["question"]
        session = json.loads(Path(".resume/intake-session.json").read_text(encoding="utf-8"))
        assert session["answered"].count("target.market") == 1
        assert session["answered"].count("target.persona") == 1
        assert session["role"] == "后端工程师"
        assert session["company"] == "示例科技"


def test_agent_summary_and_resume_do_not_consume_pending_question():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _agent_step(runner, "init", "--market", "cn_internet", "--persona", "student_with_internship")
        pending = _agent_step(runner, "intake", "--id", "preferences.application_mode", "--answer", "yes")
        saved = _saved_intake()
        summary = _agent_step(runner, "intake", "--summary")
        assert summary["summary"]["target"]["market"] == "cn_internet"
        assert _saved_intake() == saved
        # A pause/cancel requires no write; another invocation resumes the same question.
        resumed = _agent_step(runner, "intake")
        assert resumed["question"] == pending["question"]
        assert _saved_intake() == saved
        answered = _agent_step(runner, "intake", "--id", resumed["question"]["id"], "--answer", "后端开发")
        assert answered["question"]["id"] == "target.company"
        assert load_vault(root=Path.cwd())["preferences"]["application_mode"] == "mass"


def test_agent_unknown_is_a_gap_not_an_answer_or_consent():
    runner = CliRunner()
    with runner.isolated_filesystem():
        _agent_step(runner, "init", "--market", "cn_internet", "--persona", "student_with_internship")
        pending = _agent_step(runner, "intake")
        qid = pending["question"]["id"]
        response = _agent_step(runner, "intake", "--id", qid, "--answer", "不知道")
        assert response["question"]["id"] == "target.role"
        session = json.loads(Path(".resume/intake-session.json").read_text(encoding="utf-8"))
        assert qid in session["skipped"]
        assert qid not in session["answered"]
        assert session["confirmed"] is False
        summary = _agent_step(runner, "intake", "--summary")
        assert any(note["severity"] == "blocker" for note in summary["summary"]["unresolved"])
        check = runner.invoke(cli, ["--json", "check"])
        assert check.exit_code == 2


def test_agent_full_intake_preserves_free_text_and_reopens_confirmation():
    runner = CliRunner()
    description = '为示例课程实现检索服务，独立负责索引与评测。\n保留 "C++ / Python" 技术细节，不把描述改成选项标签。'
    answers = {**FULL_ANSWERS, "projects.0.own_contribution": description}
    with runner.isolated_filesystem():
        _agent_step(runner, "init")
        response = _agent_step(runner, "intake")
        seen = set()
        for _ in range(200):
            assert not response["complete"]
            question = response["question"]
            qid = question["id"]
            assert qid not in seen, f"Repeated answered question: {qid}"
            seen.add(qid)
            if qid == "confirm.summary":
                saved = _saved_intake()
                summary = _agent_step(runner, "intake", "--summary")
                assert summary["summary"]["confirmed"] is False
                assert summary["summary"]["counts"]["projects"] == 1
                assert _saved_intake() == saved
                # Simulate a legacy skipped confirmation: an exhausted question
                # list is not consent. The agent must still obtain real approval.
                skipped = _agent_step(runner, "intake", "--id", qid, "--skip")
                assert skipped["complete"] is True
                summary = _agent_step(runner, "intake", "--summary")
                assert summary["summary"]["confirmed"] is False
            if qid in answers:
                response = _agent_step(runner, "intake", "--id", qid, "--answer", answers[qid])
            else:
                assert question["required"] is False, qid
                response = _agent_step(runner, "intake", "--id", qid, "--skip")
            if response["complete"]:
                break
        else:
            raise AssertionError("Intake did not complete")

        assert response["question"] is None
        assert "confirm.summary" in seen
        vault = load_vault(root=Path.cwd())
        assert vault["projects"][0]["own_contribution"]["zh"] == description
        assert _agent_step(runner, "check")["gate"]["status"] == "strong"
        assert _agent_step(runner, "intake")["complete"] is True

        corrected = _agent_step(runner, "intake", "--id", "identity.full_name", "--answer", "示例新姓名")
        assert corrected["complete"] is False
        assert corrected["question"]["id"] == "confirm.summary"
        summary = _agent_step(runner, "intake", "--summary")
        assert summary["summary"]["identity"]["name"] == "示例新姓名"
        assert summary["summary"]["confirmed"] is False
        assert summary["summary"]["vault_status"] == "collecting"
        assert _agent_step(runner, "intake", "--id", "confirm.summary", "--answer", "yes")["complete"] is True


def test_internal_error_exits_7_with_report(tmp_path, monkeypatch):
    import resume_pro.cli as cli_module

    monkeypatch.chdir(tmp_path)

    def boom():
        raise RuntimeError("unexpected internal failure")

    monkeypatch.setattr(cli_module, "cli", boom)
    with pytest.raises(SystemExit) as exc:
        cli_module.main()
    assert exc.value.code == 7
    assert list(tmp_path.rglob("internal-error-*.json")), "an internal-error report path must be written"


def test_internal_error_message_is_redacted(tmp_path, monkeypatch, capsys):
    import resume_pro.cli as cli_module

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "_INCLUDE_PII", False)

    def boom():
        raise RuntimeError("failed for liming@example.com / +86 137 0000 0000")

    monkeypatch.setattr(cli_module, "cli", boom)
    with pytest.raises(SystemExit) as exc:
        cli_module.main()
    assert exc.value.code == 7
    err = capsys.readouterr().err
    assert "liming@example.com" not in err
    assert "+86 137 0000 0000" not in err
    assert "[REDACTED]" in err
    # The local report on disk keeps the full data (redaction is output-only).
    report = next(tmp_path.rglob("internal-error-*.json"))
    assert "liming@example.com" in report.read_text(encoding="utf-8")


def test_human_error_output_is_redacted(monkeypatch, capsys):
    import click

    import resume_pro.cli as cli_module
    from resume_pro.errors import ResumeProError

    monkeypatch.setattr(cli_module, "_INCLUDE_PII", False)
    ctx = click.Context(click.Command("demo"))
    ctx.obj = {"json": False}
    error = ResumeProError("demo.err", "contact liming@example.com or 13700000000", fix="mail a@b.com")
    with pytest.raises(click.exceptions.Exit):
        cli_module._handle(ctx, error)
    err = capsys.readouterr().err
    assert "liming@example.com" not in err
    assert "13700000000" not in err
    assert "[REDACTED]" in err


def test_cwd_overrides_project_root(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    runner = CliRunner()
    created = runner.invoke(
        cli,
        ["--cwd", str(project), "init", "--market", "cn_internet", "--persona", "student_with_internship", "--json"],
    )
    assert created.exit_code == 0, created.output
    assert (project / ".resume" / "vault.yaml").exists()
    assert not (elsewhere / ".resume").exists()


def test_new_persists_absolute_jd_path_under_cwd(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    runner = CliRunner()
    created = runner.invoke(
        cli,
        ["--cwd", str(project), "init", "--market", "cn_internet", "--persona", "student_with_internship", "--json"],
    )
    assert created.exit_code == 0, created.output
    save_vault(load_example("vault-student.yaml"), root=project, validate=False)
    (project / "jd.md").write_text("Backend engineer: Python, MySQL, Redis.", encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "--cwd", str(project), "new", "--role", "Backend Engineer",
            "--market", "cn_internet", "--persona", "student_with_internship",
            "--framework", "result_first", "--jd", "jd.md", "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    slug = json.loads(result.output)["slug"]
    application = yaml.safe_load((project / ".resume" / "applications" / slug / "application.yaml").read_text(encoding="utf-8"))
    jd_path = application["target"]["jd_path"]
    assert Path(jd_path).is_absolute(), "persisted --jd must be absolute so it survives a cwd change"
    assert Path(jd_path) == (project / "jd.md").resolve()
    assert Path(jd_path).is_file()


def test_tailor_persists_absolute_jd_path_under_cwd(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    runner = CliRunner()
    assert runner.invoke(
        cli,
        ["--cwd", str(project), "init", "--market", "cn_internet", "--persona", "student_with_internship", "--json"],
    ).exit_code == 0
    save_vault(load_example("vault-student.yaml"), root=project, validate=False)
    (project / "jd.md").write_text("Backend engineer: Python, MySQL, Redis.", encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "--cwd", str(project), "tailor", "--jd", "jd.md",
            "--market", "cn_internet", "--persona", "student_with_internship",
            "--framework", "result_first", "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    slug = json.loads(result.output)["slug"]
    application = yaml.safe_load((project / ".resume" / "applications" / slug / "application.yaml").read_text(encoding="utf-8"))
    jd_path = application["target"]["jd_path"]
    assert Path(jd_path).is_absolute()
    assert Path(jd_path) == (project / "jd.md").resolve()


def test_cwd_relative_file_argument_resolves_against_cwd_dir(tmp_path, monkeypatch):
    # --cwd chdirs before the subcommand FILE argument is parsed, so a relative
    # FILE is looked up inside the --cwd directory, not the launch directory.
    project = tmp_path / "project"
    project.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    write_html(project / "resume.html")
    write_html(elsewhere / "launch-only.html")
    monkeypatch.chdir(elsewhere)
    runner = CliRunner()

    found = runner.invoke(
        cli,
        ["--cwd", str(project), "review", "resume.html", "--market", "intl_en", "--persona", "experienced", "--json"],
    )
    assert found.exit_code == 0, found.output
    assert json.loads(found.output)["ok"] is True

    # A file that exists only in the launch directory is not visible under --cwd.
    missing = runner.invoke(
        cli,
        ["--cwd", str(project), "review", "launch-only.html", "--market", "intl_en", "--persona", "experienced", "--json"],
    )
    assert missing.exit_code == 2


def test_json_redacts_pii_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--market", "cn_internet", "--persona", "student_with_internship"]).exit_code == 0
    vault = load_vault(root=tmp_path)
    vault["identity"]["full_name"] = "Li Ming"
    vault["identity"]["email"] = "liming@example.com"
    vault["identity"]["phone"] = "+86 137 0000 0000"
    save_vault(vault, root=tmp_path, validate=False)

    redacted = runner.invoke(cli, ["--json", "intake", "--summary"])
    assert redacted.exit_code == 0, redacted.output
    ident = json.loads(redacted.output)["summary"]["identity"]
    assert ident["email"] == "[REDACTED]"
    assert ident["phone"] == "[REDACTED]"
    assert ident["name"] == "Li Ming"  # names are not in the contract's PII list

    full = runner.invoke(cli, ["--json", "--include-pii", "intake", "--summary"])
    assert full.exit_code == 0, full.output
    ident_full = json.loads(full.output)["summary"]["identity"]
    assert ident_full["email"] == "liming@example.com"
    assert ident_full["phone"] == "+86 137 0000 0000"


def _cn_student_app(tmp_path, monkeypatch, runner):
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(cli, ["init", "--market", "cn_internet", "--persona", "student_with_internship"]).exit_code == 0
    save_vault(load_example("vault-student.yaml"), root=tmp_path, validate=False)
    created = runner.invoke(
        cli,
        ["new", "--role", "Backend Engineer", "--market", "cn_internet", "--persona", "student_with_internship", "--framework", "result_first", "--json"],
    )
    assert created.exit_code == 0, created.output
    return json.loads(created.output)["slug"]


def test_restyle_newest_snapshot_is_the_delivered_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(cli, ["init", "--market", "intl_en", "--persona", "experienced"]).exit_code == 0
    save_vault(load_example("vault-experienced.yaml"), root=tmp_path, validate=False)
    created = runner.invoke(
        cli,
        ["new", "--role", "Senior Backend Engineer", "--market", "intl_en", "--persona", "experienced", "--framework", "result_first", "--template", "ats-classic", "--json"],
    )
    assert created.exit_code == 0, created.output
    slug = json.loads(created.stdout)["slug"]
    assert runner.invoke(cli, ["build", slug, "--yes", "--json"]).exit_code == 0
    restyled = runner.invoke(cli, ["restyle", "--app", slug, "--template", "modern-sidebar", "--yes", "--json"])
    assert restyled.exit_code == 0, restyled.output
    app_dir = tmp_path / ".resume" / "applications" / slug
    application = yaml.safe_load((app_dir / "application.yaml").read_text(encoding="utf-8"))
    html_name = application["output"]["html"]
    root_html = (app_dir / html_name).read_bytes()
    versions = sorted((app_dir / "versions").iterdir())
    assert len(versions) >= 2, "restyle keeps the prior state and snapshots the delivered rebuild"
    # The newest snapshot must match the published resume, not the pre-restyle state.
    assert (versions[-1] / html_name).read_bytes() == root_html


def test_build_reports_pruned_versions(tmp_path, monkeypatch):
    import resume_pro.cli as cli_module

    monkeypatch.setattr(cli_module, "MAX_VERSIONS", 1)
    runner = CliRunner()
    slug = _cn_student_app(tmp_path, monkeypatch, runner)
    assert runner.invoke(cli, ["build", slug, "--yes", "--json"]).exit_code == 0
    vault = load_vault(root=tmp_path)
    vault["identity"]["full_name"] = {"zh": "示例新名", "en": "Example Newname"}
    save_vault(vault, root=tmp_path, validate=False)
    rebuilt = runner.invoke(cli, ["build", slug, "--yes", "--json"])
    assert rebuilt.exit_code == 0, rebuilt.output
    payload = json.loads(rebuilt.stdout)
    assert payload.get("versions_pruned"), "pruning must be surfaced in the JSON payload"
    assert "versions.pruned" in rebuilt.stderr


def test_warn_versions_pruned_helper(capsys):
    import resume_pro.cli as cli_module

    cli_module._warn_versions_pruned(["20261101-000000-000000"], True)
    err = capsys.readouterr().err
    assert "versions.pruned" in err
    cli_module._warn_versions_pruned(["20261101-000000-000000"], False)
    err = capsys.readouterr().err
    assert "warning:" in err and "20261101-000000-000000" in err
    cli_module._warn_versions_pruned([], False)
    assert capsys.readouterr().err == ""


def test_diff_missing_version_mentions_pruning(tmp_path, monkeypatch):
    runner = CliRunner()
    slug = _cn_student_app(tmp_path, monkeypatch, runner)
    assert runner.invoke(cli, ["build", slug, "--yes", "--json"]).exit_code == 0
    result = runner.invoke(cli, ["diff", slug, "20990101-000000-000000", "current", "--json"])
    assert result.exit_code == 3
    error = json.loads(result.output)["error"]
    assert error["code"] == "diff.version_missing"
    assert "pruned" in error["fix"]
