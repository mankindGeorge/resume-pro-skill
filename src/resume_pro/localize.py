# SPDX-License-Identifier: MIT
"""EN↔ZH transcreation from canonical facts, plus parity checks."""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import profile
from .application import application_dir, create_application, page_budget, save_application
from .errors import ResumeProError
from .paths import get_path, set_path
from .render import load_template
from .select import select_facts
from .writing import require_consent

MARKET_FOR_LOCALE = {"zh": "cn_internet", "en": "intl_en"}
# Units: 万/千 are unambiguous; latin k/m must not be the first letter of a word
# ("4 module" is 4, never 4 million).
NUMBER_TOKEN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(万|千|[kKmM](?![A-Za-z]))?")
CORE_PREFIXES = ("edu_", "exp_", "proj_", "skl_", "awd_", "cert_", "lang_", "pub_")


class LocalizeError(ResumeProError):
    pass


@dataclass
class LocaleGap:
    path: str
    fact_id: str | None
    field: str
    source_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "fact_id": self.fact_id,
            "field": self.field,
            "source_text": self.source_text,
            "question": f"Write the {self.field} in the target language; do not machine-translate rendered HTML.",
        }


@dataclass
class ParityReport:
    status: str
    source_slug: str
    target_slug: str
    facts_missing: list[str] = field(default_factory=list)
    facts_extra: list[str] = field(default_factory=list)
    bullets_missing: list[str] = field(default_factory=list)
    bullets_extra: list[str] = field(default_factory=list)
    number_mismatches: dict[str, list[str]] = field(default_factory=dict)
    date_mismatches: dict[str, list[str]] = field(default_factory=dict)
    entity_mismatches: dict[str, list[str]] = field(default_factory=dict)
    link_mismatches: dict[str, list[str]] = field(default_factory=dict)
    locale_gaps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_slug": self.source_slug,
            "target_slug": self.target_slug,
            "facts_missing": self.facts_missing,
            "facts_extra": self.facts_extra,
            "bullets_missing": self.bullets_missing,
            "bullets_extra": self.bullets_extra,
            "number_mismatches": self.number_mismatches,
            "date_mismatches": self.date_mismatches,
            "entity_mismatches": self.entity_mismatches,
            "link_mismatches": self.link_mismatches,
            "locale_gaps": self.locale_gaps,
            "notes": self.notes,
        }


@dataclass
class LocalizeResult:
    source_slug: str
    target_slug: str
    target_market: str
    target_locale: str
    application: dict[str, Any]
    application_path: Path
    parity_path: Path
    parity: ParityReport
    gaps: list[LocaleGap]
    render_vault: dict[str, Any]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_slug": self.source_slug,
            "target_slug": self.target_slug,
            "target_market": self.target_market,
            "target_locale": self.target_locale,
            "application": str(self.application_path),
            "parity_report": str(self.parity_path),
            "parity": self.parity.to_dict(),
            "gaps": [gap.to_dict() for gap in self.gaps],
            "warnings": self.warnings,
        }


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(str(v) for v in value.values() if v)
    return str(value or "")


def _missing(value: Any, locale: str) -> bool:
    if isinstance(value, dict):
        return not str(value.get(locale) or "").strip()
    return False


def _gaps_for_item(
    item: dict[str, Any],
    *,
    base_path: str,
    locale: str,
    source_locale: str,
    fields: tuple[str, ...],
    fact_id: str | None,
) -> list[LocaleGap]:
    gaps = []
    for key in fields:
        value = item.get(key)
        if isinstance(value, dict) and _missing(value, locale):
            gaps.append(
                LocaleGap(
                    path=f"{base_path}.{key}",
                    fact_id=fact_id,
                    field=key,
                    source_text=str(value.get(source_locale) or _text(value)),
                )
            )
    return gaps


