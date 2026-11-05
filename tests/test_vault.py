# SPDX-License-Identifier: MIT
"""Vault validation, atomic save, ids, and merge tests."""

from __future__ import annotations

import copy

import pytest
import yaml

from resume_pro.errors import VaultError
from resume_pro.paths import delete_path, get_path, set_path
from resume_pro.vault import (
    empty_vault,
    ensure_ids,
    merge_vaults,
    next_id,
    save_vault,
    load_vault,
    validate_vault,
    vault_fingerprint,
)


def test_empty_vault_is_valid():
    assert validate_vault(empty_vault()).ok


def test_save_and_load_roundtrip(tmp_path):
    vault = empty_vault()
    vault["identity"]["full_name"] = "Li Ming"
    path = tmp_path / "vault.yaml"
    save_vault(vault, path, validate=False)
    loaded = load_vault(path)
    assert loaded["identity"]["full_name"] == "Li Ming"
    assert not list(tmp_path.glob(".vault-*"))


def test_ready_vault_with_invalid_schema_is_rejected(tmp_path):
    vault = empty_vault()
    vault["status"] = "ready"
    vault["schema_version"] = "9.9"
    with pytest.raises(VaultError) as error:
        save_vault(vault, tmp_path / "vault.yaml")
    assert error.value.code == "vault.invalid"


def test_duplicate_ids_are_reported():
    vault = empty_vault()
    vault["education"] = [
        {"id": "edu_001", "school": "A"},
        {"id": "edu_001", "school": "B"},
    ]
    result = validate_vault(vault)
    assert any(issue.code == "vault.duplicate_id" for issue in result.errors)


def test_missing_evidence_ref_is_reported():
    vault = empty_vault()
    vault["experience"] = [
        {
            "id": "exp_001",
            "company": "Acme",
            "title": {"en": "Intern"},
            "start": "2026-06",
            "bullets": [
                {"id": "bul_exp_001_1", "text": {"en": "Did work"}, "evidence": ["ev_missing"]}
            ],
        }
    ]
    result = validate_vault(vault)
    assert any(issue.code == "vault.missing_evidence" for issue in result.errors)


def test_next_id_increments():
    vault = empty_vault()
    assert next_id(vault, "edu") == "edu_001"
    vault["education"].append({"id": "edu_001", "school": "A"})
    assert next_id(vault, "edu") == "edu_002"


def test_ensure_ids_fills_missing_ids():
    vault = empty_vault()
    vault["education"] = [{"school": "A"}]
    vault["experience"] = [
        {
            "company": "Acme",
            "title": {"en": "Intern"},
            "start": "2026-06",
            "bullets": [{"text": {"en": "Did work"}, "evidence": ["ev_001"]}],
        }
    ]
    ensure_ids(vault)
    assert vault["education"][0]["id"] == "edu_001"
    assert vault["experience"][0]["id"] == "exp_001"
    assert vault["experience"][0]["bullets"][0]["id"] == "bul_exp_001_1"


def test_merge_dedupes_same_education():
    base = empty_vault()
    base["education"] = [
        {"id": "edu_001", "school": "Example University", "degree": {"en": "B.Eng."}, "start": "2023-09"}
    ]
    incoming = empty_vault()
    incoming["education"] = [
        {
            "id": "edu_002",
            "school": "example university",
            "degree": {"en": "B.Eng."},
            "start": "2023-09",
            "honors": {"en": ["Dean's list"]},
        }
    ]
    merged = merge_vaults(base, incoming)
    assert len(merged["education"]) == 1
    assert merged["education"][0]["honors"]["en"] == ["Dean's list"]


def test_merge_conflicting_id_reassigns():
    base = empty_vault()
    base["education"] = [{"id": "edu_001", "school": "A", "start": "2023-09"}]
    incoming = empty_vault()
    incoming["education"] = [{"id": "edu_001", "school": "B", "start": "2020-09"}]
    merged = merge_vaults(base, incoming)
    assert len(merged["education"]) == 2
    assert {item["id"] for item in merged["education"]} == {"edu_001", "edu_002"}
    assert {item["school"] for item in merged["education"]} == {"A", "B"}


def test_merge_remaps_conflicting_evidence():
    base = empty_vault()
    base["evidence"]["ev_001"] = {
        "id": "ev_001",
        "claim": "Original claim",
        "status": "user_asserted",
        "source": "user_statement",
    }
    base["experience"] = [
        {"id": "exp_001", "company": "A", "title": {"en": "Engineer"}, "start": "2022-01",
         "bullets": [{"id": "bul_exp_001_1", "text": {"en": "A"}, "evidence": ["ev_001"]}]}
    ]
    incoming = empty_vault()
    incoming["evidence"]["ev_001"] = {
        "id": "ev_001",
        "claim": "Different claim",
        "status": "user_asserted",
        "source": "document",
    }
    incoming["experience"] = [
        {"id": "exp_002", "company": "B", "title": {"en": "Engineer"}, "start": "2020-01",
         "bullets": [{"id": "bul_exp_002_1", "text": {"en": "B"}, "evidence": ["ev_001"]}]}
    ]
    merged = merge_vaults(base, incoming)
    new_ev = merged["experience"][1]["bullets"][0]["evidence"][0]
    assert new_ev != "ev_001"
    assert merged["evidence"][new_ev]["claim"] == "Different claim"
    assert merged["evidence"]["ev_001"]["claim"] == "Original claim"


def test_fingerprint_is_stable_for_identical_content():
    vault = empty_vault()
    assert vault_fingerprint(vault) == vault_fingerprint(copy.deepcopy(vault))
    vault["identity"]["full_name"] = "Li Ming"
    assert vault_fingerprint(vault) != vault_fingerprint(empty_vault())


def test_path_helpers_create_and_delete():
    data = {}
    set_path(data, "education[0].school", "Example University")
    assert get_path(data, "education[0].school") == "Example University"
    delete_path(data, "education[0].school")
    assert get_path(data, "education[0].school") is None


def test_collecting_vault_skips_schema_on_load(tmp_path):
    vault = empty_vault()
    vault["identity"]["full_name"] = 123  # wrong type, but collecting is allowed
    path = tmp_path / "vault.yaml"
    path.write_text(yaml.safe_dump(vault), encoding="utf-8")
    loaded = load_vault(path)
    assert loaded["identity"]["full_name"] == 123


def test_unsupported_schema_version_raises(tmp_path):
    path = tmp_path / "vault.yaml"
    path.write_text("schema_version: '2.0'\nstatus: collecting\n", encoding="utf-8")
    with pytest.raises(VaultError) as error:
        load_vault(path)
    assert error.value.code == "vault.unsupported_version"


def test_merge_does_not_merge_different_roles_at_same_company():
    base = empty_vault()
    base["experience"] = [
        {"id": "exp_001", "company": "Acme", "title": {"en": "Intern"}, "start": "2025-06"}
    ]
    incoming = empty_vault()
    incoming["experience"] = [
        {"id": "exp_002", "company": "Acme", "title": {"en": "Engineer"}, "start": "2025-06"}
    ]
    merged = merge_vaults(base, incoming)
    assert len(merged["experience"]) == 2
