# SPDX-License-Identifier: MIT
"""JD parsing, fit scoring, gaps, and risks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

MUST = "must"
NICE = "nice"
GATE = "gate"

REQUIREMENT_HEADINGS = re.compile(
    r"^(requirements?|qualifications?|must[- ]haves?|what you(?:'|’)ll need|what we(?:'|’)re looking for|"
    r"任职要求|岗位要求|必备条件|我们需要你|要求)$",
    re.IGNORECASE,
)
NICE_HEADINGS = re.compile(r"^(preferred|bonus|nice to have|plus|加分项|优先条件|加分)$", re.IGNORECASE)
SKIP_HEADINGS = re.compile(
    r"^(responsibilities|what you(?:'|’)ll do|about (us|the team|the role)|benefits|job description|role|"
    r"岗位职责|工作内容|关于我们|福利|职位描述)$",
    re.IGNORECASE,
)
GATE_RE = re.compile(
    r"\b(visa|work authorization|authorized to work|right to work|work permit|citizen|security clearance|"
    r"permanent resident|green card|cpa|cfa|license|licensed)\b|签证|国籍|居民|工作许可|执业|证书|资格证",
    re.IGNORECASE,
)

LEXICON = {
    "python", "java", "javascript", "typescript", "go", "golang", "c++", "c#", "rust", "ruby", "php", "scala", "kotlin", "swift",
    "react", "vue", "angular", "next.js", "node.js", "django", "flask", "spring", "spring boot", "fastapi", "rails",
    "mysql", "postgresql", "postgres", "redis", "mongodb", "elasticsearch", "kafka", "rabbitmq", "grpc", "rest", "graphql",
    "docker", "kubernetes", "aws", "gcp", "azure", "linux", "terraform", "ansible", "ci/cd", "jenkins",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "spark", "hadoop", "flink", "airflow", "dbt", "sql",
    "llm", "rag", "nlp", "computer vision", "machine learning", "deep learning", "transformer", "langchain", "vector database",
    "figma", "sketch", "adobe", "photoshop", "ui", "ux", "user research", "prototyping",
    "product management", "roadmap", "prd", "stakeholder", "a/b testing", "analytics",
    "microservices", "distributed systems", "high availability", "latency", "throughput", "observability", "sre",
    "security", "penetration testing", "iam", "oauth", "encryption",
    "android", "ios", "flutter", "react native",
    "agile", "scrum", "kanban", "cross-functional", "ownership", "0-1", "startup",
    "后端", "前端", "全栈", "算法", "数据结构", "操作系统", "计算机网络", "数据库", "分布式", "微服务", "高并发",
    "机器学习", "深度学习", "大模型", "检索增强", "自然语言处理", "计算机视觉", "数据分析", "数据仓库",
    "产品经理", "交互设计", "视觉设计", "用户研究", "测试", "自动化测试", "运维", "安全", "嵌入式",
}

HIDDEN_SIGNALS = {
    "ownership": ("owns", "owned", "ownership", "lead", "led", "drive", "drove", "主导", "负责", "独立"),
    "ambiguity": ("0-1", "zero to one", "from scratch", "ambiguous", "fast-paced", "ambiguity", "从零", "快速变化", "不确定"),
    "influence": ("cross-functional", "stakeholder", "align", "influence", "partner", "协调", "推动", "跨部门", "影响"),
    "craft": ("craft", "quality", "detail", "polish", "rigor", "细节", "打磨", "质量"),
    "mission": ("mission", "impact", "mission-driven", "使命", "价值", "社会影响"),
    "learning": ("learn", "growth", "curious", "coach", "学习", "成长", "好奇心"),
}

STOPWORDS = {
    "with", "and", "the", "for", "from", "that", "this", "you", "your", "will", "have", "has", "are", "our", "who",
    "experience", "years", "year", "strong", "good", "ability", "skills", "knowledge", "familiar", "proficient",
    "工作", "经验", "熟悉", "掌握", "具备", "能力", "负责", "相关", "优先", "加分", "要求",
}


@dataclass
class Requirement:
    text: str
    kind: str
    keywords: list[str]
    gate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "kind": self.kind, "keywords": self.keywords, "gate": self.gate}


@dataclass
class Gap:
    requirement: str
    status: str  # partial | missing
    classification: str  # fixable | hard | not_important
    fix: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "status": self.status,
            "classification": self.classification,
            "fix": self.fix,
        }


@dataclass
class MatchReport:
    market: str
    persona: str
    score: int
    score_range: list[int]
    tier: str
    must_score: float
    nice_score: float
    hidden_score: float
    requirements: list[Requirement]
    gaps: list[Gap]
    risks: list[dict[str, str]]
    hidden_signals: dict[str, float]
    keywords: list[str]
    notes: list[str] = field(default_factory=list)
    gate_missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "persona": self.persona,
            "score": self.score,
            "score_range": self.score_range,
            "tier": self.tier,
            "must_score": round(self.must_score, 3),
            "nice_score": round(self.nice_score, 3),
            "hidden_score": round(self.hidden_score, 3),
            "requirements": [r.to_dict() for r in self.requirements],
            "gaps": [g.to_dict() for g in self.gaps],
            "risks": self.risks,
            "hidden_signals": {k: round(v, 2) for k, v in self.hidden_signals.items()},
            "keywords": self.keywords,
            "notes": self.notes,
            "gate_missing": self.gate_missing,
        }


def _lines(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return [re.sub(r"\s+", " ", line).strip() for line in text.split("\n") if line.strip()]


def _clean(line: str) -> str:
    return re.sub(r"^\s*[-•*·▪◦●○–—]\s*", "", line).strip()


def _contains(text: str, term: str) -> bool:
    term = term.lower()
    if re.search(r"[一-鿿]", term):
        return term in text
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None


def _keywords(text: str) -> list[str]:
    lowered = text.lower()
    found = sorted({term for term in LEXICON if _contains(lowered, term)})
    if found:
        return found
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{2,}|[\u4e00-\u9fff]{2,}", text)
    result = []
    for token in tokens:
        lowered_token = token.lower()
        if lowered_token in STOPWORDS or len(lowered_token) < 3:
            continue
        result.append(lowered_token)
    return sorted(set(result))[:5]


def parse_jd(text: str) -> tuple[list[Requirement], list[str], dict[str, float], str | None, str | None, str | None]:
    lines = _lines(text)
    requirements: list[Requirement] = []
    mode = MUST
    keywords: set[str] = set()
    title = None
    location = None
    level = None

    for index, raw in enumerate(lines):
        line = _clean(raw)
        if not line:
            continue
        raw_is_bullet = bool(re.match(r"^\s*[-•*·▪◦●○–—]\s*", raw))
        if index == 0 and not raw_is_bullet and len(line) < 120 and not REQUIREMENT_HEADINGS.match(line):
            title = line
            if not re.search(r"(must|required|require|at least|minimum)|必须|至少|要求", line, re.IGNORECASE) and not GATE_RE.search(line):
                continue
        if REQUIREMENT_HEADINGS.match(line):
            mode = MUST
            continue
        if NICE_HEADINGS.match(line):
            mode = NICE
            continue
        if SKIP_HEADINGS.match(line):
            mode = "skip"
            continue
        if mode == "skip":
            continue
        location_match = re.search(r"(?:location|based in|base|地点|工作地点)\s*[:：]\s*(.+)", line, re.IGNORECASE)
        if location_match:
            location = location_match.group(1).strip()
        salary_match = re.search(r"(\d+)\s*[kK]\s*[-–—]\s*(\d+)\s*[kK]", line)
        if salary_match:
            level = level or "salary_detected"
        if len(line) < 8:
            continue
        kind = mode
        lowered = line.lower()
        if re.search(r"\b(must|required|require|at least|minimum)\b|必须|至少|要求", lowered):
            kind = MUST
        if re.search(r"\b(preferred|plus|bonus|nice to have)\b|优先|加分", lowered):
            kind = NICE
        gate = bool(GATE_RE.search(line))
        if gate:
            kind = GATE if kind != NICE else NICE
        item_keywords = _keywords(line)
        requirements.append(Requirement(text=line, kind=kind, keywords=item_keywords, gate=gate))
        keywords.update(item_keywords)

    if not requirements:
        # Fallback: treat every non-heading line as a requirement.
        for raw in lines:
            line = _clean(raw)
            if len(line) >= 12 and not REQUIREMENT_HEADINGS.match(line):
                requirements.append(Requirement(line, MUST, _keywords(line)))
                keywords.update(requirements[-1].keywords)

    hidden_terms = {}
    jd_lower = text.lower()
    for signal, terms in HIDDEN_SIGNALS.items():
        if any(term in jd_lower for term in terms):
            hidden_terms[signal] = 1.0
    return requirements, sorted(keywords), hidden_terms, title, location, level


def _vault_text(vault: dict[str, Any]) -> str:
    parts: list[str] = []
    identity = vault.get("identity") or {}
    for value in (identity.get("summary") or {}).values() if isinstance(identity.get("summary"), dict) else []:
        parts.append(str(value))
    for group in vault.get("skills") or []:
        parts.extend(str(item.get("name", "")) for item in group.get("items") or [])
    for section in ("education", "experience", "projects", "awards", "certificates", "publications"):
        for item in vault.get(section) or []:
            for key, value in item.items():
                if key in {"id", "evidence", "summary_evidence"}:
                    continue
                if isinstance(value, dict):
                    parts.extend(str(v) for v in value.values() if isinstance(v, str))
                elif isinstance(value, list):
                    for entry in value:
                        if isinstance(entry, str):
                            parts.append(entry)
                        elif isinstance(entry, dict):
                            text = entry.get("text")
                            if isinstance(text, dict):
                                parts.extend(str(v) for v in text.values())
                            elif entry.get("name"):
                                parts.append(str(entry["name"]))
                elif isinstance(value, str):
                    parts.append(value)
    return " ".join(parts).lower()


def _coverage(requirement: Requirement, vault_text: str, bullet_text: str) -> float:
    if not requirement.keywords:
        return 0.0
    matches = [keyword for keyword in requirement.keywords if _contains(vault_text, keyword)]
    if not matches:
        return 0.0
    if len(matches) < len(requirement.keywords):
        return 0.5
    # Full only if at least one keyword appears in a bullet, not just a skills list.
    if any(_contains(bullet_text, keyword) for keyword in requirement.keywords):
        return 1.0
    return 0.5


def _years(vault: dict[str, Any]) -> int:
    years = []
    for role in vault.get("experience") or []:
        start = str(role.get("start") or "")
        if start[:4].isdigit():
            years.append(int(start[:4]))
    if not years:
        return 0
    return max(0, datetime.now().year - min(years))


def _months(start: str | None, end: str | None) -> int:
    if not start or not start[:4].isdigit():
        return 0
    start_year, start_month = int(start[:4]), int(start[5:7] or 1) if len(start) >= 7 else 1
    if not end or end == "present":
        end_year, end_month = datetime.now().year, datetime.now().month
    elif end[:4].isdigit():
        end_year = int(end[:4])
        end_month = int(end[5:7] or 1) if len(end) >= 7 else 1
    else:
        return 0
    return max(0, (end_year - start_year) * 12 + (end_month - start_month))


def match_vault(
    vault: dict[str, Any],
    jd_text: str,
    *,
    market: str,
    persona: str,
    target_role: str | None = None,
) -> MatchReport:
    requirements, keywords, jd_signals, title, location, _ = parse_jd(jd_text)
    vault_text = _vault_text(vault)
    bullet_text = " ".join(
        " ".join(str(v) for v in (bullet.get("text") or {}).values())
        for section in ("experience", "projects")
        for item in vault.get(section) or []
        for bullet in item.get("bullets") or []
    ).lower()

    must_items = [r for r in requirements if r.kind == MUST]
    nice_items = [r for r in requirements if r.kind == NICE]
    work_authorization = str(((vault.get("preferences") or {}).get("work_authorization")) or "").strip()
    coverage: dict[int, float] = {}
    for index, requirement in enumerate(requirements):
        if requirement.kind == GATE and re.search(
            r"visa|authorized to work|right to work|work permit|work authorization|签证|工作许可",
            requirement.text,
            re.IGNORECASE,
        ):
            coverage[index] = 1.0 if work_authorization else 0.0
        else:
            coverage[index] = _coverage(requirement, vault_text, bullet_text)

    must_scores = [coverage[index] for index, r in enumerate(requirements) if r.kind == MUST]
    nice_scores = [coverage[index] for index, r in enumerate(requirements) if r.kind == NICE]
    must_score = sum(must_scores) / len(must_scores) if must_scores else 0.5
    nice_score = sum(nice_scores) / len(nice_scores) if nice_scores else 0.5

    hidden: dict[str, float] = {}
    for signal in jd_signals:
        terms = HIDDEN_SIGNALS[signal]
        hits = sum(1 for term in terms if _contains(vault_text, term))
        hidden[signal] = 1.0 if hits >= 2 else 0.5 if hits == 1 else 0.0
    hidden_score = sum(hidden.values()) / len(hidden) if hidden else 0.5

    total = 0.6 * must_score + 0.2 * nice_score + 0.2 * hidden_score
    zero_must = sum(1 for score in must_scores if score == 0)
    gate_missing = False
    authorization_risk = False
    for index, requirement in enumerate(requirements):
        if requirement.kind != GATE or coverage[index] != 0:
            continue
        if re.search(r"cpa|cfa|license|licensed|security clearance|执业|证书|资格证", requirement.text, re.IGNORECASE):
            gate_missing = True
        else:
            authorization_risk = True
    if zero_must >= 2:
        total = min(total, 0.55)
    elif zero_must == 1:
        total = min(total, 0.75)
    if gate_missing:
        total = min(total, 0.30)

    score = int(round(total * 100))
    score_range = [max(0, score - 5), min(100, score + 5)]
    if score >= 85:
        tier = "Strong"
    elif score >= 70:
        tier = "Worth applying"
    elif score >= 55:
        tier = "Stretch"
    else:
        tier = "Not yet"

    gaps: list[Gap] = []
    for index, requirement in enumerate(requirements):
        score_value = coverage[index]
        if score_value >= 1.0:
            continue
        if requirement.kind == NICE and score_value == 0 and not requirement.gate:
            continue
        text_lower = requirement.text.lower()
        hard = bool(
            re.search(r"\b(\d+\+?\s*years?|degree|bachelor|master|phd|leadership|managed a team)\b|年|学历|本科|硕士|博士|带团队", text_lower)
        ) or requirement.gate
        if score_value == 0.5:
            gaps.append(
                Gap(
                    requirement.text,
                    "partial",
                    "fixable",
                    "Add one concrete bullet or portfolio proof that uses this requirement's language.",
                )
            )
        elif hard:
            gaps.append(
                Gap(
                    requirement.text,
                    "missing",
                    "hard",
                    "This is structural; either show an adjacent proof point or treat the role as a stretch.",
                )
            )
        else:
            gaps.append(
                Gap(
                    requirement.text,
                    "missing",
                    "fixable",
                    "Build or surface a small proof point in the next 2–4 weeks; do not invent experience.",
                )
            )

    risks: list[dict[str, str]] = []
    if authorization_risk:
        risks.append(
            {
                "type": "authorization",
                "question": "Do you have the required work authorization or visa status?",
                "response": "Confirm your status directly before applying; never imply authorization you do not have.",
            }
        )
    years = _years(vault)
    job_title = (target_role or title or "").lower()
    if re.search(r"senior|staff|principal|lead|manager|director", job_title) and years < 5:
        risks.append(
            {
                "type": "level",
                "question": "Is this candidate ready for a more senior scope?",
                "response": "Lead with scope and outcomes, not tenure; name the largest system or team you influenced.",
            }
        )
    if re.search(r"startup|0-1|zero to one|fast-paced", jd_text, re.IGNORECASE) and not re.search(
        r"startup|0-1|zero to one|从零", vault_text
    ):
        risks.append(
            {
                "type": "background",
                "question": "Can this candidate operate without mature process?",
                "response": "Show one example where you defined the process or direction yourself.",
            }
        )
    short_roles = 0
    for role in vault.get("experience") or []:
        if _months(role.get("start"), role.get("end")) < 12:
            short_roles += 1
    if short_roles >= 2:
        risks.append(
            {
                "type": "stability",
                "question": "Why so many short stints?",
                "response": "Prepare a factual, non-defensive reason for each move and emphasize the work delivered.",
            }
        )
    identity_city = ((vault.get("identity") or {}).get("location") or {}).get("city")
    if location and identity_city and location.lower() not in identity_city.lower() and identity_city.lower() not in location.lower():
        risks.append(
            {
                "type": "location",
                "question": "Will the candidate relocate or work in the required location?",
                "response": "State your location preference and whether you will relocate; do not leave it ambiguous.",
            }
        )

    notes = []
    if not must_items:
        notes.append("No must-have requirements were detected; review the JD format.")
    if gate_missing:
        notes.append("A gate requirement appears to be missing; the score is capped.")
    if hidden:
        notes.append("Hidden-signal fit is based on language in your bullets, not a personality test.")

    return MatchReport(
        market=market,
        persona=persona,
        score=score,
        score_range=score_range,
        tier=tier,
        must_score=must_score,
        nice_score=nice_score,
        hidden_score=hidden_score,
        requirements=requirements,
        gaps=gaps,
        risks=risks,
        hidden_signals=hidden,
        keywords=keywords,
        notes=notes,
        gate_missing=gate_missing,
    )
