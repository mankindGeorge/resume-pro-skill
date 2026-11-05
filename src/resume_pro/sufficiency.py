# SPDX-License-Identifier: MIT
"""Sufficiency gate: decide whether the vault is ready to build."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import profile
from .evidence import validate_evidence
from .vault import validate_vault

STATUS_BLOCKED = "blocked"
STATUS_MINIMUM = "minimum"
STATUS_STRONG = "strong"

DIMENSION_LABELS = {
    "structural": ("Structural completeness", "结构完整度"),
    "evidence": ("Evidence density", "证据密度"),
    "specificity": ("Specificity", "具体程度"),
    "depth": ("Depth", "深度"),
    "differentiation": ("Differentiation", "区分度"),
    "market_fit": ("Market fit", "市场匹配"),
    "recency": ("Recency", "时效性"),
}

QUESTION_BANK = {
    "sufficiency.identity_name": {
        "ask": "What is your full name?",
        "why": "A resume without a name cannot be used.",
        "example": "Li Ming",
    },
    "sufficiency.contact": {
        "ask": "What email or phone should employers use?",
        "why": "Contact information is required.",
        "example": "name@example.com",
    },
    "sufficiency.education_missing": {
        "ask": "Which school are you in or did you graduate from?",
        "why": "Education is required, and HR systems parse it automatically.",
        "example": "Example University, B.Eng. Computer Science, 2023-09 to 2027-06",
    },
    "sufficiency.education_fields": {
        "ask": "What are the school, degree, major, and dates?",
        "why": "A partial education entry causes parser mismatches and manual checks.",
        "example": "Example University / B.Eng. / Computer Science / 2023-09 – 2027-06",
    },
    "sufficiency.experience_missing": {
        "ask": "What is one role you held, even part-time or freelance?",
        "why": "This persona expects real experience.",
        "example": "Acme Cloud, Backend Intern, 2026-06 to 2026-09",
    },
    "sufficiency.internship_missing": {
        "ask": "Have you done an internship? If not, say so and we will switch to a project-led version.",
        "why": "An internship is a core signal for this persona.",
        "example": "Acme Cloud, Backend Intern, 2026-06 to 2026-09",
    },
    "sufficiency.role_bullets": {
        "ask": "What did you personally change or achieve in that role? Give one result.",
        "why": "Duties are not evidence; results are.",
        "example": "Cut query latency from 480ms to 190ms",
    },
    "sufficiency.projects_missing": {
        "ask": "What is one thing you built where you changed or improved something yourself?",
        "why": "Projects are the main proof when experience is thin.",
        "example": "A course QA tool where you improved retrieval quality",
    },
    "sufficiency.project_depth": {
        "ask": "What did you personally change or optimize in that project, and why?",
        "why": "A demo reproduction is not evidence of your thinking.",
        "example": "Replaced fixed chunking with heading-aware chunking, then measured Recall@5",
    },
    "sufficiency.demo_only_project": {
        "ask": "This project looks like a demo. What did you change, optimize, or decide yourself?",
        "why": "A project that only reproduces a tutorial fails the first follow-up question.",
        "example": "Added caching after profiling showed repeated queries, then measured p95",
    },
    "sufficiency.skills_missing": {
        "ask": "Which languages, frameworks, and tools can you actually use?",
        "why": "Core skills are one of the four campus signals.",
        "example": "Java, Python, MySQL, Redis, Git",
    },
    "sufficiency.skills_used": {
        "ask": "Which of those skills did you actually use in a project?",
        "why": "A skill with no project evidence is a claim, not a signal.",
        "example": "Python and FAISS in the course QA project",
    },
    "sufficiency.bullets_missing": {
        "ask": "What is one concrete result from this experience or project?",
        "why": "A section with no bullets cannot be evaluated.",
        "example": "Reduced manual work by 6 hours per week",
    },
    "sufficiency.cs_fundamentals": {
        "ask": "Which CS fundamentals can you defend in a written test: OS, networks, data structures, algorithms, databases?",
        "why": "Campus written tests check fundamentals, not AI buzzwords.",
        "example": "Operating Systems, Computer Networks, Data Structures, Algorithms, Databases",
    },
    "sufficiency.publications_missing": {
        "ask": "What is one publication or research output?",
        "why": "This persona is evaluated on research output.",
        "example": "A conference paper with venue and year",
    },
    "sufficiency.portfolio_missing": {
        "ask": "What is your portfolio or GitHub link?",
        "why": "This persona is judged on work that can be opened.",
        "example": "https://github.com/you",
    },
    "sufficiency.bridge_missing": {
        "ask": "Why this role, and what proof shows you can do it?",
        "why": "A switcher needs a bridge, not a list of intentions.",
        "example": "Two years of data analysis plus a shipped Python service",
    },
    "sufficiency.leadership_missing": {
        "ask": "What was the scope you led: team size, budget, or system scale?",
        "why": "Senior resumes are judged on scope, not tasks.",
        "example": "Led 9 engineers; owned a service handling 4M daily transactions",
    },
    "sufficiency.build_mode": {
        "ask": "You have no project yet. What could you build in the next 2–4 weeks?",
        "why": "We will not invent a project; we will plan one real proof point.",
        "example": "A small service with a measurable before/after result",
    },
    "sufficiency.target_role": {
        "ask": "What role are you targeting?",
        "why": "The target role anchors the job-intent line and selection.",
        "example": "Backend Engineer (new grad)",
    },
}

_DEFAULT_QUESTION = {
    "ask": "What is one concrete fact that would close this gap?",
    "why": "The gate needs a real fact, not a generic sentence.",
    "example": "A specific action and a verifiable result",
}


@dataclass
class Dimension:
    id: str
    status: str
    score: float
    detail: str
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        label_en, label_zh = DIMENSION_LABELS.get(self.id, (self.id, self.id))
        return {
            "id": self.id,
            "label": label_en,
            "label_zh": label_zh,
            "status": self.status,
            "score": round(self.score, 3),
            "detail": self.detail,
            "fix": self.fix,
        }


@dataclass
class GateReport:
    status: str
    market: str
    persona: str
    dimensions: list[Dimension]
    blockers: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    questions: list[dict[str, Any]] = field(default_factory=list)
    draft: bool = False
    notes: list[Any] = field(default_factory=list)

    @property
    def can_build(self) -> bool:
        return self.status != STATUS_BLOCKED

    @property
    def requires_confirmation(self) -> bool:
        return self.status == STATUS_MINIMUM

    @property
    def deliverable(self) -> bool:
        return self.can_build and not self.draft

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "market": self.market,
            "persona": self.persona,
            "can_build": self.can_build,
            "requires_confirmation": self.requires_confirmation,
            "deliverable": self.deliverable,
            "draft": self.draft,
            "draft_label": "DRAFT — NOT FOR SUBMISSION" if self.draft else None,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "blockers": self.blockers,
            "warnings": self.warnings,
            "questions": self.questions,
            "notes": self.notes,
        }


def _localized(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("en") or value.get("zh") or "")
    return str(value or "")


def _skills_total(vault: dict[str, Any]) -> int:
    return sum(len(group.get("items") or []) for group in vault.get("skills") or [])


def _bullets(vault: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for collection in ("experience", "projects"):
        for index, item in enumerate(vault.get(collection) or []):
            for b_index, bullet in enumerate(item.get("bullets") or []):
                out.append((f"{collection}[{index}].bullets[{b_index}]", bullet))
    return out


def _text(bullet: dict[str, Any]) -> str:
    return " ".join(str(v) for v in (bullet.get("text") or {}).values())


def _has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _internships(vault: dict[str, Any]) -> list[dict[str, Any]]:
    return [x for x in vault.get("experience") or [] if x.get("employment_type") == "internship"]


def _most_recent_year(vault: dict[str, Any]) -> int | None:
    years = []
    for item in (vault.get("experience") or []) + (vault.get("projects") or []):
        for key in ("end", "start"):
            value = item.get(key)
            if isinstance(value, str) and len(value) >= 4 and value[:4].isdigit():
                years.append(int(value[:4]))
    return max(years) if years else None


def _add_issue(
    code: str,
    path: str,
    message: str,
    fix: str,
    *,
    severity: str,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    ask: bool = True,
) -> None:
    item = {"code": code, "path": path, "message": message, "fix": fix, "severity": severity}
    if severity == "error":
        blockers.append(item)
    else:
        warnings.append(item)
    if ask and code in QUESTION_BANK:
        q = dict(QUESTION_BANK[code])
        q.update({"code": code, "path": path})
        if q not in questions:
            questions.append(q)


def evaluate(
    vault: dict[str, Any],
    *,
    market: str,
    persona: str,
    target_role: str | None = None,
    draft: bool = False,
) -> GateReport:
    market_profile = profile.load_market(market)
    persona_profile = profile.load_persona(persona)
    minimum = persona_profile.get("minimum_facts") or {}

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    dimensions: list[Dimension] = []
    notes: list[Any] = [n for n in vault.get("needs_confirmation") or [] if not n.get("resolved")]

    # Schema and evidence are hard gates.
    validation = validate_vault(vault)
    evidence_validation = validate_evidence(vault)
    for issue in validation.errors + evidence_validation.errors:
        _add_issue(
            issue.code,
            issue.path,
            issue.message,
            issue.fix,
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
            ask=False,
        )
    for issue in validation.warnings + evidence_validation.warnings:
        _add_issue(
            issue.code,
            issue.path,
            issue.message,
            issue.fix,
            severity="warning",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
            ask=False,
        )

    identity = vault.get("identity") or {}
    if not identity.get("full_name"):
        _add_issue(
            "sufficiency.identity_name",
            "identity.full_name",
            "The name is missing.",
            "Add the full name.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )
    if not identity.get("email") and not identity.get("phone"):
        _add_issue(
            "sufficiency.contact",
            "identity.email",
            "Neither email nor phone is present.",
            "Add at least one contact method.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )

    education = vault.get("education") or []
    if not education:
        _add_issue(
            "sufficiency.education_missing",
            "education",
            "Education is missing.",
            "Add school, degree, major, and dates.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )
    else:
        for index, item in enumerate(education):
            missing = [
                key
                for key in ("school", "degree", "major", "start", "end")
                if not _localized(item.get(key))
            ]
            if missing:
                _add_issue(
                    "sufficiency.education_fields",
                    f"education[{index}]",
                    f"Education is missing: {', '.join(missing)}.",
                    "Complete the education record; do not omit school or dates.",
                    severity="error",
                    blockers=blockers,
                    warnings=warnings,
                    questions=questions,
                )

    if not target_role:
        _add_issue(
            "sufficiency.target_role",
            "preferences.target_roles",
            "No target role is recorded.",
            "Add a target role, or keep this as a review-only vault.",
            severity="warning",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )

    # Persona minimums.
    experience = vault.get("experience") or []
    projects = vault.get("projects") or []
    internships = _internships(vault)
    skills_total = _skills_total(vault)

    if "roles" in minimum and len(experience) < int(minimum["roles"]):
        _add_issue(
            "sufficiency.experience_missing",
            "experience",
            f"Expected at least {minimum['roles']} roles; found {len(experience)}.",
            "Add the missing role, or switch to a student persona.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )
    if "internships" in minimum and len(internships) < int(minimum["internships"]):
        _add_issue(
            "sufficiency.internship_missing",
            "experience",
            f"Expected at least {minimum['internships']} internship(s); found {len(internships)}.",
            "Add the internship, or switch to a project-led persona.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )
    if "projects" in minimum and len(projects) < int(minimum["projects"]):
        _add_issue(
            "sufficiency.projects_missing",
            "projects",
            f"Expected at least {minimum['projects']} project(s); found {len(projects)}.",
            "Add a real project, or switch to build mode.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )
    if "skills" in minimum and skills_total < int(minimum["skills"]):
        _add_issue(
            "sufficiency.skills_missing",
            "skills",
            f"Expected at least {minimum['skills']} skills; found {skills_total}.",
            "Add concrete skills, including fundamentals where relevant.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )

    bullets_per_role = minimum.get("bullets_per_role")
    if bullets_per_role:
        for index, role in enumerate(experience):
            if len(role.get("bullets") or []) < int(bullets_per_role):
                _add_issue(
                    "sufficiency.role_bullets",
                    f"experience[{index}].bullets",
                    f"Role {index + 1} has fewer than {bullets_per_role} bullets.",
                    "Add a result-oriented bullet, not a duty list.",
                    severity="error",
                    blockers=blockers,
                    warnings=warnings,
                    questions=questions,
                )
    internship_bullets = minimum.get("internship_bullets")
    if internship_bullets:
        for index, role in enumerate(experience):
            if role.get("employment_type") == "internship" and len(role.get("bullets") or []) < int(internship_bullets):
                _add_issue(
                    "sufficiency.role_bullets",
                    f"experience[{index}].bullets",
                    f"The internship has fewer than {internship_bullets} bullets.",
                    "Add a result and a scope detail.",
                    severity="error",
                    blockers=blockers,
                    warnings=warnings,
                    questions=questions,
                )
    project_bullets = minimum.get("project_bullets")
    if project_bullets:
        for index, project in enumerate(projects):
            if len(project.get("bullets") or []) < int(project_bullets):
                _add_issue(
                    "sufficiency.project_depth",
                    f"projects[{index}].bullets",
                    f"Project {index + 1} has fewer than {project_bullets} bullets.",
                    "Add what you changed and what happened.",
                    severity="error",
                    blockers=blockers,
                    warnings=warnings,
                    questions=questions,
                )
    if minimum.get("graduation_date") and education and not education[0].get("end"):
        _add_issue(
            "sufficiency.education_fields",
            "education[0].end",
            "The graduation date is missing.",
            "Add the expected graduation month.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )
    if minimum.get("transferable_proof_points"):
        proof_points = len(experience) + len(projects)
        if proof_points < int(minimum["transferable_proof_points"]):
            _add_issue(
                "sufficiency.bridge_missing",
                "projects",
                f"Expected at least {minimum['transferable_proof_points']} transferable proof points; found {proof_points}.",
                "Add a project, freelance work, open-source contribution, or internal transfer.",
                severity="error",
                blockers=blockers,
                warnings=warnings,
                questions=questions,
            )
    if minimum.get("leadership_scope"):
        if not any(role.get("team_size") or role.get("scope") for role in experience):
            _add_issue(
                "sufficiency.leadership_missing",
                "experience",
                "No leadership scope is recorded.",
                "Add team size, budget, revenue, or system scale.",
                severity="error",
                blockers=blockers,
                warnings=warnings,
                questions=questions,
            )
    if minimum.get("publications") and len(vault.get("publications") or []) < int(minimum["publications"]):
        _add_issue(
            "sufficiency.publications_missing",
            "publications",
            "No publication is recorded.",
            "Add a publication or switch to a non-academic persona.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )
    if minimum.get("research_experience"):
        research = [p for p in projects if p.get("context") == "research"]
        if not research:
            _add_issue(
                "sufficiency.publications_missing",
                "projects",
                "No research project is recorded.",
                "Add a research project or switch persona.",
                severity="error",
                blockers=blockers,
                warnings=warnings,
                questions=questions,
            )
    if minimum.get("portfolio"):
        links = identity.get("links") or []
        has_portfolio = any(
            link.get("kind") in ("portfolio", "github", "blog") for link in links if isinstance(link, dict)
        ) or any(p.get("links") for p in projects)
        if not has_portfolio:
            _add_issue(
                "sufficiency.portfolio_missing",
                "identity.links",
                "No portfolio or repository link is recorded.",
                "Add a live link; a dead link is worse than none.",
                severity="error",
                blockers=blockers,
                warnings=warnings,
                questions=questions,
            )
    if minimum.get("skills_used_in_projects"):
        used = set()
        for project in projects:
            for tech in project.get("tech") or []:
                used.add(str(tech).lower())
        if len(used) < int(minimum["skills_used_in_projects"]):
            _add_issue(
                "sufficiency.skills_used",
                "projects",
                f"Only {len(used)} distinct project technologies are recorded.",
                "Add the tools you actually used in the project.",
                severity="warning",
                blockers=blockers,
                warnings=warnings,
                questions=questions,
            )

    if persona_profile.get("build_mode") and not projects:
        _add_issue(
            "sufficiency.build_mode",
            "projects",
            "This persona needs a proof plan, not a generated resume.",
            "Build 1–2 real proof points in 2–4 weeks, then re-run intake.",
            severity="error",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
        )

    # Dimension: structural completeness.
    structural_problems = len(blockers)
    dimensions.append(
        Dimension(
            "structural",
            "fail" if structural_problems else "pass",
            0.0 if structural_problems else 1.0,
            "Required facts are present." if not structural_problems else f"{structural_problems} blocker(s) remain.",
            "Close the blockers above." if structural_problems else "",
        )
    )

    # Dimension: evidence density.
    all_bullets = _bullets(vault)
    registry = vault.get("evidence") or {}
    supported = 0
    weak_only = 0
    for _, bullet in all_bullets:
        refs = bullet.get("evidence") or []
        statuses = [registry.get(r, {}).get("status") for r in refs]
        if refs and any(s not in ("estimated", "unknown", None) for s in statuses):
            supported += 1
        if refs and statuses and all(s == "user_asserted" for s in statuses):
            weak_only += 1
    ratio = supported / len(all_bullets) if all_bullets else 0.0
    if not all_bullets:
        dimensions.append(Dimension("evidence", "fail", 0.0, "No bullets exist.", "Add at least one result bullet."))
    elif ratio < 0.5:
        dimensions.append(Dimension("evidence", "fail", ratio, f"{supported}/{len(all_bullets)} bullets have usable evidence.", "Attach a source to each bullet."))
    elif ratio < 0.8:
        dimensions.append(Dimension("evidence", "warn", ratio, f"{supported}/{len(all_bullets)} bullets have usable evidence.", "Source the remaining bullets."))
    else:
        dimensions.append(Dimension("evidence", "pass", ratio, f"{supported}/{len(all_bullets)} bullets have usable evidence."))
    if all_bullets and weak_only == len(all_bullets):
        notes.append(
            "All evidence is user-asserted. Nothing is verified yet; add a document, repository, or certificate locator where possible."
        )

    # Dimension: specificity.
    specific = sum(1 for _, b in all_bullets if _has_digit(_text(b)))
    spec_ratio = specific / len(all_bullets) if all_bullets else 0.0
    if not all_bullets:
        dimensions.append(Dimension("specificity", "fail", 0.0, "No bullets to score.", "Add result bullets."))
    elif spec_ratio < 0.3:
        dimensions.append(Dimension("specificity", "fail", spec_ratio, f"{specific}/{len(all_bullets)} bullets contain a number.", "Add a scope or result number where it is real."))
    elif spec_ratio < 0.6:
        dimensions.append(Dimension("specificity", "warn", spec_ratio, f"{specific}/{len(all_bullets)} bullets contain a number.", "Quantify one more real result."))
    else:
        dimensions.append(Dimension("specificity", "pass", spec_ratio, f"{specific}/{len(all_bullets)} bullets contain a number."))
    if all_bullets and specific == 0:
        _add_issue(
            "sufficiency.no_metrics",
            "experience",
            "No bullet contains a number or measurable scope.",
            "Add one real number: latency, users, time saved, or scale.",
            severity="warning",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
            ask=False,
        )

    # Dimension: depth.
    if projects:
        deep = sum(1 for p in projects if p.get("own_contribution") and (p.get("optimizations") or p.get("approach")) and p.get("outcome"))
        depth_ratio = deep / len(projects)
        if depth_ratio == 0:
            dimensions.append(Dimension("depth", "fail", 0.0, "No project shows your own change and outcome.", "Describe one change you made and what happened."))
        elif depth_ratio < 0.5:
            dimensions.append(Dimension("depth", "warn", depth_ratio, f"{deep}/{len(projects)} projects show own work and outcome.", "Add the missing change or outcome."))
        else:
            dimensions.append(Dimension("depth", "pass", depth_ratio, f"{deep}/{len(projects)} projects show own work and outcome."))
        for index, project in enumerate(projects):
            if not project.get("own_contribution") and not project.get("optimizations"):
                _add_issue(
                    "sufficiency.demo_only_project",
                    f"projects[{index}]",
                    "This project has no own contribution or optimization recorded.",
                    "Describe what you changed or decided yourself.",
                    severity="error" if profile.is_student(persona) else "warning",
                    blockers=blockers,
                    warnings=warnings,
                    questions=questions,
                )
    else:
        if profile.is_student(persona):
            dimensions.append(Dimension("depth", "warn", 0.5, "No projects; depth cannot be judged.", "Add a project with your own change and outcome."))
        else:
            dimensions.append(Dimension("depth", "pass", 1.0, "No projects; depth is judged from role scope and outcomes."))

    # Dimension: differentiation.
    proof_points = len(experience) + len(projects)
    if proof_points == 0:
        dimensions.append(Dimension("differentiation", "fail", 0.0, "No proof points.", "Add one real role or project."))
    elif specific == 0:
        dimensions.append(Dimension("differentiation", "warn", 0.5, "Proof points exist but none is measurable.", "Make one result concrete."))
    else:
        dimensions.append(Dimension("differentiation", "pass", 1.0, f"{proof_points} proof point(s), at least one measurable."))

    # Dimension: market fit.
    market_issues = 0
    if market == "cn_internet" and profile.is_student(persona):
        if not any(group.get("kind") == "fundamentals" for group in vault.get("skills") or []):
            _add_issue(
                "sufficiency.cs_fundamentals",
                "skills",
                "No CS fundamentals group is recorded.",
                "Add OS, networks, data structures, algorithms, and databases.",
                severity="error",
                blockers=blockers,
                warnings=warnings,
                questions=questions,
            )
            market_issues += 1
    personal = identity.get("personal") or {}
    if market == "intl_en":
        if identity.get("photo"):
            _add_issue(
                "sufficiency.photo_suppressed",
                "identity.photo",
                "A photo is stored but will not be rendered for intl_en.",
                "No action needed; the renderer suppresses it.",
                severity="warning",
                blockers=blockers,
                warnings=warnings,
                questions=questions,
                ask=False,
            )
        forbidden = [key for key in ("date_of_birth", "gender", "marital_status", "nationality", "political_status") if personal.get(key)]
        if forbidden:
            _add_issue(
                "sufficiency.personal_fields_suppressed",
                "identity.personal",
                f"Sensitive fields will be suppressed: {', '.join(forbidden)}.",
                "No action needed; the renderer suppresses them.",
                severity="warning",
                blockers=blockers,
                warnings=warnings,
                questions=questions,
                ask=False,
            )
    if profile.is_experimental(market_profile) or profile.is_experimental(persona_profile):
        _add_issue(
            "sufficiency.experimental_profile",
            "market",
            "This market or persona profile is experimental and not validated in the MVP.",
            "Use intl_en or cn_internet with a stable persona, or treat the output as exploratory.",
            severity="warning",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
            ask=False,
        )
    dimensions.append(
        Dimension(
            "market_fit",
            "fail" if market_issues else "pass",
            1.0 - 0.5 * market_issues,
            "No market blockers." if not market_issues else f"{market_issues} market-specific blocker(s).",
            "Close the market-specific gap above." if market_issues else "",
        )
    )

    # Dimension: recency.
    latest = _most_recent_year(vault)
    current_year = datetime.now().year
    if latest is None:
        dimensions.append(Dimension("recency", "warn", 0.5, "No dated experience or project.", "Add dates."))
    elif latest >= current_year - 5:
        dimensions.append(Dimension("recency", "pass", 1.0, f"Most recent dated item is from {latest}."))
    else:
        dimensions.append(Dimension("recency", "warn", 0.4, f"Most recent dated item is from {latest}.", "Add recent work or projects."))
        _add_issue(
            "sufficiency.recency",
            "experience",
            f"The most recent dated item is from {latest}, more than five years ago.",
            "Add recent work, projects, or coursework.",
            severity="warning",
            blockers=blockers,
            warnings=warnings,
            questions=questions,
            ask=False,
        )

    if draft:
        warnings.append(
            {
                "code": "sufficiency.draft",
                "path": "output.draft",
                "message": "Draft mode: output is not a deliverable.",
                "fix": "Resolve blockers and rebuild without --draft before submitting.",
                "severity": "warning",
            }
        )

    status = STATUS_STRONG
    if blockers:
        status = STATUS_BLOCKED
    elif warnings or any(d.status != "pass" for d in dimensions):
        status = STATUS_MINIMUM

    return GateReport(
        status=status,
        market=market,
        persona=persona,
        dimensions=dimensions,
        blockers=blockers,
        warnings=warnings,
        questions=questions,
        draft=draft,
        notes=notes,
    )


def ensure_buildable(report: GateReport) -> None:
    from .errors import GateError

    if not report.can_build:
        first = report.blockers[0] if report.blockers else {}
        raise GateError(
            "gate.blocked",
            f"The vault is blocked: {first.get('message', 'minimum facts are missing')}",
            path=first.get("path", ""),
            fix=first.get("fix", "Answer the targeted questions, then run `resume check` again."),
            details=report.to_dict(),
        )
