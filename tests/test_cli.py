# SPDX-License-Identifier: MIT
"""CLI contract tests."""

from __future__ import annotations

import json

from click.testing import CliRunner

from resume_pro.cli import cli


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
