# SPDX-License-Identifier: MIT
"""Evidence, numeric-claim, and fabrication tests."""

from __future__ import annotations

import pytest

from resume_pro.errors import IntakeError
from resume_pro.evidence import (
    add_evidence,
    assert_no_fabrication,
    infer_source,
    upsert_bullet,
    validate_evidence,
)
from resume_pro.vault import empty_vault


def _vault_with_bullet(status: str, text: str = "Cut latency from 480ms to 190ms"):
    vault = empty_vault()
    vault["experience"] = [
        {
            "id": "exp_001",
            "company": "Acme",
            "title": {"en": "Intern"},
            "start": "2026-06",
            "bullets": [],
        }
    ]
    evidence_id = add_evidence(vault, "claim", status=status)
    vault["experience"][0]["bullets"].append(
        {"id": "bul_exp_001_1", "text": {"en": text}, "evidence": [evidence_id]}
    )
    return vault


def test_bullet_without_evidence_is_an_error():
    vault = empty_vault()
    vault["experience"] = [
        {
            "id": "exp_001",
            "company": "Acme",
            "title": {"en": "Intern"},
            "start": "2026-06",
            "bullets": [{"id": "bul_exp_001_1", "text": {"en": "Did work"}, "evidence": []}],
        }
    ]
    codes = [issue.code for issue in validate_evidence(vault).errors]
    assert "evidence.missing" in codes


def test_number_with_only_estimated_source_is_an_error():
    vault = _vault_with_bullet("estimated")
    codes = [issue.code for issue in validate_evidence(vault).errors]
    assert "evidence.unsupported_number" in codes


def test_number_with_user_asserted_source_is_allowed():
    vault = _vault_with_bullet("user_asserted")
    assert validate_evidence(vault).ok


def test_inference_cannot_be_promoted():
    vault = empty_vault()
    vault["evidence"]["ev_001"] = {
        "id": "ev_001",
        "claim": "Inferred from context",
        "status": "verified",
        "source": "inference",
    }
    codes = [issue.code for issue in validate_evidence(vault).errors]
    assert "evidence.inference_promoted" in codes


def test_verified_without_locator_warns():
    vault = empty_vault()
    vault["evidence"]["ev_001"] = {
        "id": "ev_001",
        "claim": "Verified but unlocatable",
        "status": "verified",
        "source": "document",
    }
    codes = [issue.code for issue in validate_evidence(vault).warnings]
    assert "evidence.verified_without_locator" in codes


@pytest.mark.parametrize(
    "text,expected",
    [
        ("See https://github.com/example/repo", ("repo", "https://github.com/example/repo")),
        ("Portfolio: https://example.com/work", ("portfolio", "https://example.com/work")),
        ("No link here", ("user_statement", None)),
    ],
)
def test_infer_source(text, expected):
    assert infer_source(text) == expected


@pytest.mark.parametrize("text", ["just make something up", "随便写一个", "编一个项目", "fabricate it"])
def test_fabrication_is_refused(text):
    with pytest.raises(IntakeError) as error:
        assert_no_fabrication(text)
    assert error.value.code == "intake.fabrication_refused"


def test_upsert_bullet_creates_stable_ids_and_evidence():
    vault = empty_vault()
    vault["experience"] = [
        {"id": "exp_001", "company": "Acme", "title": {"en": "Intern"}, "start": "2026-06", "bullets": []}
    ]
    bullet = upsert_bullet(vault, "experience", 0, 0, "Cut latency by 40%", lang="en")
    assert bullet["id"] == "bul_exp_001_1"
    assert bullet["evidence"][0] in vault["evidence"]
    assert vault["evidence"][bullet["evidence"][0]]["status"] == "user_asserted"
    # Re-answering updates rather than duplicating.
    again = upsert_bullet(vault, "experience", 0, 0, "Cut latency by 45%", lang="en")
    assert again["id"] == bullet["id"]
    assert len(vault["experience"][0]["bullets"]) == 1
    assert vault["evidence"][bullet["evidence"][0]]["claim"] == "Cut latency by 45%"
