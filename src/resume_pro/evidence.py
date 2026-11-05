# SPDX-License-Identifier: MIT
"""Evidence registry, bullet creation, and no-fabrication checks."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from .errors import Issue, ValidationResult
from .vault import iter_bullets, next_id

EVIDENCE_STATUSES = ("verified", "user_asserted", "estimated", "unknown")
EVIDENCE_SOURCES = ("user_statement", "document", "portfolio", "repo", "certificate", "inference")
WEAK_STATUSES = ("estimated", "unknown")

_URL_RE = re.compile(r"https?://[^\s,，;；]+", re.IGNORECASE)
_DIGIT_RE = re.compile(r"\d")

_FABRICATION_PATTERNS = (
    "make something up",
    "make it up",
    "make up a",
    "fake it",
    "fabricate",
    "just invent",
    "编一个",
    "随便写",
    "瞎编",
    "不用真实",
    "造一个",
)


def assert_no_fabrication(text: str) -> None:
    from .errors import IntakeError

    lowered = text.lower()
    for pattern in _FABRICATION_PATTERNS:
        if pattern in lowered:
            raise IntakeError(
                "intake.fabrication_refused",
                "I cannot invent experience, projects, or numbers.",
                fix=(
                    "Give the real fact, or say `skip` and we will leave the gap. "
                    "A smaller true detail is always better than a bigger invented one."
                ),
            )


def infer_source(text: str) -> tuple[str, str | None]:
    match = _URL_RE.search(text)
    if not match:
        return "user_statement", None
    url = match.group(0)
    if "github.com" in url or "gitlab.com" in url:
        return "repo", url
    return "portfolio", url


def add_evidence(
    vault: dict[str, Any],
    claim: str,
    *,
    source: str = "user_statement",
    status: str = "user_asserted",
    locator: str | None = None,
    notes: str | None = None,
) -> str:
    if status not in EVIDENCE_STATUSES:
        raise ValueError(f"unknown evidence status: {status}")
    if source not in EVIDENCE_SOURCES:
        raise ValueError(f"unknown evidence source: {source}")
    evidence_id = next_id(vault, "ev")
    entry: dict[str, Any] = {
        "id": evidence_id,
        "claim": claim,
        "status": status,
        "source": source,
        "captured_at": date.today().isoformat(),
    }
    if locator:
        entry["locator"] = locator
    if notes:
        entry["notes"] = notes
    vault.setdefault("evidence", {})[evidence_id] = entry
    return evidence_id


def _localized(text: str, lang: str) -> dict[str, str]:
    return {lang: text}


def upsert_bullet(
    vault: dict[str, Any],
    collection: str,
    parent_index: int,
    bullet_index: int,
    text: str,
    *,
    lang: str = "en",
    source: str = "user_statement",
    locator: str | None = None,
) -> dict[str, Any]:
    """Create or update a bullet and its evidence entry."""
    if collection not in ("experience", "projects"):
        raise ValueError(f"unsupported collection: {collection}")
    items = vault.get(collection) or []
    if parent_index >= len(items):
        raise IndexError(f"{collection}[{parent_index}] does not exist")
    parent = items[parent_index]
    bullets = parent.setdefault("bullets", [])
    parent_id = parent.get("id") or next_id(vault, "exp" if collection == "experience" else "proj")
    parent["id"] = parent_id
    bullet_id = f"bul_{parent_id}_{bullet_index + 1}"
    existing = next((b for b in bullets if b.get("id") == bullet_id), None)
    evidence_id = None
    if existing and existing.get("evidence"):
        evidence_id = existing["evidence"][0]
        entry = (vault.get("evidence") or {}).get(evidence_id)
        if entry is not None:
            entry["claim"] = text
            if source != "user_statement":
                entry["source"] = source
            if locator:
                entry["locator"] = locator
    if evidence_id is None:
        evidence_id = add_evidence(vault, text, source=source, status="user_asserted", locator=locator)
    bullet = {
        "id": bullet_id,
        "text": _localized(text, lang),
        "evidence": [evidence_id],
        "skill_ids": existing.get("skill_ids", []) if existing else [],
    }
    if existing is None:
        bullets.append(bullet)
    else:
        existing.update(bullet)
    return bullet


def _text_of(bullet: dict[str, Any]) -> str:
    text = bullet.get("text") or {}
    if isinstance(text, dict):
        return " ".join(str(v) for v in text.values())
    return str(text)


def has_digits(text: str) -> bool:
    return bool(_DIGIT_RE.search(text))


def validate_evidence(vault: dict[str, Any]) -> ValidationResult:
    result = ValidationResult()
    registry = vault.get("evidence") or {}

    for path, bullet in iter_bullets(vault):
        refs = bullet.get("evidence") or []
        if not refs:
            result.issues.append(
                Issue(
                    code="evidence.missing",
                    path=f"{path}.evidence",
                    message="This bullet has no evidence entry.",
                    fix="Link a user_asserted evidence entry rather than leaving the claim unsourced.",
                )
            )
            continue
        statuses = []
        for ref in refs:
            entry = registry.get(ref)
            if entry is None:
                result.issues.append(
                    Issue(
                        code="evidence.unknown_ref",
                        path=f"{path}.evidence",
                        message=f"Evidence id {ref!r} does not exist.",
                        fix="Add the evidence entry or remove the reference.",
                    )
                )
            else:
                statuses.append(entry.get("status"))
        text = _text_of(bullet)
        if has_digits(text) and statuses and all(s in WEAK_STATUSES for s in statuses):
            result.issues.append(
                Issue(
                    code="evidence.unsupported_number",
                    path=f"{path}.text",
                    message="This bullet contains a number, but every linked source is estimated or unknown.",
                    fix="Attach a verified or user-asserted source, or remove the number.",
                )
            )

    summary = (vault.get("identity") or {}).get("summary") or {}
    summary_text = " ".join(str(v) for v in summary.values()) if isinstance(summary, dict) else str(summary)
    if summary_text and has_digits(summary_text):
        refs = (vault.get("identity") or {}).get("summary_evidence") or []
        statuses = [registry.get(r, {}).get("status") for r in refs]
        if not refs or all(s in WEAK_STATUSES for s in statuses):
            result.issues.append(
                Issue(
                    code="evidence.unsupported_number",
                    path="identity.summary",
                    message="The summary contains a number without a verified or user-asserted source.",
                    fix="Link summary_evidence or remove the number.",
                )
            )

    for key, entry in registry.items():
        if not isinstance(entry, dict):
            continue
        if entry.get("source") == "inference" and entry.get("status") in ("verified", "user_asserted"):
            result.issues.append(
                Issue(
                    code="evidence.inference_promoted",
                    path=f"evidence.{key}.status",
                    message="Inference cannot be presented as verified or user-asserted.",
                    fix="Use status estimated/unknown, or replace the inference with a real source.",
                )
            )
        if entry.get("status") == "verified" and not entry.get("locator"):
            result.issues.append(
                Issue(
                    code="evidence.verified_without_locator",
                    path=f"evidence.{key}.locator",
                    message="A verified source has no locator, so it cannot be checked.",
                    severity="warning",
                    fix="Add a file, URL, page, or certificate id.",
                )
            )
    return result