def collect_gaps(vault: dict[str, Any], selection: dict[str, Any], *, locale: str, source_locale: str) -> list[LocaleGap]:
    fact_ids = set(selection.get("fact_ids") or [])
    bullet_ids = set(selection.get("bullet_ids") or [])
    gaps: list[LocaleGap] = []

    summary = selection.get("summary")
    if isinstance(summary, dict) and _missing(summary, locale):
        gaps.append(
            LocaleGap(
                path="selection.summary",
                fact_id="identity.summary",
                field="summary",
                source_text=str(summary.get(source_locale) or _text(summary)),
            )
        )

    for index, item in enumerate(vault.get("education") or []):
        if item.get("id") in fact_ids:
            gaps.extend(
                _gaps_for_item(item, base_path=f"education[{index}]", locale=locale, source_locale=source_locale, fields=("school", "degree", "major"), fact_id=item.get("id"))
            )
    for index, item in enumerate(vault.get("experience") or []):
        if item.get("id") not in fact_ids:
            continue
        gaps.extend(
            _gaps_for_item(item, base_path=f"experience[{index}]", locale=locale, source_locale=source_locale, fields=("title",), fact_id=item.get("id"))
        )
        for b_index, bullet in enumerate(item.get("bullets") or []):
            if bullet.get("id") in bullet_ids and _missing(bullet.get("text"), locale):
                gaps.append(
                    LocaleGap(
                        path=f"experience[{index}].bullets[{b_index}].text",
                        fact_id=bullet.get("id"),
                        field="bullet",
                        source_text=str((bullet.get("text") or {}).get(source_locale) or _text(bullet.get("text"))),
                    )
                )
    for index, item in enumerate(vault.get("projects") or []):
        if item.get("id") not in fact_ids:
            continue
        gaps.extend(
            _gaps_for_item(
                item,
                base_path=f"projects[{index}]",
                locale=locale,
                source_locale=source_locale,
                fields=("name", "role", "own_contribution", "optimizations", "outcome"),
                fact_id=item.get("id"),
            )
        )
        for b_index, bullet in enumerate(item.get("bullets") or []):
            if bullet.get("id") in bullet_ids and _missing(bullet.get("text"), locale):
                gaps.append(
                    LocaleGap(
                        path=f"projects[{index}].bullets[{b_index}].text",
                        fact_id=bullet.get("id"),
                        field="bullet",
                        source_text=str((bullet.get("text") or {}).get(source_locale) or _text(bullet.get("text"))),
                    )
                )
    for index, item in enumerate(vault.get("skills") or []):
        if item.get("id") in fact_ids:
            gaps.extend(
                _gaps_for_item(item, base_path=f"skills[{index}]", locale=locale, source_locale=source_locale, fields=("name",), fact_id=item.get("id"))
            )
            for item_index, sub in enumerate(item.get("items") or []):
                gaps.extend(
                    _gaps_for_item(sub, base_path=f"skills[{index}].items[{item_index}]", locale=locale, source_locale=source_locale, fields=("name",), fact_id=item.get("id"))
                )
    for collection in ("awards", "certificates", "languages"):
        for index, item in enumerate(vault.get(collection) or []):
            if item.get("id") in fact_ids:
                field_name = "title" if collection == "awards" else "name"
                gaps.extend(
                    _gaps_for_item(item, base_path=f"{collection}[{index}]", locale=locale, source_locale=source_locale, fields=(field_name,), fact_id=item.get("id"))
                )
    identity = vault.get("identity") or {}
    gaps.extend(
        _gaps_for_item(identity, base_path="identity", locale=locale, source_locale=source_locale, fields=("full_name",), fact_id="identity.full_name")
    )
    gaps.extend(
        _gaps_for_item(identity.get("location") or {}, base_path="identity.location", locale=locale, source_locale=source_locale, fields=("city", "region", "country"), fact_id="identity.location")
    )
    unique: dict[str, LocaleGap] = {}
    for gap in gaps:
        unique.setdefault(gap.path, gap)
    return list(unique.values())


def fill_markers(vault: dict[str, Any], gaps: list[LocaleGap], *, locale: str) -> dict[str, Any]:
    target = copy.deepcopy(vault)
    for gap in gaps:
        if gap.path == "selection.summary":
            continue
        current = get_path(target, gap.path)
        marker = f"[NEEDS {locale.upper()}] {gap.source_text}".strip()
        if isinstance(current, dict):
            updated = dict(current)
            updated[locale] = marker
            set_path(target, gap.path, updated)
        else:
            set_path(target, gap.path, marker)
    return target


def _normalized_numbers(texts: list[str]) -> list[str]:
    values: list[str] = []
    for text in texts:
        for raw_value, unit in NUMBER_TOKEN_RE.findall(text):
            value = float(raw_value)
            normalized_unit = (unit or "").lower()
            if normalized_unit == "万":
                value *= 10_000
            elif normalized_unit in {"千", "k"}:
                value *= 1_000
            elif normalized_unit == "m":
                value *= 1_000_000
            values.append(str(int(value)) if value.is_integer() else f"{value:g}")
    return sorted(values)


def _selected_bullet_texts(vault: dict[str, Any], application: dict[str, Any]) -> list[str]:
    locale = application["writing"]["locale"]
    selected = set(application["selection"].get("bullet_ids") or [])
    texts = []
    for section in ("experience", "projects"):
        for item in vault.get(section) or []:
            for bullet in item.get("bullets") or []:
                if bullet.get("id") in selected:
                    value = bullet.get("text") or {}
                    text = value.get(locale) if isinstance(value, dict) else value
                    if text:
                        texts.append(str(text))
    return texts


