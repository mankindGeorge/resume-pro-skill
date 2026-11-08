# SPDX-License-Identifier: MIT
"""Redaction coverage: PII key variants, free-text phone/email/ID, and safety."""

from __future__ import annotations

import pytest

from resume_pro.redact import REDACTED, redact_pii


PHONE_KEYS = (
    "phone",
    "phone_number",
    "tel",
    "telephone",
    "telephone_number",
    "mobile",
    "mobile_number",
    "mobile_phone",
    "cell",
    "cellphone",
    "cell_phone",
)


@pytest.mark.parametrize("key", PHONE_KEYS)
def test_phone_key_variants_are_redacted(key):
    assert redact_pii({key: "+86 137 0000 0000"})[key] == REDACTED


def test_phone_keys_match_case_insensitively():
    assert redact_pii({"Phone_Number": "13700000000"})["Phone_Number"] == REDACTED
    assert redact_pii({"TEL": "010-12345678"})["TEL"] == REDACTED


def test_names_and_cities_are_preserved():
    data = {"full_name": "Li Ming", "name": "Li Ming", "city": "Beijing", "email": "a@b.com"}
    out = redact_pii(data)
    assert out["full_name"] == "Li Ming"
    assert out["name"] == "Li Ming"
    assert out["city"] == "Beijing"
    assert out["email"] == REDACTED


@pytest.mark.parametrize(
    "phone",
    (
        "+86 137 0000 0000",
        "+8613700000000",
        "13700000000",
        "13800138000",
        "137-0000-0000",
        "137 0000 0000",
        "(555) 123-4567",
        "555-123-4567",
        "+1-555-123-4567",
        "010-12345678",
    ),
)
def test_free_text_phones_are_redacted(phone):
    out = redact_pii(f"Reach me at {phone} anytime.")
    assert phone not in out
    assert REDACTED in out


def test_free_text_email_and_cn_id_are_redacted():
    assert redact_pii("mail liming@example.com ok") == f"mail {REDACTED} ok"
    assert redact_pii("id 110101199001011234 end") == f"id {REDACTED} end"
    assert redact_pii("id 11010119900101123X end") == f"id {REDACTED} end"


@pytest.mark.parametrize(
    "text",
    (
        "2023-09 to 2027-06",
        "2023-09-01",
        "2023.09.01",
        "2026-06 to 2026-09",
        "Cut P95 latency from 480ms to 190ms across 300K daily requests",
        "owned a service handling 4M daily transactions",
        "Reduced manual work by 6 hours per week",
        "Led 9 engineers; owned a service handling 4M daily transactions",
        "Recall@5 improved from 0.61 to 0.82",
        "GPA 3.8/4.0, ranked 5/120",
        "100% remote, 1.2s build time",
        "body font is 10.5pt across 2 pages",
    ),
)
def test_phone_regex_does_not_touch_dates_or_metrics(text):
    assert redact_pii(text) == text


def test_nested_structures_are_redacted():
    data = {
        "identity": {"email": "a@b.com", "phone_number": "13700000000", "full_name": "Li Ming"},
        "notes": ["call 555-123-4567", {"tel": "010-12345678"}],
    }
    out = redact_pii(data)
    assert out["identity"]["email"] == REDACTED
    assert out["identity"]["phone_number"] == REDACTED
    assert out["identity"]["full_name"] == "Li Ming"
    assert out["notes"][0] == f"call {REDACTED}"
    assert out["notes"][1]["tel"] == REDACTED


def test_empty_pii_values_are_preserved():
    assert redact_pii({"phone": None})["phone"] is None
    assert redact_pii({"phone": ""})["phone"] == ""
    assert redact_pii({"email": []})["email"] == []


def test_non_string_scalars_pass_through():
    assert redact_pii(42) == 42
    assert redact_pii(True) is True
    assert redact_pii(None) is None