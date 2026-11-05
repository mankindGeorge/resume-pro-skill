# SPDX-License-Identifier: MIT
"""CLI contract tests."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from resume_pro.cli import cli
from resume_pro.vault import load_vault
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
