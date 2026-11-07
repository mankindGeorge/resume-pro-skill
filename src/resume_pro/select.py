# SPDX-License-Identifier: MIT
"""Fact selection and ordering for one application."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from . import profile

DEFAULT_SECTION_ORDER = (
    "summary",
    "education",
    "experience",
    "projects",
    "skills",
    "awards",
    "certificates",
    "languages",
    "publications",
    "open_source",
)

WEAK_WORDS = re.compile(
    r"^(worked on|responsible for|helped|participated in|assisted|involved in|负责|参与|协助|配合)",
    re.IGNORECASE,
)


def _localized(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(str(v) for v in value.values() if v)
    return str(value or "")


def _norm(value: str) -> str:
    return " ".join(value.lower().split())


def _order_key(market_profile: dict[str, Any], persona: str) -> str:
    order = market_profile.get("section_order") or {}
    if persona == "academic" and "academic" in order:
        return "academic"
    if profile.is_student(persona):
        if "campus" in order:
            return "campus"
        if "student" in order:
            return "student"
    if persona == "senior_manager" and "senior" in order:
        return "senior"
    if "experienced" in order:
        return "experienced"
    if "student" in order:
        return "student"
    return next(iter(order), "")


def _section_order(market: str, persona: str) -> list[str]:
    market_profile = profile.load_market(market)
    key = _order_key(market_profile, persona)
    order = list((market_profile.get("section_order") or {}).get(key) or [])
    if not order:
        order = list(DEFAULT_SECTION_ORDER)
    if persona == "academic":
        return order
    if profile.is_student(persona):
        priority = ["education", "experience", "projects"]
    else:
        priority = ["summary", "experience", "projects", "education", "skills"]
    return priority + [section for section in order if section not in priority]


def _bullet_text(bullet: dict[str, Any]) -> str:
    return _localized(bullet.get("text"))


def _evidence_strength(bullet: dict[str, Any], registry: dict[str, Any]) -> float:
    refs = bullet.get("evidence") or []
    statuses = [registry.get(ref, {}).get("status") for ref in refs]
    if "verified" in statuses:
        return 2.0
    if "user_asserted" in statuses:
        return 1.0
    return 0.0


def _bullet_score(bullet: dict[str, Any], registry: dict[str, Any], jd_terms: set[str]) -> float:
    text = _bullet_text(bullet)
    lowered = _norm(text)
    score = _evidence_strength(bullet, registry)
    if re.search(r"\d", text):
        score += 1.5
    matches = sum(1 for term in jd_terms if term and term in lowered)
    score += min(4.0, matches * 1.5)
    if 40 <= len(text) <= 220:
        score += 0.5
    if WEAK_WORDS.search(text):
        score -= 1.0
    return score


def _fact_text(item: dict[str, Any]) -> str:
    parts = [
        _localized(item.get("company")),
        _localized(item.get("title")),
        _localized(item.get("name")),
        _localized(item.get("role")),
        _localized(item.get("own_contribution")),
        _localized(item.get("outcome")),
        " ".join(str(x) for x in item.get("tech") or []),
        " ".join(_bullet_text(b) for b in item.get("bullets") or []),
    ]
    return _norm(" ".join(str(p) for p in parts if p))


def _fact_score(item: dict[str, Any], registry: dict[str, Any], jd_terms: set[str], target_role: str | None = None) -> float:
    score = sum(_bullet_score(b, registry, jd_terms) for b in item.get("bullets") or [])
    text = _fact_text(item)
    score += min(4.0, sum(1.5 for term in jd_terms if term and term in text))
    end = str(item.get("end") or "")
    if end == "present":
        score += 2.0
    elif end[:4].isdigit():
        year = int(end[:4])
        if year >= datetime.now().year - 3:
            score += 1.0
    if item.get("own_contribution") or item.get("outcome"):
        score += 1.0
    preferred = _norm(target_role or "")
    roles = [_norm(role) for role in item.get("target_roles") or []]
    if preferred in {"general application", "target role"}:
        preferred = ""
    if preferred and roles:
        score += 3.0 if any(preferred in role or role in preferred for role in roles) else -1.0
    return score


def _pick_bullets(
    item: dict[str, Any],
    registry: dict[str, Any],
    jd_terms: set[str],
    limit: int,
    dropped: list[dict[str, Any]],
    parent_id: str,
) -> list[str]:
    bullets = item.get("bullets") or []
    ranked = sorted(
        enumerate(bullets),
        key=lambda pair: (-_bullet_score(pair[1], registry, jd_terms), pair[0]),
    )
    selected = [bullet for _, bullet in ranked[:limit]]
    for _, bullet in ranked[limit:]:
        dropped.append(
            {
                "fact_id": bullet.get("id") or parent_id,
                "reason": "Dropped to fit the page budget; lower relevance or weaker evidence.",
            }
        )
    return [b["id"] for b in selected if b.get("id")]


def select_facts(
    vault: dict[str, Any],
    *,
    market: str,
    persona: str,
    target_role: str | None = None,
    jd_terms: set[str] | None = None,
    page_max: int | None = None,
) -> dict[str, Any]:
    jd_terms = {_norm(term) for term in (jd_terms or set()) if term}
    registry = vault.get("evidence") or {}
    is_student = profile.is_student(persona)
    max_roles = 2 if page_max == 1 else 3 if is_student else 5
    max_projects = 2 if page_max == 1 else 3 if is_student else 2
    max_bullets_role = 3 if page_max == 1 else 4 if is_student else 5
    max_bullets_project = 2 if page_max == 1 else 3
    max_skills = 12 if market.startswith("cn_") else 16

    dropped: list[dict[str, Any]] = []
    fact_ids: list[str] = []
    bullet_ids: list[str] = []

    # Roles: rank to select, then display in reverse chronological order.
    experiences = vault.get("experience") or []
    ranked_exp = sorted(
        enumerate(experiences),
        key=lambda pair: (-_fact_score(pair[1], registry, jd_terms, target_role), pair[0]),
    )
    selected_exp_indices = sorted(index for index, _ in ranked_exp[:max_roles])
    for index, item in ranked_exp[max_roles:]:
        dropped.append(
            {
                "fact_id": item.get("id") or f"experience[{index}]",
                "reason": "Older or less relevant than the roles kept for this page budget.",
            }
        )
    for index in selected_exp_indices:
        item = experiences[index]
        if item.get("id"):
            fact_ids.append(item["id"])
        bullet_ids.extend(
            _pick_bullets(
                item,
                registry,
                jd_terms,
                max_bullets_role,
                dropped,
                item.get("id") or f"experience[{index}]",
            )
        )

    # Projects: rank and keep the strongest.
    projects = vault.get("projects") or []
    ranked_proj = sorted(
        enumerate(projects),
        key=lambda pair: (-_fact_score(pair[1], registry, jd_terms, target_role), pair[0]),
    )
    selected_proj_indices = [index for index, _ in ranked_proj[:max_projects]]
    for index, item in ranked_proj[max_projects:]:
        dropped.append(
            {
                "fact_id": item.get("id") or f"projects[{index}]",
                "reason": "Lower relevance than the projects kept for this page budget.",
            }
        )
    for index in selected_proj_indices:
        item = projects[index]
        if item.get("id"):
            fact_ids.append(item["id"])
        bullet_ids.extend(
            _pick_bullets(
                item,
                registry,
                jd_terms,
                max_bullets_project,
                dropped,
                item.get("id") or f"projects[{index}]",
            )
        )

    # Education and other sections.
    for item in vault.get("education") or []:
        if item.get("id"):
            fact_ids.append(item["id"])
    for collection in ("awards", "certificates", "languages", "publications"):
        for item in vault.get(collection) or []:
            if item.get("id"):
                fact_ids.append(item["id"])

    # Skills: fundamentals first for CN campus, then AI, then the rest.
    skill_groups = vault.get("skills") or []
    priority = {"fundamentals": 0, "ai_ml": 1, "language": 2, "framework": 3, "database": 4, "platform": 5, "tool": 6, "other": 7}
    ordered_groups = sorted(skill_groups, key=lambda g: priority.get(g.get("kind"), 9))
    kept_skill_items = 0
    skill_item_indices: dict[str, list[int]] = {}
    for group in ordered_groups:
        group_id = group.get("id")
        if group_id:
            fact_ids.append(group_id)
        kept_indices: list[int] = []
        for index, item in enumerate(group.get("items") or []):
            kept_skill_items += 1
            if kept_skill_items > max_skills:
                dropped.append(
                    {
                        "fact_id": item.get("name") or group.get("id") or "skill",
                        "reason": "Skill list trimmed to the template budget.",
                    }
                )
            else:
                kept_indices.append(index)
        if group_id:
            skill_item_indices[group_id] = kept_indices

    summary = _localized((vault.get("identity") or {}).get("summary")).strip() or None
    summary_evidence = (vault.get("identity") or {}).get("summary_evidence") or []
    if summary and not summary_evidence:
        dropped.append(
            {
                "fact_id": "identity.summary",
                "reason": "Summary omitted because it has no evidence reference.",
            }
        )
        summary = None

    ordered_sections = _section_order(market, persona)
    preferred_sections = set(ordered_sections)
    known = set(DEFAULT_SECTION_ORDER)
    for section in ordered_sections:
        if section not in known:
            ordered_sections = [s for s in ordered_sections if s != section]
    for section in DEFAULT_SECTION_ORDER:
        if section not in ordered_sections:
            ordered_sections.append(section)

    enabled_map = {
        "summary": bool(summary) and "summary" in preferred_sections,
        "education": bool(vault.get("education")),
        "experience": bool(experiences),
        "projects": bool(projects),
        "skills": bool(skill_groups),
        "awards": bool(vault.get("awards")),
        "certificates": bool(vault.get("certificates")),
        "languages": bool(vault.get("languages")),
        "publications": bool(vault.get("publications")),
        "open_source": any(project.get("context") == "open_source" for project in projects),
    }

    sections = [
        {"id": section_id, "enabled": enabled_map.get(section_id, False), "order": order}
        for order, section_id in enumerate(ordered_sections, start=1)
    ]

    selection: dict[str, Any] = {
        "sections": sections,
        "fact_ids": list(dict.fromkeys(fact_ids)),
        "bullet_ids": list(dict.fromkeys(bullet_ids)),
        "skill_item_indices": skill_item_indices,
        "dropped": dropped,
    }
    if summary and enabled_map["summary"]:
        selection["summary"] = (vault.get("identity") or {}).get("summary")
        if summary_evidence:
            selection["summary_evidence"] = summary_evidence
    return selection
