# SPDX-License-Identifier: MIT
"""Content linter: global rules plus Chinese-market rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import profile
from .application import page_budget
from .layout import content_lines, pages_from_lines
from .skim import SkimResult, skim_test

AI_TERMS = re.compile(
    r"\b(ai|llm|rag|aigc|agent|prompt|transformer|deep learning|machine learning|nlp|cv)\b|大模型|人工智能|机器学习|深度学习|检索增强",
    re.IGNORECASE,
)
WEAK_START = re.compile(
    r"^(worked on|responsible for|helped|participated in|assisted|involved in|负责|参与|协助|配合)",
    re.IGNORECASE,
)
SUPERLATIVES = re.compile(
    r"\b(best|world-class|cutting-edge|revolutionary|unparalleled)\b|第一|顶尖|颠覆|革命性",
    re.IGNORECASE,
)
CLICHES = (
    "具有良好的沟通能力",
    "团队合作精神",
    "学习能力强",
    "吃苦耐劳",
    "责任心强",
    "积极主动",
    "熟练掌握",
    "精通",
    "passionate about",
    "team player",
    "hard-working",
    "detail-oriented",
    "self-starter",
    "excellent communication skills",
)
PLACEHOLDER_RE = re.compile(r"example\.com|your-domain|yourdomain|xxx|todo|placeholder", re.IGNORECASE)
FIRST_PERSON = re.compile(r"^(i|my)\b|我的|本人", re.IGNORECASE)

# Per-locale bullet length limits from SKILL.md Writing rules (hard errors).
BULLET_CHAR_LIMITS = {"en": 240, "zh": 140}

# A leading point label is exactly what render.py renders bold: a short prefix
# ending in a full-width or ASCII colon. Keep this pattern in sync with
# render._LEADING_LABEL_RE.
_POINT_LABEL_RE = re.compile(r"^([^：:。.!?!?,，;；/]{1,30}[：:])")

# Packaging recipes from references/writing-engine.md §2. Each framework maps
# to an ordered tuple of slots; a slot is (zh labels, en labels, is_result).
# The first listed label is canonical; extras are accepted aliases. The result
# slot must carry a number. `user_voice` has no fixed recipe: the user's own
# labels and order are kept, and only non-empty point content is checked.
FRAMEWORK_RECIPES: dict[str, tuple[tuple[tuple[str, ...], tuple[str, ...], bool], ...]] = {
    "star": (
        (("项目背景：",), ("Background:",), False),
        (("核心框架：",), ("Framework:",), False),
        (("解决方案：", "难点："), ("Solution:", "Challenge:"), False),
        (("核心成果：",), ("Outcome:",), True),
    ),
    "xyz": (
        (("核心成果：",), ("Outcome:",), True),
        (("衡量口径：",), ("Measure:",), False),
        (("实现做法：",), ("Approach:",), False),
    ),
    "fab": (
        (("核心能力：",), ("Capability:",), False),
        (("技术优势：",), ("Advantage:",), False),
        (("实际收益：",), ("Benefit:",), True),
    ),
    "car": (
        (("难点：",), ("Challenge:",), False),
        (("解决方案：",), ("Solution:",), False),
        (("核心成果：",), ("Outcome:",), True),
    ),
    "result_first": (
        (("核心成果：",), ("Outcome:",), True),
        (("解决方案：",), ("Solution:",), False),
        (("项目背景：",), ("Background:",), False),
    ),
}


@dataclass
class LintIssue:
    code: str
    severity: str  # error | warn | info
    path: str
    message: str
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
            "fix": self.fix,
        }


@dataclass
class LintReport:
    issues: list[LintIssue]
    skim: SkimResult
    page_estimate: int
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[LintIssue]:
        return [i for i in self.issues if i.severity == "warn"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "page_estimate": self.page_estimate,
            "counts": self.counts,
            "skim": self.skim.to_dict(),
            "issues": [i.to_dict() for i in self.issues],
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
        }


def _text(bullet: dict[str, Any]) -> str:
    return " ".join(str(v) for v in (bullet.get("text") or {}).values() if v)


def _has_digit(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _iter_bullets(vault: dict[str, Any]):
    for collection in ("experience", "projects"):
        for index, item in enumerate(vault.get(collection) or []):
            for b_index, bullet in enumerate(item.get("bullets") or []):
                yield f"{collection}[{index}].bullets[{b_index}]", bullet, item


def _summary_text(vault: dict[str, Any]) -> str:
    summary = (vault.get("identity") or {}).get("summary") or {}
    if isinstance(summary, dict):
        return " ".join(str(v) for v in summary.values() if v)
    return str(summary or "")


def _estimate_pages(vault: dict[str, Any], application: dict[str, Any] | None) -> int:
    """Estimate pages with layout's single estimator on the rendered content.

    When the application declares a selection (fact_ids), estimate exactly what
    the renderer will render; otherwise fall back to the whole vault. Sharing
    layout.content_lines keeps lint and render page decisions consistent.
    """
    app = application or {}
    locale = (app.get("writing") or {}).get("locale")
    if not locale:
        locale = "zh" if str(app.get("market", "")).startswith("cn_") else "en"
    selection = app.get("selection") or {}
    fact_ids = set(selection.get("fact_ids") or [])
    bullet_ids = set(selection.get("bullet_ids") or [])
    skill_item_indices = selection.get("skill_item_indices") or {}

    def localized(value: Any) -> str:
        if isinstance(value, dict):
            if value.get(locale):
                return str(value[locale])
            return next((str(v) for v in value.values() if v), "")
        return str(value or "")

    def kept(item: dict[str, Any]) -> bool:
        return not fact_ids or item.get("id") in fact_ids

    def bullet_texts(item: dict[str, Any]) -> list[str]:
        return [
            localized(bullet.get("text"))
            for bullet in item.get("bullets") or []
            if not bullet_ids or bullet.get("id") in bullet_ids
        ]

    # Mirror build_render_model: with a declared selection the summary comes
    # from the selection (absent means the section is disabled); without one,
    # the vault summary is the best available estimate.
    summary_source = selection.get("summary") if fact_ids else (vault.get("identity") or {}).get("summary")
    projects = [item for item in vault.get("projects") or [] if kept(item)]
    skills = []
    for group in vault.get("skills") or []:
        if not kept(group):
            continue
        items = group.get("items") or []
        kept_indices = skill_item_indices.get(group.get("id"))
        if kept_indices is not None:
            items = [items[i] for i in kept_indices if 0 <= i < len(items)]
        skills.append({"items": [item for item in items if item.get("name")]})
    model = {
        "locale": locale,
        "summary": localized(summary_source),
        "education": [item for item in vault.get("education") or [] if kept(item)],
        "experience": [{"bullets": bullet_texts(item)} for item in vault.get("experience") or [] if kept(item)],
        "projects": [{"bullets": bullet_texts(item)} for item in projects],
        "skills": skills,
        "awards": [item for item in vault.get("awards") or [] if kept(item) and localized(item.get("title"))],
        "certificates": [item for item in vault.get("certificates") or [] if kept(item)],
        "languages": [item for item in vault.get("languages") or [] if kept(item)],
        "publications": [item for item in vault.get("publications") or [] if kept(item)],
        "open_source": [item for item in projects if item.get("context") == "open_source"],
    }
    return pages_from_lines(content_lines(model))


def _label_key(label: str) -> str:
    return label.rstrip("：:").lower()


def _recipe_label_maps(recipe) -> dict[str, dict[str, tuple[int, str]]]:
    """Map normalized label -> (slot index, canonical label) per locale."""
    maps: dict[str, dict[str, tuple[int, str]]] = {}
    for locale in ("zh", "en"):
        mapping: dict[str, tuple[int, str]] = {}
        for slot_index, (zh_labels, en_labels, _is_result) in enumerate(recipe):
            for label in zh_labels if locale == "zh" else en_labels:
                mapping[_label_key(label)] = (slot_index, label)
        maps[locale] = mapping
    return maps


def _recipe_order_text(recipe, locale: str) -> str:
    labels = [(slot[0] if locale == "zh" else slot[1])[0] for slot in recipe]
    return " → ".join(labels)


def _framework_recipe_issues(
    vault: dict[str, Any],
    application: dict[str, Any] | None,
    market: str,
) -> list[LintIssue]:
    """Hard-check labeled points against the declared framework's recipe.

    Only retained bullets (the application's selection order, which is the
    render order) are checked, and only when a framework is declared. A point
    counts as labeled when it starts with a leading label — the same prefix
    the renderer shows bold. Unlabeled raw facts keep the existing behavior.
    """
    if not application:
        return []
    writing = application.get("writing") or {}
    framework = writing.get("framework")
    if not framework:
        return []
    recipe = FRAMEWORK_RECIPES.get(framework)
    if framework != "user_voice" and recipe is None:
        return []
    locale = writing.get("locale") or profile.load_market(market)["language"]
    label_maps = _recipe_label_maps(recipe) if recipe else {}
    allowed = _recipe_order_text(recipe, locale) if recipe else ""
    result_slots = {index for index, slot in enumerate(recipe) if slot[2]} if recipe else set()

    selection = application.get("selection") or {}
    order_ids = selection.get("bullet_ids") or []
    order = {bullet_id: index for index, bullet_id in enumerate(order_ids)}

    issues: list[LintIssue] = []
    for collection in ("experience", "projects"):
        for item_index, item in enumerate(vault.get(collection) or []):
            bullets = item.get("bullets") or []
            indexed = list(enumerate(bullets))
            if order_ids:
                indexed = [(index, bullet) for index, bullet in indexed if bullet.get("id") in order]
                indexed.sort(key=lambda pair: order[pair[1]["id"]])
            item_path = f"{collection}[{item_index}]"
            seen_slots: list[int] = []
            seen_labels: list[str] = []
            for bullet_index, bullet in indexed:
                texts = bullet.get("text") or {}
                if isinstance(texts, dict):
                    text = str(texts.get(locale) or next((value for value in texts.values() if value), "") or "")
                else:
                    text = str(texts or "")
                match = _POINT_LABEL_RE.match(text)
                if not text or match is None:
                    continue
                label = match.group(1)
                content = text[len(label):].strip()
                path = f"{item_path}.bullets[{bullet_index}]"
                if recipe is None:  # user_voice: keep custom labels, require content.
                    if not content:
                        issues.append(LintIssue(
                            "lint.framework_label", "error", path,
                            f"The point {label!r} is a bare label with no content.",
                            "Write the complete point after the label; a bare label is not a point.",
                        ))
                    continue
                entry = label_maps.get(locale, {}).get(_label_key(label))
                if entry is None:
                    issues.append(LintIssue(
                        "lint.framework_label", "error", path,
                        f"The label {label!r} is not part of the {framework} recipe for locale {locale!r}.",
                        f"Rewrite the point with the recipe labels, in order: {allowed} (references/writing-engine.md §2).",
                    ))
                    continue
                slot_index, canonical = entry
                if not content:
                    issues.append(LintIssue(
                        "lint.framework_label", "error", path,
                        f"The point {label!r} is a bare label with no content.",
                        "Write the complete point after the label; a bare label is not a point.",
                    ))
                if slot_index in result_slots and not _has_digit(text):
                    issues.append(LintIssue(
                        "lint.result_no_data", "error", path,
                        f"The result point {canonical} carries no number.",
                        "Ask the user for the real data first; only after an explicit no-data answer propose candidate values for confirmation, then write.",
                    ))
                seen_slots.append(slot_index)
                seen_labels.append(label)
            if recipe and any(earlier > later for earlier, later in zip(seen_slots, seen_slots[1:])):
                issues.append(LintIssue(
                    "lint.framework_order", "error", item_path,
                    f"Labeled points are out of {framework} order: {' → '.join(seen_labels)}",
                    f"Reorder the points to the {framework} recipe: {allowed} (references/writing-engine.md §2).",
                ))
    return issues


def lint(
    vault: dict[str, Any],
    *,
    market: str,
    persona: str,
    application: dict[str, Any] | None = None,
    target_role: str | None = None,
) -> LintReport:
    issues: list[LintIssue] = []
    is_cn = market.startswith("cn_")
    is_student = profile.is_student(persona)
    budget = (application or {}).get("page_budget") or page_budget(market, persona)
    summary = _summary_text(vault)
    registry = vault.get("evidence") or {}
    all_skills = [
        str(item.get("name", ""))
        for group in vault.get("skills") or []
        for item in group.get("items") or []
    ]
    skills_text = " ".join(all_skills)
    fundamentals = any(group.get("kind") == "fundamentals" for group in vault.get("skills") or [])
    ai_mentions = len(AI_TERMS.findall(skills_text + " " + summary + " " + " ".join(_text(b) for _, b, _ in _iter_bullets(vault))))

    def add(code: str, severity: str, path: str, message: str, fix: str = "") -> None:
        issues.append(LintIssue(code, severity, path, message, fix))

    if not vault.get("education"):
        add(
            "cn.structure_missing_education" if is_cn else "lint.missing_education",
            "error",
            "education",
            "Education is missing.",
            "Add school, degree, major, and dates; never omit education for parser or HR reasons.",
        )

    for path, bullet, parent in _iter_bullets(vault):
        text = _text(bullet)
        if not text:
            add("lint.empty_bullet", "error", path, "The bullet is empty.", "Remove it or fill it with a real result.")
            continue
        if FIRST_PERSON.search(text):
            add("lint.first_person", "warn", path, "First-person wording is usually unnecessary.", "Start with the action or result, not `I` or `我的`.")
        if WEAK_START.search(text):
            add("lint.weak_verb", "warn", path, "The bullet starts with a weak verb.", "Lead with what you drove, built, cut, or shipped.")
        if not _has_digit(text):
            add("lint.no_metric", "warn", path, "The bullet has no number.", "Ask the user for real data first; if unavailable, propose a plausible value for confirmation.")
        texts = bullet.get("text")
        if isinstance(texts, dict):
            for bullet_locale, value in texts.items():
                limit = BULLET_CHAR_LIMITS.get(bullet_locale)
                if limit and value and len(str(value)) > limit:
                    add(
                        "lint.bullet_too_long",
                        "error",
                        path,
                        f"The {bullet_locale} text is {len(str(value))} characters, over the {limit}-character limit.",
                        "Cut it to one action and one result; keep EN bullets within 240 characters and ZH within 140.",
                    )
        elif len(text) > (140 if is_cn else 240):
            add(
                "lint.bullet_too_long",
                "error",
                path,
                "The bullet is too long for a skim.",
                "Cut it to one action and one result; keep EN bullets within 240 characters and ZH within 140.",
            )
        if len(text) < (12 if is_cn else 20):
            add("lint.bullet_thin", "warn", path, "This bullet is too thin to show ability.", "Expand it with a complete action and outcome, or merge it.")
        if SUPERLATIVES.search(text):
            add("lint.unsupported_superlative", "warn", path, "Superlatives without proof are noise.", "Replace the adjective with a specific result.")
        if PLACEHOLDER_RE.search(text):
            add("lint.placeholder_link", "warn", path, "A placeholder URL is present.", "Use the real link or remove it.")
        refs = bullet.get("evidence") or []
        statuses = [registry.get(ref, {}).get("status") for ref in refs]
        if _has_digit(text) and refs and all(status in ("estimated", "unknown") for status in statuses):
            add("lint.unsupported_number", "error", path, "A number is backed only by an estimate.", "Attach a real source or remove the number.")
        if is_cn and WEAK_START.search(text) and not _has_digit(text):
            add("cn.flow_account", "warn", path, "This reads like a duty list, not an owned result.", "Rewrite as: what you owned, what you changed, what happened.")
        if is_cn:
            for phrase in CLICHES:
                if phrase in text:
                    add("cn.cliche", "warn", path, f"Cliché phrase: {phrase}", "Delete it and show the behavior with a fact.")
                    break

    # Framework packaging recipes: labels, order, and result data are hard checks.
    issues.extend(_framework_recipe_issues(vault, application, market))

    # Summary rules.
    if summary:
        if is_cn and re.match(r"^(本人|作为一名|我是一名)", summary):
            add("cn.cliche_opening", "warn", "identity.summary", "The summary opens with a cliché.", "Open with the strongest fact, not a self-description.")
        if is_cn and "自我评价" in summary:
            add("cn.self_evaluation", "warn", "identity.summary", "Self-evaluation filler is present.", "Replace it with evidence.")
        for phrase in CLICHES:
            if phrase in summary:
                add("cn.cliche", "warn", "identity.summary", f"Cliché phrase: {phrase}", "Delete it and show the behavior with a fact.")
                break

    # CN campus rules.
    if is_cn and is_student:
        if not fundamentals:
            add(
                "cn.cs_fundamentals_missing",
                "error",
                "skills",
                "No CS fundamentals group is present.",
                "Add OS, networks, data structures, algorithms, and databases; campus written tests check them.",
            )
        if ai_mentions >= 5 and fundamentals:
            add(
                "cn.ai_buzzword_density",
                "warn",
                "skills",
                "AI terms outnumber the fundamentals signal.",
                "Keep AI skills that are real and make the CS fundamentals visible.",
            )

    for index, project in enumerate(vault.get("projects") or []):
        context = project.get("context")
        bullets = [_text(bullet) for bullet in project.get("bullets") or []]
        if len(bullets) < 3 or sum(len(text) for text in bullets) < (90 if is_cn else 160):
            add(
                "lint.project_thin",
                "warn",
                f"projects[{index}]",
                "This project reads thin for HR.",
                "Use 3–4 labeled points in the chosen framework's shape with substantial real detail, or exclude the project.",
            )
        if is_student and context in {"personal", "course", "competition", "research", "volunteer"}:
            text = " ".join(bullets)
            tech_count = len(project.get("tech") or [])
            if tech_count <= 2 or len(text) < (180 if is_cn else 320):
                add(
                    "lint.project_rescue",
                    "warn",
                    f"projects[{index}]",
                    "This project could use more depth.",
                    "Ask the user to keep it and add real detail, or remove it.",
                )
        if context in {"course", "personal", "open_source"}:
            if not project.get("own_contribution") and not project.get("optimizations"):
                severity = "error" if is_cn and is_student else "warn"
                add(
                    "cn.demo_only_project" if is_cn else "lint.demo_only_project",
                    severity,
                    f"projects[{index}]",
                    "This project has no personal change or optimization.",
                    "Describe what you changed, why, and what happened.",
                )
        for key in ("start", "end"):
            value = project.get(key)
            if isinstance(value, str) and value[:4].isdigit() and int(value[:4]) > datetime.now().year + 7:
                add("lint.date_future", "warn", f"projects[{index}].{key}", "The date is far in the future.", "Confirm the date.")

    for index, role in enumerate(vault.get("experience") or []):
        start = role.get("start")
        end = role.get("end")
        if isinstance(start, str) and isinstance(end, str) and end not in {"present", ""}:
            if end < start:
                add("lint.date_order", "error", f"experience[{index}]", "The end date is before the start date.", "Fix the dates.")
        if isinstance(start, str) and start[:4].isdigit() and int(start[:4]) > datetime.now().year + 1:
            add("lint.date_future", "warn", f"experience[{index}].start", "The start date is in the future.", "Confirm the date.")

    for section in ("education", "experience", "projects"):
        for index, item in enumerate(vault.get(section) or []):
            if item.get("end") == "present":
                add(
                    "lint.date_open",
                    "warn",
                    f"{section}[{index}].end",
                    "This period ends with 至今/Present.",
                    "Ask for a concrete end month before delivery.",
                )

    for link in (vault.get("identity") or {}).get("links") or []:
        url = str(link.get("url") or "")
        if PLACEHOLDER_RE.search(url) or url in {"#", ""}:
            add(
                "cn.dead_link" if is_cn else "lint.placeholder_link",
                "warn",
                "identity.links",
                f"Placeholder link: {url}",
                "Use the real link or remove it.",
            )

    # Page estimate.
    pages = _estimate_pages(vault, application)
    maximum = int(budget.get("max", 2))
    target = int(budget.get("target", maximum))
    if pages > maximum:
        add(
            "cn.page_count" if is_cn else "lint.page_count",
            "error",
            "page_budget",
            f"Estimated {pages} page(s), above the maximum of {maximum}.",
            "Cut weaker bullets or roles; do not shrink the font below 9pt.",
        )
    elif pages > target:
        add(
            "cn.page_count" if is_cn else "lint.page_count",
            "warn",
            "page_budget",
            f"Estimated {pages} page(s), above the target of {target}.",
            "Tighten the content or accept the larger budget deliberately.",
        )

    # Primacy and structure.
    if application:
        sections = application.get("selection", {}).get("sections") or []
        enabled = [section["id"] for section in sorted(sections, key=lambda s: s["order"]) if section.get("enabled")]
        if is_cn and is_student and "education" in enabled and enabled.index("education") > 2:
            add("cn.primacy", "warn", "selection.sections", "Education is not in the first screen.", "Move education earlier for a CN campus resume.")
        ids = [section["id"] for section in sections]
        if len(ids) != len(set(ids)):
            add("cn.weird_structure", "warn", "selection.sections", "Duplicate sections are configured.", "Keep one entry per section.")

    skim = skim_test(vault, market, persona)
    if not skim.passed:
        add(
            "lint.skim_failed",
            "warn",
            "skim",
            "A 10-second skim does not find name/contact, education, and two core signals.",
            "Move the strongest signals into the first screen.",
        )

    counts = {
        "errors": sum(1 for i in issues if i.severity == "error"),
        "warnings": sum(1 for i in issues if i.severity == "warn"),
        "info": sum(1 for i in issues if i.severity == "info"),
    }
    return LintReport(issues=issues, skim=skim, page_estimate=pages, counts=counts)
