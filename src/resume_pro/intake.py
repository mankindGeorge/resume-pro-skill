# SPDX-License-Identifier: MIT
"""Guided, one-question-at-a-time intake and persistent session state."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import profile
from .errors import IntakeError
from .evidence import assert_no_fabrication, infer_source, upsert_bullet, validate_evidence
from .paths import delete_path, set_path
from .vault import SCHEMA_VERSION, ensure_ids, next_id, validate_vault

SESSION_VERSION = "1.0"
STAGES = ("target", "identity", "education", "experience", "projects", "skills", "proof", "preferences", "confirm")

_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE = re.compile(r"^([0-9]{4})[-/.](0[1-9]|1[0-2])$")

MARKET_ALIASES = {
    "intl": "intl_en",
    "international": "intl_en",
    "en": "intl_en",
    "cn": "cn_internet",
    "china": "cn_internet",
    "internet": "cn_internet",
    "soe": "cn_soe",
    "finance": "cn_finance",
    "creative": "cn_creative",
    "hk": "hk_sg",
    "sg": "hk_sg",
    "academic": "academic",
}
PERSONA_ALIASES = {
    "student": "student_with_internship",
    "student_internship": "student_with_internship",
    "student_projects": "student_with_projects",
    "student_no_projects": "student_no_projects",
    "grad": "new_grad",
    "newgrad": "new_grad",
    "switcher": "career_switcher",
    "experienced": "experienced",
    "senior": "senior_manager",
    "manager": "senior_manager",
    "academic": "academic",
    "creative": "creative",
}

SKILL_LABELS = {
    "language": {"en": "Languages", "zh": "编程语言"},
    "framework": {"en": "Frameworks", "zh": "框架"},
    "fundamentals": {"en": "CS Fundamentals", "zh": "计算机基础"},
    "ai_ml": {"en": "AI / ML", "zh": "AI / 机器学习"},
    "tool": {"en": "Tools", "zh": "工具"},
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_session(*, lang: str = "en") -> dict[str, Any]:
    now = _utcnow()
    return {
        "schema_version": SESSION_VERSION,
        "lang": lang,
        "market": None,
        "persona": None,
        "role": None,
        "company": None,
        "answered": [],
        "skipped": [],
        "flags": {},
        "artifacts": {},
        "confirmed": False,
        "completed": False,
        "started_at": now,
        "updated_at": now,
    }


def load_session(path: Path | str, *, lang: str = "en") -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        return new_session(lang=lang)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return new_session(lang=lang)
    if not isinstance(data, dict) or data.get("schema_version") != SESSION_VERSION:
        return new_session(lang=lang)
    base = new_session(lang=lang)
    base.update(data)
    base.setdefault("answered", [])
    base.setdefault("skipped", [])
    base.setdefault("flags", {})
    base.setdefault("artifacts", {})
    return base


def save_session(session: dict[str, Any], path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    session["updated_at"] = _utcnow()
    payload = json.dumps(session, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=".session-", suffix=".json.tmp", dir=str(path.parent))
    try:
        import os

        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            import os

            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


@dataclass
class Question:
    id: str
    stage: str
    prompt: dict[str, str]
    why: dict[str, str]
    kind: str = "text"
    path: str | None = None
    choices: tuple[str, ...] = ()
    aliases: dict[str, str] = field(default_factory=dict)
    required: bool = True
    example: str | None = None
    when: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None
    handler: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def optional(self) -> bool:
        return not self.required

    def text(self, lang: str) -> str:
        return self.prompt.get(lang) or self.prompt.get("en") or ""

    def why_text(self, lang: str) -> str:
        return self.why.get(lang) or self.why.get("en") or ""


def _q(
    qid: str,
    stage: str,
    en: str,
    zh: str,
    why_en: str,
    why_zh: str,
    *,
    kind: str = "text",
    path: str | None = None,
    choices: tuple[str, ...] = (),
    aliases: dict[str, str] | None = None,
    required: bool = True,
    example: str | None = None,
    when: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
    handler: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Question:
    return Question(
        id=qid,
        stage=stage,
        prompt={"en": en, "zh": zh},
        why={"en": why_en, "zh": why_zh},
        kind=kind,
        path=path,
        choices=choices,
        aliases=aliases or {},
        required=required,
        example=example,
        when=when,
        handler=handler,
        meta=meta or {},
    )


def _has(vault: dict[str, Any], collection: str, index: int = 0) -> bool:
    return len(vault.get(collection) or []) > index


def _flag(session: dict[str, Any], name: str) -> bool:
    return bool(session.get("flags", {}).get(name))


def _is_targeted(session: dict[str, Any]) -> bool:
    return session.get("application_mode") == "targeted" or session.get("flags", {}).get("application_mode") == "targeted"


def build_questions() -> list[Question]:
    questions: list[Question] = []

    # Target ---------------------------------------------------------------
    questions += [
        _q(
            "target.market",
            "target",
            "Which market are you targeting? Options: " + ", ".join(profile.MARKET_IDS),
            "你投哪个市场？可选：" + "、".join(profile.MARKET_IDS),
            "The market decides page size, photo policy, section order, and page count.",
            "市场决定纸张、照片策略、章节顺序和页数。",
            kind="choice",
            choices=profile.MARKET_IDS,
            aliases=MARKET_ALIASES,
            handler="market",
            example="cn_internet",
        ),
        _q(
            "target.persona",
            "target",
            "Which description fits you? Options: " + ", ".join(profile.PERSONA_IDS),
            "你属于哪种情况？可选：" + "、".join(profile.PERSONA_IDS),
            "The persona sets the minimum facts the gate expects.",
            "身份决定最低事实要求和页数预算。",
            kind="choice",
            choices=profile.PERSONA_IDS,
            aliases=PERSONA_ALIASES,
            handler="persona",
            example="student_with_internship",
        ),
        _q(
            "preferences.application_mode",
            "target",
            "Is this resume mainly for mass applications? (yes/no)",
            "这份简历主要用来海投吗？（yes/no）",
            "For a targeted resume we classify each experience by role and ask which role you prefer; for mass applications we keep one broad version.",
            "如果是定向投递，我们会给每段经历分类并询问你更倾向的岗位；海投则保持一份通用版本。",
            kind="bool",
            handler="application_mode",
        ),
        _q(
            "target.role",
            "target",
            "What role are you targeting? (optional for mass applications)",
            "你想投什么岗位？（海投可不填）",
            "The target role is used for ranking and the file name, not as a rendered job-intent line.",
            "目标岗位只用于排序和文件命名，不会在简历里生成求职意向栏。",
            required=False,
            handler="target_role",
            example="Backend Engineer (new grad)",
        ),
        _q(
            "target.company",
            "target",
            "Any target company? (optional)",
            "有目标公司吗？（可选）",
            "A company is optional; it helps tailor the version later.",
            "公司可不填，填了方便后面定向。",
            required=False,
            handler="target_company",
        ),
    ]

    # Identity -------------------------------------------------------------
    questions += [
        _q("identity.full_name", "identity", "What is your full name?", "你的姓名？", "The name is the first thing a recruiter sees.", "姓名是招聘方第一眼看到的信息。", path="identity.full_name"),
        _q(
            "identity.email",
            "identity",
            "Email address? (optional, but email or phone is required)",
            "邮箱？（可选，但邮箱和电话至少填一个）",
            "Contact information is required for a usable resume.",
            "联系方式是简历可用的前提。",
            kind="email",
            path="identity.email",
            required=False,
            example="name@example.com",
        ),
        _q(
            "identity.phone",
            "identity",
            "Phone number? (optional, but email or phone is required)",
            "手机号？（可选，但邮箱和电话至少填一个）",
            "Contact information is required for a usable resume.",
            "联系方式是简历可用的前提。",
            path="identity.phone",
            required=False,
            example="+86 138 0000 0000",
        ),
        _q("identity.city", "identity", "Which city are you in?", "你所在的城市？", "Location affects market fit and interview logistics.", "城市影响市场匹配和面试安排。", path="identity.location.city"),
        _q(
            "identity.links",
            "identity",
            "Any GitHub, blog, or portfolio links? (comma-separated, optional)",
            "有 GitHub、博客或作品集链接吗？（逗号分隔，可选）",
            "A live link is a proof point; a dead link is worse than none.",
            "有效链接是加分项，死链比没有更差。",
            kind="list",
            required=False,
            handler="links",
            example="https://github.com/you, https://your.blog",
        ),
    ]

    # Education ------------------------------------------------------------
    for index in range(2):
        when = None if index == 0 else (lambda v, s: _flag(s, "more_education"))
        questions += [
            _q(f"education.{index}.school", "education", "Which school?", "哪所学校？", "Education is required; parsers and HR systems look for it.", "教育经历必填，简历系统会解析学校。", path=f"education[{index}].school", when=when),
            _q(f"education.{index}.degree", "education", "What degree?", "什么学历？", "Degree and major are part of the education record.", "学历和专业是教育经历的一部分。", path=f"education[{index}].degree", handler="localized", when=when, example="B.Eng."),
            _q(f"education.{index}.major", "education", "What major?", "什么专业？", "Degree and major are part of the education record.", "学历和专业是教育经历的一部分。", path=f"education[{index}].major", handler="localized", when=when, example="Computer Science"),
            _q(f"education.{index}.start", "education", "Start date? (YYYY-MM)", "入学时间？（YYYY-MM）", "Dates make the timeline parseable.", "日期让时间线可被解析。", kind="date", path=f"education[{index}].start", when=when, example="2023-09"),
            _q(f"education.{index}.end", "education", "Graduation date? (YYYY-MM, or `present`)", "毕业时间？（YYYY-MM，或 `present`）", "Dates make the timeline parseable.", "日期让时间线可被解析。", kind="date", path=f"education[{index}].end", when=when, example="2027-06"),
            _q(
                f"education.{index}.gpa",
                "education",
                "GPA? (optional, e.g. 3.7/4.0)",
                "GPA？（可选，例如 3.7/4.0）",
                "Include GPA only when it is a strength.",
                "GPA 只有在有优势时才写。",
                path=f"education[{index}].gpa",
                required=False,
                handler="gpa",
                when=when,
            ),
            _q(
                f"education.{index}.coursework",
                "education",
                "Relevant coursework? (comma-separated, optional)",
                "相关课程？（逗号分隔，可选）",
                "Coursework can carry technical signal when projects are thin.",
                "项目较少时，相关课程能体现技术基础。",
                kind="list",
                path=f"education[{index}].coursework",
                required=False,
                handler="localized_list",
                when=when,
            ),
        ]
        if index == 0:
            questions.append(
                _q(
                    "education.more",
                    "education",
                    "Do you have another degree? (yes/no, optional)",
                    "还有另一段学历吗？（yes/no，可选）",
                    "Two degrees are useful only when both are relevant.",
                    "只有两段学历都相关时才需要写。",
                    kind="bool",
                    required=False,
                    handler="more_education",
                    when=lambda v, s: _has(v, "education"),
                )
            )

    # Experience -----------------------------------------------------------
    questions.append(
        _q(
            "experience.has",
            "experience",
            "Do you have any internship or work experience? (yes/no)",
            "你有实习或工作经历吗？（yes/no）",
            "Real experience changes what the resume should lead with.",
            "真实经历会改变简历的主线。",
            kind="bool",
            handler="has_experience",
        )
    )
    for index in range(2):
        group_when = (
            (lambda v, s: _flag(s, "has_experience"))
            if index == 0
            else (lambda v, s: _flag(s, "has_experience") and _flag(s, "more_experience"))
        )
        base_when = (
            lambda v, s, i=index, gw=group_when: gw(v, s)
            and _has(v, "experience", i)
            and bool((v["experience"][i] or {}).get("company"))
        )
        questions += [
            _q(f"experience.{index}.company", "experience", "Company or organization?", "公司或组织？", "The company anchors the role.", "公司是这段经历的锚点。", path=f"experience[{index}].company", when=group_when, handler="experience_init"),
            _q(f"experience.{index}.title", "experience", "Your title?", "你的职位？", "The title tells the reader what you owned.", "职位说明你负责什么。", path=f"experience[{index}].title", when=base_when, handler="localized"),
            _q(f"experience.{index}.start", "experience", "Start date? (YYYY-MM)", "开始时间？（YYYY-MM）", "Dates make the timeline parseable.", "日期让时间线可被解析。", kind="date", path=f"experience[{index}].start", when=base_when),
            _q(f"experience.{index}.end", "experience", "End date? (YYYY-MM, or `present`)", "结束时间？（YYYY-MM，或 `present`）", "Dates make the timeline parseable.", "日期让时间线可被解析。", kind="date", path=f"experience[{index}].end", when=base_when),
            _q(
                f"experience.{index}.type",
                "experience",
                "Type? (internship / full_time / part_time / contract / freelance / volunteer)",
                "类型？（internship / full_time / part_time / contract / freelance / volunteer）",
                "The type decides how the role is framed.",
                "类型决定这段经历怎么呈现。",
                kind="choice",
                choices=("internship", "full_time", "part_time", "contract", "freelance", "volunteer"),
                path=f"experience[{index}].employment_type",
                when=base_when,
                example="internship",
            ),
        ]
        for bullet_index in range(3):
            questions.append(
                _q(
                    f"experience.{index}.bullet.{bullet_index}",
                    "experience",
                    (
                        "What did you do or change? One result, with a number if you have one."
                        if bullet_index == 0
                        else "Another result? (one sentence)"
                        if bullet_index == 1
                        else "One more result? (optional)"
                    ),
                    (
                        "你做了什么、改了什么？一条结果，有数字就写。"
                        if bullet_index == 0
                        else "还有一条结果吗？（一句话）"
                        if bullet_index == 1
                        else "再补一条结果？（可选）"
                    ),
                    "A result beats a duty. If you have no number, give a verifiable outcome.",
                    "结果比职责有说服力。没有数字就给可验证的结果。",
                    required=bullet_index < 2,
                    when=base_when,
                    handler="bullet",
                    meta={"collection": "experience", "parent": index, "bullet": bullet_index},
                )
            )
        questions.append(
            _q(
                f"experience.{index}.roles",
                "experience",
                "Which job families does this experience support? (comma-separated; optional)",
                "这段经历支持哪些求职方向？（逗号分隔，可选）",
                "A targeted resume uses this classification to put the most relevant experience first.",
                "定向简历会用这个分类把最相关的经历排在前面。",
                kind="list",
                required=False,
                when=lambda v, s, gw=base_when: gw(v, s) and _is_targeted(s),
                handler="item_roles",
                meta={"collection": "experience", "parent": index},
                example="backend, platform",
            )
        )
        if index == 0:
            questions.append(
                _q(
                    "experience.more",
                    "experience",
                    "Do you have another role? (yes/no, optional)",
                    "还有另一段经历吗？（yes/no，可选）",
                    "The gate needs two roles for experienced candidates.",
                    "资深候选人至少需要两段经历。",
                    kind="bool",
                    required=False,
                    handler="more_experience",
                    when=lambda v, s: _flag(s, "has_experience"),
                )
            )

    # Projects -------------------------------------------------------------
    questions.append(
        _q(
            "projects.has",
            "projects",
            "Do you have a project you can explain in depth? (yes/no)",
            "有没有一个你能讲清楚细节的项目？（yes/no）",
            "Projects are the main proof for students without internships.",
            "没有实习的学生，项目是主要证明。",
            kind="bool",
            handler="has_projects",
        )
    )
    for index in range(2):
        group_when = (
            (lambda v, s: _flag(s, "has_projects"))
            if index == 0
            else (lambda v, s: _flag(s, "has_projects") and _flag(s, "more_projects"))
        )
        base_when = (
            lambda v, s, i=index, gw=group_when: gw(v, s)
            and _has(v, "projects", i)
            and bool((v["projects"][i] or {}).get("name"))
        )
        questions += [
            _q(f"projects.{index}.name", "projects", "Project name?", "项目名称？", "The name anchors the project.", "项目名是这段经历的锚点。", path=f"projects[{index}].name", when=group_when, handler="project_init"),
            _q(
                f"projects.{index}.context",
                "projects",
                "Context? (course / personal / open_source / internship / work / competition / research / volunteer)",
                "项目场景？（course / personal / open_source / internship / work / competition / research / volunteer）",
                "Context tells the reader how much ownership to expect.",
                "场景决定读者对 ownership 的预期。",
                kind="choice",
                choices=("course", "personal", "open_source", "internship", "work", "competition", "research", "volunteer"),
                path=f"projects[{index}].context",
                when=base_when,
                example="course",
            ),
            _q(f"projects.{index}.role", "projects", "Your role in the project? (optional)", "你在项目里的角色？（可选）", "Role separates your work from the team's.", "角色区分你个人和团队的工作。", required=False, path=f"projects[{index}].role", when=base_when, handler="localized"),
            _q(f"projects.{index}.tech", "projects", "Tech stack? (comma-separated, optional)", "技术栈？（逗号分隔，可选）", "Tools are evidence only when tied to work.", "工具只有和具体工作绑定才算证据。", kind="list", required=False, path=f"projects[{index}].tech", when=base_when),
            _q(
                f"projects.{index}.own_contribution",
                "projects",
                "What did you personally build or decide?",
                "你个人做了什么、决定了什么？",
                "This separates your work from a demo reproduction.",
                "这区分你自己的工作和一个 Demo 复现。",
                when=base_when,
                handler="project_bullet",
                meta={"parent": index, "field": "own_contribution", "bullet": 0},
            ),
            _q(
                f"projects.{index}.optimization",
                "projects",
                "What did you change or optimize, and why?",
                "你改了什么、优化了什么，为什么？",
                "A project without your own change is a demo.",
                "没有你自己的改动，就只是 Demo。",
                when=base_when,
                handler="project_bullet",
                meta={"parent": index, "field": "optimization", "bullet": 1},
            ),
            _q(
                f"projects.{index}.outcome",
                "projects",
                "What was the result? (a number or a verifiable outcome)",
                "结果是什么？（数字或可验证的结果）",
                "Outcomes make the project credible.",
                "结果让项目可信。",
                when=base_when,
                handler="project_bullet",
                meta={"parent": index, "field": "outcome", "bullet": 2},
            ),
            _q(f"projects.{index}.link", "projects", "Project link? (optional)", "项目链接？（可选）", "A live repo or demo is a proof point.", "可访问的仓库或 demo 是加分项。", required=False, when=base_when, handler="project_link", meta={"parent": index}),
            _q(
                f"projects.{index}.roles",
                "projects",
                "Which job families does this project support? (comma-separated; optional)",
                "这个项目支持哪些求职方向？（逗号分隔，可选）",
                "A targeted resume uses this classification to put the most relevant projects first.",
                "定向简历会用这个分类把最相关的项目排在前面。",
                kind="list",
                required=False,
                when=lambda v, s, gw=base_when: gw(v, s) and _is_targeted(s),
                handler="item_roles",
                meta={"collection": "projects", "parent": index},
                example="backend, data",
            ),
        ]
        if index == 0:
            questions.append(
                _q(
                    "projects.more",
                    "projects",
                    "Do you have another project? (yes/no, optional)",
                    "还有另一个项目吗？（yes/no，可选）",
                    "Two projects are the minimum for a student without an internship.",
                    "没有实习的学生至少需要两个项目。",
                    kind="bool",
                    required=False,
                    handler="more_projects",
                    when=lambda v, s: _flag(s, "has_projects"),
                )
            )

    # Skills ---------------------------------------------------------------
    questions += [
        _q("skills.languages", "skills", "Programming languages you can defend? (comma-separated)", "你能在面试中讲清楚的编程语言？（逗号分隔）", "Core skills are one of the four campus signals.", "核心技能是校招四个主信号之一。", kind="list", handler="skills", meta={"kind": "language"}, example="Java, Python, SQL"),
        _q("skills.frameworks", "skills", "Frameworks or libraries? (optional)", "框架或库？（可选）", "Frameworks are useful only with real use.", "框架只有真用过才有意义。", kind="list", required=False, handler="skills", meta={"kind": "framework"}, example="Spring Boot, React"),
        _q("skills.cs_fundamentals", "skills", "CS fundamentals you can defend? (OS, networks, data structures, algorithms, databases)", "你能讲清的计算机基础？（操作系统、计网、数据结构、算法、数据库）", "Campus written tests check fundamentals, not AI buzzwords.", "校招笔试考基础，不考 AI 名词。", kind="list", required=False, handler="skills", meta={"kind": "fundamentals"}, example="Operating Systems, Computer Networks, Data Structures, Algorithms, Databases"),
        _q("skills.ai", "skills", "AI / ML skills? (optional)", "AI / ML 相关技能？（可选）", "AI is a signal only when it is real.", "AI 只有真实做过才是信号。", kind="list", required=False, handler="skills", meta={"kind": "ai_ml"}),
        _q("skills.tools", "skills", "Tools? (optional)", "工具？（可选）", "Tools support the work; they do not replace it.", "工具是辅助，不替代实际工作。", kind="list", required=False, handler="skills", meta={"kind": "tool"}),
    ]

    # Proof ----------------------------------------------------------------
    questions += [
        _q("proof.links", "proof", "Any GitHub, blog, or portfolio links? (optional)", "有 GitHub、博客或作品集链接吗？（可选）", "A live link is a proof point.", "有效链接是加分项。", kind="list", required=False, handler="links"),
        _q("proof.awards", "proof", "Any awards or honors? (comma-separated, optional)", "有奖项或荣誉吗？（逗号分隔，可选）", "Awards help when they are specific and relevant.", "具体且相关的奖项才有帮助。", kind="list", required=False, handler="awards"),
    ]

    # Preferences ----------------------------------------------------------
    questions += [
        _q(
            "preferences.preferred_role",
            "preferences",
            "Which role do you prefer for this resume? (optional; used for targeting and the file name)",
            "这份简历你更倾向于投什么岗位？（可选；用于定向和文件命名）",
            "A targeted resume is built for one preferred role; no job-intent section is added.",
            "定向简历围绕一个首选岗位生成，但不会增加求职意向栏。",
            required=False,
            when=lambda v, s: _is_targeted(s),
            handler="preferred_role",
        ),
        _q("preferences.locations", "preferences", "Preferred locations? (comma-separated, optional)", "期望城市？（逗号分隔，可选）", "Location is a hard constraint for some candidates.", "地点对部分候选人是硬约束。", kind="list", required=False, handler="locations"),
        _q("preferences.remote", "preferences", "Remote preference? (required / preferred / negotiable / no, optional)", "远程偏好？（required / preferred / negotiable / no，可选）", "Remote policy affects which roles fit.", "远程政策影响岗位匹配。", kind="choice", choices=("required", "preferred", "negotiable", "no"), required=False, handler="remote"),
    ]

    # Confirm --------------------------------------------------------------
    questions += [
        _q("confirm.summary", "confirm", "Does the summary look right? (yes/no)", "上面的汇总信息对吗？（yes/no）", "Nothing is generated until the facts are confirmed.", "事实确认之前不会生成任何简历。", kind="bool", handler="confirm"),
        _q("confirm.note", "confirm", "What should be corrected? (one sentence)", "哪里需要改？（一句话）", "A correction note is recorded and the summary is shown again.", "修改说明会被记录，然后重新确认。", required=False, handler="confirm_note", when=lambda v, s: _flag(s, "declined_confirm")),
    ]
    return questions


class SkipQuestion(Exception):
    pass


class UnknownAnswer(Exception):
    pass


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"yes", "y", "true", "1", "是", "有", "对", "好的"}:
        return True
    if value in {"no", "n", "false", "0", "否", "没有", "不", "无"}:
        return False
    raise IntakeError("intake.invalid_bool", f"{raw!r} is not a yes/no answer.", fix="Answer `yes` or `no`.")


def _parse_choice(question: Question, raw: str) -> str:
    value = raw.strip()
    if value.isdigit():
        index = int(value) - 1
        if 0 <= index < len(question.choices):
            return question.choices[index]
    lowered = value.lower()
    if lowered in question.aliases:
        return question.aliases[lowered]
    for choice in question.choices:
        if lowered == choice.lower():
            return choice
    raise IntakeError(
        "intake.invalid_choice",
        f"{raw!r} is not one of the allowed values.",
        fix="Use one of: " + ", ".join(question.choices) + ".",
    )


def _parse_date(raw: str) -> str:
    value = raw.strip().lower()
    if value in {"present", "now", "至今", "现在", "目前"}:
        return "present"
    match = _DATE_RE.match(value)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    raise IntakeError(
        "intake.invalid_date",
        f"{raw!r} is not a month.",
        fix="Use YYYY-MM, for example 2025-09, or `present`.",
    )


def parse_answer(question: Question, raw: str) -> Any:
    value = raw.strip()
    if value == "":
        if question.optional:
            raise SkipQuestion()
        raise IntakeError("intake.required", "This question is required.", fix="Provide a value, or answer `skip` to leave a recorded gap.")
    lowered = value.lower()
    if lowered in {"skip", "跳过"}:
        raise SkipQuestion()
    if lowered in {"don't know", "dont know", "not sure", "不知道", "不清楚", "不记得"}:
        raise UnknownAnswer()
    assert_no_fabrication(value)

    if question.kind == "bool":
        return _parse_bool(value)
    if question.kind == "choice":
        return _parse_choice(question, value)
    if question.kind == "date":
        return _parse_date(value)
    if question.kind == "email":
        if not _EMAIL_RE.match(value):
            raise IntakeError("intake.invalid_email", f"{raw!r} is not an email address.", fix="Use name@example.com.")
        return value
    if question.kind == "list":
        parts = [p.strip() for p in re.split(r"[,，;；\n]", value) if p.strip()]
        if not parts and question.required:
            raise IntakeError("intake.empty_list", "The list is empty.", fix="Provide at least one item.")
        return parts
    return value


def _ensure_item(vault: dict[str, Any], collection: str, index: int) -> dict[str, Any]:
    items = vault.setdefault(collection, [])
    while len(items) <= index:
        items.append({})
    return items[index]


def _set_localized(vault: dict[str, Any], path: str, value: str, lang: str) -> None:
    set_path(vault, path, {lang: value})


def _append_localized_list(vault: dict[str, Any], path: str, values: list[str], lang: str) -> None:
    set_path(vault, path, {lang: values})


def _add_links(vault: dict[str, Any], values: list[str]) -> None:
    links = (vault.get("identity") or {}).get("links") or []
    existing = {link.get("url") for link in links if isinstance(link, dict)}
    for value in values:
        if not _URL_RE.match(value):
            raise IntakeError(
                "intake.invalid_url",
                f"{value!r} is not a URL.",
                fix="Use a full link starting with http:// or https://, or skip.",
            )
        if value in existing:
            continue
        kind = "github" if "github.com" in value else "portfolio"
        if "linkedin.com" in value:
            kind = "linkedin"
        links.append({"label": kind.capitalize(), "url": value, "kind": kind})
        existing.add(value)
    vault.setdefault("identity", {})["links"] = links


def _parse_gpa(raw: str) -> dict[str, Any]:
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)\s*$", raw)
    if not match:
        raise IntakeError(
            "intake.invalid_gpa",
            f"{raw!r} is not a GPA value.",
            fix="Use value/scale, for example 3.7/4.0.",
        )
    return {"value": float(match.group(1)), "scale": float(match.group(2))}


class IntakeEngine:
    def __init__(self, vault: dict[str, Any], session: dict[str, Any], *, lang: str | None = None):
        self.vault = vault
        self.session = session
        self.lang = lang or session.get("lang") or "en"
        self.questions = build_questions()

    def applicable(self) -> list[Question]:
        answered = set(self.session.get("answered") or [])
        skipped = set(self.session.get("skipped") or [])
        result = []
        for question in self.questions:
            if question.id in answered or question.id in skipped:
                continue
            if question.when and not question.when(self.vault, self.session):
                continue
            result.append(question)
        return result

    def current(self) -> Question | None:
        applicable = self.applicable()
        return applicable[0] if applicable else None

    def by_id(self, question_id: str) -> Question:
        for question in self.questions:
            if question.id == question_id:
                return question
        raise IntakeError(
            "intake.unknown_question",
            f"No question with id {question_id!r}.",
            fix="Run `resume intake --json` to see the current question id.",
        )

    def progress(self) -> dict[str, int]:
        answered = set(self.session.get("answered") or [])
        skipped = set(self.session.get("skipped") or [])
        total = len(self.applicable()) + len(answered & {q.id for q in self.questions}) + len(skipped)
        done = len(answered) + len(skipped)
        return {"answered": done, "total": max(total, done)}

    def answer(self, question: Question, raw: str) -> Question | None:
        try:
            value = parse_answer(question, raw)
        except SkipQuestion:
            return self.skip(question)
        except UnknownAnswer:
            return self.skip(question, unknown=True)

        if question.id != "confirm.summary":
            self.vault["status"] = "collecting"
            self.session["confirmed"] = False
            if "confirm.summary" in self.session.get("answered", []):
                self.session["answered"].remove("confirm.summary")
        self._apply(question, value)
        if question.id not in self.session.setdefault("answered", []):
            self.session["answered"].append(question.id)
        if question.id in self.session.get("skipped", []):
            self.session["skipped"].remove(question.id)
        self.session["completed"] = self.current() is None
        return self.current()

    def skip(self, question: Question, *, unknown: bool = False) -> Question | None:
        if question.id not in self.session.setdefault("skipped", []):
            self.session["skipped"].append(question.id)
        if question.id in self.session.get("answered", []):
            self.session["answered"].remove(question.id)
        reason = "The user does not know this yet." if unknown else "Skipped during intake."
        self._record_confirmation(question, reason, blocker=question.required)
        self.session["completed"] = self.current() is None
        return self.current()

    def _record_confirmation(self, question: Question, reason: str, *, blocker: bool) -> None:
        path = question.path or question.id
        notes = self.vault.setdefault("needs_confirmation", [])
        for note in notes:
            if note.get("path") == path and note.get("question") == question.prompt["en"]:
                return
        notes.append(
            {
                "path": path,
                "reason": reason,
                "severity": "blocker" if blocker else "warning",
                "question": question.prompt["en"],
                "resolved": False,
            }
        )

    def _apply(self, question: Question, value: Any) -> None:
        handler = question.handler
        if handler == "market":
            self.session["market"] = value
            self.vault.setdefault("preferences", {})["target_markets"] = [value]
        elif handler == "persona":
            self.session["persona"] = value
        elif handler == "application_mode":
            mode = "mass" if bool(value) else "targeted"
            self.session["application_mode"] = mode
            self.session.setdefault("flags", {})["application_mode"] = mode
            self.vault.setdefault("preferences", {})["application_mode"] = mode
        elif handler == "target_role":
            self.session["role"] = value
            self.vault.setdefault("preferences", {})["target_roles"] = [value]
            self.vault["preferences"]["preferred_role"] = value
        elif handler == "preferred_role":
            self.session["role"] = value
            self.vault.setdefault("preferences", {})["preferred_role"] = value
            self.vault["preferences"]["target_roles"] = [value]
        elif handler == "item_roles":
            collection = question.meta["collection"]
            parent = question.meta["parent"]
            items = self.vault.get(collection) or []
            if parent < len(items):
                items[parent]["target_roles"] = list(value)
        elif handler == "target_company":
            self.session["company"] = value
        elif handler == "links":
            _add_links(self.vault, value)
        elif handler == "localized":
            _set_localized(self.vault, question.path or "", value, self.lang)
        elif handler == "localized_list":
            _append_localized_list(self.vault, question.path or "", value, self.lang)
        elif handler == "gpa":
            set_path(self.vault, question.path or "", _parse_gpa(value))
        elif handler == "more_education":
            self.session.setdefault("flags", {})["more_education"] = bool(value)
        elif handler == "has_experience":
            self.session.setdefault("flags", {})["has_experience"] = bool(value)
        elif handler == "more_experience":
            self.session.setdefault("flags", {})["more_experience"] = bool(value)
        elif handler == "has_projects":
            self.session.setdefault("flags", {})["has_projects"] = bool(value)
        elif handler == "more_projects":
            self.session.setdefault("flags", {})["more_projects"] = bool(value)
        elif handler == "experience_init":
            index = question.meta.get("index", _question_index(question.id))
            item = _ensure_item(self.vault, "experience", index)
            if not item.get("id"):
                item["id"] = next_id(self.vault, "exp")
            item["company"] = value
        elif handler == "bullet":
            collection = question.meta["collection"]
            parent = question.meta["parent"]
            bullet_index = question.meta["bullet"]
            items = self.vault.get(collection) or []
            if parent >= len(items) or not items[parent].get("id"):
                raise IntakeError(
                    "intake.missing_parent",
                    "The parent entry does not exist yet.",
                    fix="Answer the company or project name question first.",
                )
            source, locator = infer_source(value)
            upsert_bullet(self.vault, collection, parent, bullet_index, value, lang=self.lang, source=source, locator=locator)
        elif handler == "project_init":
            index = question.meta.get("parent", _question_index(question.id))
            item = _ensure_item(self.vault, "projects", index)
            if not item.get("id"):
                item["id"] = next_id(self.vault, "proj")
            item["name"] = value
        elif handler == "project_bullet":
            parent = question.meta["parent"]
            field_name = question.meta["field"]
            bullet_index = question.meta["bullet"]
            item = _ensure_item(self.vault, "projects", parent)
            if not item.get("id"):
                item["id"] = next_id(self.vault, "proj")
            if field_name == "own_contribution":
                item["own_contribution"] = {self.lang: value}
            elif field_name == "optimization":
                item["optimizations"] = {self.lang: [value]}
            elif field_name == "outcome":
                item["outcome"] = {self.lang: value}
            source, locator = infer_source(value)
            upsert_bullet(self.vault, "projects", parent, bullet_index, value, lang=self.lang, source=source, locator=locator)
        elif handler == "project_link":
            parent = question.meta["parent"]
            item = _ensure_item(self.vault, "projects", parent)
            if not _URL_RE.match(value):
                raise IntakeError("intake.invalid_url", f"{value!r} is not a URL.", fix="Use a full link starting with http:// or https://, or skip.")
            item.setdefault("links", []).append({"label": "Project", "url": value, "kind": "other"})
        elif handler == "skills":
            self._apply_skills(question, value)
        elif handler == "awards":
            for title in value:
                self.vault.setdefault("awards", []).append(
                    {"id": next_id(self.vault, "awd"), "title": {self.lang: title}}
                )
        elif handler == "locations":
            self.vault.setdefault("preferences", {})["locations"] = value
        elif handler == "remote":
            self.vault.setdefault("preferences", {})["remote"] = value
        elif handler == "confirm":
            self._apply_confirm(bool(value))
        elif handler == "confirm_note":
            self.session["notes"] = str(value)
            self.session.setdefault("flags", {})["declined_confirm"] = False
            if "confirm.summary" in self.session.get("answered", []):
                self.session["answered"].remove("confirm.summary")
        elif question.path:
            set_path(self.vault, question.path, value)
        else:
            raise IntakeError(
                "intake.unhandled",
                f"No handler for question {question.id!r}.",
                fix="This is a bug; report the question id.",
            )

    def _apply_skills(self, question: Question, values: list[str]) -> None:
        kind = question.meta["kind"]
        groups = self.vault.setdefault("skills", [])
        artifact_key = f"skills.{kind}"
        group_id = self.session.setdefault("artifacts", {}).get(artifact_key)
        group = next((g for g in groups if g.get("id") == group_id), None)
        if group is None:
            group_id = next_id(self.vault, "skl")
            group = {
                "id": group_id,
                "name": dict(SKILL_LABELS.get(kind, {"en": kind, "zh": kind})),
                "kind": kind,
                "items": [],
            }
            groups.append(group)
            self.session["artifacts"][artifact_key] = group_id
        existing = {item.get("name") for item in group.get("items", [])}
        for name in values:
            if name not in existing:
                group.setdefault("items", []).append({"name": name, "level": "unknown"})
                existing.add(name)

    def _apply_confirm(self, yes: bool) -> None:
        if yes:
            self.session["confirmed"] = True
            self.session.setdefault("flags", {})["declined_confirm"] = False
            ensure_ids(self.vault)
            self.vault["status"] = "ready"
            result = validate_vault(self.vault)
            evidence_result = validate_evidence(self.vault)
            result.issues.extend(evidence_result.issues)
            if not result.ok:
                self.vault["status"] = "collecting"
                self.session["confirmed"] = False
                first = result.errors[0]
                raise IntakeError(
                    "intake.vault_invalid",
                    f"The vault is not complete enough to confirm: {first.message}",
                    path=first.path,
                    fix=first.fix,
                    details=result.to_dict(),
                )
        else:
            self.session["confirmed"] = False
            self.session.setdefault("flags", {})["declined_confirm"] = True
            self.vault["status"] = "collecting"


def _question_index(question_id: str) -> int:
    match = re.search(r"\.(\d+)\.", question_id)
    return int(match.group(1)) if match else 0


def summary(vault: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    identity = vault.get("identity") or {}
    return {
        "target": {
            "market": session.get("market"),
            "persona": session.get("persona"),
            "role": session.get("role"),
            "company": session.get("company"),
        },
        "identity": {
            "name": identity.get("full_name"),
            "email": identity.get("email"),
            "phone": identity.get("phone"),
            "city": (identity.get("location") or {}).get("city"),
            "links": identity.get("links") or [],
        },
        "education": vault.get("education") or [],
        "experience": [
            {
                "company": item.get("company"),
                "title": item.get("title"),
                "start": item.get("start"),
                "end": item.get("end"),
                "bullets": len(item.get("bullets") or []),
            }
            for item in vault.get("experience") or []
        ],
        "projects": [
            {
                "name": item.get("name"),
                "context": item.get("context"),
                "bullets": len(item.get("bullets") or []),
            }
            for item in vault.get("projects") or []
        ],
        "skills": [
            {"group": (item.get("name") or {}).get("en") or (item.get("name") or {}).get("zh"), "items": [i.get("name") for i in item.get("items") or []]}
            for item in vault.get("skills") or []
        ],
        "counts": {
            "education": len(vault.get("education") or []),
            "experience": len(vault.get("experience") or []),
            "projects": len(vault.get("projects") or []),
            "skills": sum(len(g.get("items") or []) for g in vault.get("skills") or []),
            "bullets": sum(len(x.get("bullets") or []) for x in (vault.get("experience") or []) + (vault.get("projects") or [])),
            "evidence": len(vault.get("evidence") or {}),
        },
        "vault_status": vault.get("status"),
        "confirmed": session.get("confirmed"),
        "notes": session.get("notes"),
        "unresolved": [n for n in vault.get("needs_confirmation") or [] if not n.get("resolved")],
    }


def reset_answers(vault: dict[str, Any], question_id: str) -> None:
    """Remove a single answer so it can be asked again."""
    for collection in ("education", "experience", "projects"):
        for index in range(len(vault.get(collection) or [])):
            if question_id.startswith(f"{collection}.{index}."):
                delete_path(vault, f"{collection}[{index}]")
                return
    for prefix in ("identity.", "preferences."):
        if question_id.startswith(prefix):
            delete_path(vault, question_id)
            return
    if question_id.startswith("skills."):
        return