def _selected_entities(vault: dict[str, Any], application: dict[str, Any]) -> set[str]:
    selected = set(application["selection"].get("fact_ids") or [])
    values = set()
    for item in vault.get("experience") or []:
        if item.get("id") in selected and item.get("company"):
            values.add(str(item["company"]).strip().casefold())
    for item in vault.get("education") or []:
        if item.get("id") in selected and item.get("school"):
            values.add(_text(item["school"]).strip().casefold())
    for item in vault.get("projects") or []:
        if item.get("id") in selected and item.get("name"):
            values.add(_text(item["name"]).strip().casefold())
    return values


def _selected_dates(vault: dict[str, Any], application: dict[str, Any]) -> set[tuple[str, str]]:
    selected = set(application["selection"].get("fact_ids") or [])
    dates = set()
    for section in ("education", "experience", "projects"):
        for item in vault.get(section) or []:
            if item.get("id") in selected:
                start = str(item.get("start") or "")
                end = str(item.get("end") or "")
                if start or end:
                    dates.add((start, end))
    return dates


def _selected_links(vault: dict[str, Any], application: dict[str, Any]) -> set[str]:
    selected = set(application["selection"].get("fact_ids") or [])
    links = set()
    for link in (vault.get("identity") or {}).get("links") or []:
        if link.get("url"):
            links.add(str(link["url"]))
    for item in vault.get("projects") or []:
        if item.get("id") in selected:
            for link in item.get("links") or []:
                if link.get("url"):
                    links.add(str(link["url"]))
    return links


def _core_facts(application: dict[str, Any]) -> set[str]:
    return {
        fact_id
        for fact_id in application["selection"].get("fact_ids") or []
        if fact_id.startswith(CORE_PREFIXES)
    }


def compare(
    vault: dict[str, Any],
    source_app: dict[str, Any],
    target_app: dict[str, Any],
    *,
    gaps: list[LocaleGap] | None = None,
) -> ParityReport:
    gaps = gaps or []
    source_facts = _core_facts(source_app)
    target_facts = _core_facts(target_app)
    source_bullets = set(source_app["selection"].get("bullet_ids") or [])
    target_bullets = set(target_app["selection"].get("bullet_ids") or [])
    source_texts = _selected_bullet_texts(vault, source_app)
    target_texts = _selected_bullet_texts(vault, target_app)
    source_numbers = _normalized_numbers(source_texts)
    target_numbers = _normalized_numbers(target_texts)
    source_dates = _selected_dates(vault, source_app)
    target_dates = _selected_dates(vault, target_app)
    source_entities = _selected_entities(vault, source_app)
    target_entities = _selected_entities(vault, target_app)
    source_links = _selected_links(vault, source_app)
    target_links = _selected_links(vault, target_app)

    report = ParityReport(
        status="pass",
        source_slug=source_app["slug"],
        target_slug=target_app["slug"],
        facts_missing=sorted(source_facts - target_facts),
        facts_extra=sorted(target_facts - source_facts),
        bullets_missing=sorted(source_bullets - target_bullets),
        bullets_extra=sorted(target_bullets - source_bullets),
        number_mismatches={
            "missing_in_target": sorted(set(source_numbers) - set(target_numbers)),
            "extra_in_target": sorted(set(target_numbers) - set(source_numbers)),
        }
        if source_numbers != target_numbers
        else {},
        date_mismatches={
            "missing_in_target": sorted(f"{a}–{b}" for a, b in source_dates - target_dates),
            "extra_in_target": sorted(f"{a}–{b}" for a, b in target_dates - source_dates),
        }
        if source_dates != target_dates
        else {},
        entity_mismatches={
            "missing_in_target": sorted(source_entities - target_entities),
            "extra_in_target": sorted(target_entities - source_entities),
        }
        if source_entities != target_entities
        else {},
        link_mismatches={
            "missing_in_target": sorted(source_links - target_links),
            "extra_in_target": sorted(target_links - source_links),
        }
        if source_links != target_links
        else {},
        locale_gaps=[gap.path for gap in gaps],
        notes=[],
    )
    failures = (
        report.facts_missing
        or report.facts_extra
        or report.number_mismatches
        or report.date_mismatches
        or report.entity_mismatches
        or report.locale_gaps
    )
    if failures:
        report.status = "fail"
    if report.bullets_missing or report.bullets_extra:
        report.notes.append("Bullet differences may come from page budgets; review them before submitting.")
    if report.link_mismatches:
        report.notes.append("Link sets differ; confirm which links belong in the target-market resume.")
    if not report.notes:
        report.notes.append("Facts, numbers, dates, entities, and core selections match.")
    return report


def localize_application(
    root: Path,
    vault: dict[str, Any],
    source_app: dict[str, Any],
    *,
    target_locale: str,
    target_market: str | None = None,
    target_role: str | None = None,
    template_id: str | None = None,
    framework: str | None = None,
    draft: bool = False,
) -> LocalizeResult:
    if target_locale not in ("en", "zh"):
        raise LocalizeError(
            "localize.invalid_locale",
            f"Unsupported target locale {target_locale!r}.",
            fix="Use `--to en` or `--to zh`.",
        )
    market = target_market or MARKET_FOR_LOCALE[target_locale]
    market_profile = profile.load_market(market)
    if market_profile.get("language") != target_locale:
        raise LocalizeError(
            "localize.market_language_mismatch",
            f"Market {market!r} uses {market_profile.get('language')!r}, not {target_locale!r}.",
            fix="Choose a market whose profile language matches the target locale.",
        )
    source_locale = source_app["writing"]["locale"]
    if source_locale == target_locale:
        raise LocalizeError(
            "localize.same_locale",
            f"The source application is already in {target_locale!r}.",
            fix="Choose the other locale or create a new application for a different market.",
        )
    persona = source_app["persona"]
    role = target_role or (source_app.get("target") or {}).get("role")
    if not role:
        raise LocalizeError(
            "localize.role_missing",
            "A target role is required.",
            fix="Pass --role with the target-language role title.",
        )
    chosen_framework = framework or source_app["writing"]["framework"]
    require_consent(chosen_framework, True)
    chosen_template = template_id or source_app["template"]["id"]
    # Preserve the layout, including learned layouts when a target variant exists.
    # Fail before saving anything rather than silently substituting another design.
    load_template(chosen_template, root=root, language=target_locale)

    budget = page_budget(market, persona)
    target_selection = select_facts(
        vault,
        market=market,
        persona=persona,
        target_role=role,
        page_max=budget["max"],
    )
    gaps = collect_gaps(vault, target_selection, locale=target_locale, source_locale=source_locale)
    if gaps and not draft:
        raise LocalizeError(
            "localize.locale_gaps",
            f"{len(gaps)} fact(s) have no {target_locale!r} text.",
            fix="Write the target-language facts in the vault; never machine-translate rendered text. Or use --draft to see the gaps marked.",
            details={"gaps": [gap.to_dict() for gap in gaps]},
        )
    render_vault = fill_markers(vault, gaps, locale=target_locale) if gaps else vault
    if gaps:
        for gap in gaps:
            if gap.path == "selection.summary":
                summary = dict(target_selection.get("summary") or {})
                summary[target_locale] = f"[NEEDS {target_locale.upper()}] {gap.source_text}".strip()
                target_selection["summary"] = summary
        render_vault.setdefault("needs_confirmation", []).extend(
            {
                "path": gap.path,
                "reason": f"Missing {target_locale!r} text; marked in draft.",
                "severity": "blocker",
                "question": f"Write the target-language text for {gap.path}.",
                "resolved": False,
            }
            for gap in gaps
        )

    target_slug = f"{source_app['slug']}-{target_locale}"
    application = create_application(
        vault=vault,
        selection=target_selection,
        role=role,
        market=market,
        persona=persona,
        framework=chosen_framework,
        company=(source_app.get("target") or {}).get("company"),
        template_id=chosen_template,
        slug=target_slug,
    )
    application_dir(root, target_slug).mkdir(parents=True, exist_ok=True)
    parity_path = application_dir(root, target_slug) / "parity.json"
    parity = compare(vault, source_app, application, gaps=gaps)
    application["localization"] = {
        "source_locale": source_locale,
        "target_locale": target_locale,
        "parity_status": parity.status,
        "parity_report": str(parity_path),
        "source_application": source_app["slug"],
    }
    path = save_application(root, application)
    parity_path.write_text(json.dumps(parity.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    warnings = []
    if gaps:
        warnings.append(f"{len(gaps)} target-locale fact(s) are marked as missing in the draft.")
    if not target_role:
        warnings.append("The target role was copied from the source application; confirm it is in the target language.")
    return LocalizeResult(
        source_slug=source_app["slug"],
        target_slug=target_slug,
        target_market=market,
        target_locale=target_locale,
        application=application,
        application_path=path,
        parity_path=parity_path,
        parity=parity,
        gaps=gaps,
        render_vault=render_vault,
        warnings=warnings,
    )
