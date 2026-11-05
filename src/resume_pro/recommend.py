# SPDX-License-Identifier: MIT
"""Role-family recommendation from the vault. No live job-board access."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import profile

FAMILIES: dict[str, dict[str, Any]] = {
    "backend": {
        "label": "Backend Engineering",
        "terms": ("java", "go", "python", "spring", "mysql", "postgresql", "redis", "kafka", "microservices", "api", "后端", "服务端"),
        "core": ("java", "go", "python", "mysql", "redis", "api", "后端"),
    },
    "frontend": {
        "label": "Frontend Engineering",
        "terms": ("react", "vue", "typescript", "javascript", "css", "html", "next.js", "前端"),
        "core": ("react", "vue", "typescript", "javascript", "前端"),
    },
    "fullstack": {
        "label": "Full-stack Engineering",
        "terms": ("react", "vue", "node.js", "java", "python", "mysql", "api", "全栈"),
        "core": ("react", "vue", "node.js", "api"),
    },
    "data": {
        "label": "Data Engineering / Analytics",
        "terms": ("sql", "spark", "hadoop", "flink", "airflow", "dbt", "etl", "data warehouse", "pandas", "数据分析", "数据仓库"),
        "core": ("sql", "spark", "etl", "数据分析"),
    },
    "ai_ml": {
        "label": "AI / Machine Learning",
        "terms": ("pytorch", "tensorflow", "scikit-learn", "llm", "rag", "nlp", "computer vision", "transformer", "langchain", "大模型", "机器学习", "深度学习", "检索增强"),
        "core": ("pytorch", "tensorflow", "llm", "rag", "机器学习", "大模型"),
    },
    "mobile": {
        "label": "Mobile Engineering",
        "terms": ("android", "ios", "swift", "kotlin", "flutter", "react native", "移动端"),
        "core": ("android", "ios", "swift", "kotlin", "flutter"),
    },
    "devops": {
        "label": "DevOps / SRE / Platform",
        "terms": ("docker", "kubernetes", "aws", "gcp", "azure", "terraform", "ci/cd", "linux", "observability", "sre", "运维"),
        "core": ("docker", "kubernetes", "aws", "ci/cd", "linux"),
    },
    "security": {
        "label": "Security Engineering",
        "terms": ("security", "penetration testing", "iam", "oauth", "encryption", "安全"),
        "core": ("security", "penetration testing", "iam", "安全"),
    },
    "qa": {
        "label": "Quality Engineering",
        "terms": ("testing", "automation", "selenium", "pytest", "junit", "测试", "自动化测试"),
        "core": ("testing", "automation", "测试"),
    },
    "product": {
        "label": "Product Management",
        "terms": ("product", "roadmap", "prd", "user research", "a/b testing", "analytics", "产品经理", "需求"),
        "core": ("product", "roadmap", "prd", "产品经理"),
    },
    "design": {
        "label": "Product / UX Design",
        "terms": ("figma", "sketch", "ui", "ux", "user research", "prototyping", "交互设计", "视觉设计", "用户研究"),
        "core": ("figma", "ui", "ux", "交互设计"),
    },
    "embedded": {
        "label": "Embedded / Systems",
        "terms": ("c", "c++", "rtos", "firmware", "embedded", "linux kernel", "嵌入式", "固件"),
        "core": ("c", "c++", "rtos", "embedded", "嵌入式"),
    },
}


@dataclass
class FamilyFit:
    id: str
    label: str
    score: float
    tier: str
    matched: list[str]
    missing: list[str]
    build_plan: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "score": round(self.score, 2),
            "tier": self.tier,
            "matched": self.matched,
            "missing": self.missing,
            "build_plan": self.build_plan,
        }


@dataclass
class RecommendationReport:
    market: str
    persona: str
    families: list[FamilyFit]
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "persona": self.persona,
            "families": [f.to_dict() for f in self.families],
            "notes": self.notes,
        }


def _vault_text(vault: dict[str, Any]) -> str:
    parts = []
    for group in vault.get("skills") or []:
        parts.extend(str(item.get("name", "")) for item in group.get("items") or [])
    for section in ("experience", "projects"):
        for item in vault.get(section) or []:
            parts.extend(
                str(value)
                for key, value in item.items()
                if isinstance(value, str) and key not in {"id", "start", "end", "context"}
            )
            if isinstance(item.get("title"), dict):
                parts.extend(str(v) for v in item["title"].values())
            if isinstance(item.get("name"), str):
                parts.append(item["name"])
            if isinstance(item.get("tech"), list):
                parts.extend(str(x) for x in item["tech"])
            for bullet in item.get("bullets") or []:
                parts.extend(str(v) for v in (bullet.get("text") or {}).values())
    return " ".join(parts).lower()


def _contains(text: str, term: str) -> bool:
    import re

    if re.search(r"[\u4e00-\u9fff]", term):
        return term in text
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None


def recommend(vault: dict[str, Any], *, market: str, persona: str) -> RecommendationReport:
    text = _vault_text(vault)
    has_proof = bool(vault.get("experience") or vault.get("projects"))
    results: list[FamilyFit] = []
    for family_id, family in FAMILIES.items():
        matched = [term for term in family["terms"] if _contains(text, term)]
        core_matched = [term for term in family["core"] if _contains(text, term)]
        core_ratio = len(core_matched) / len(family["core"]) if family["core"] else 0.0
        total_ratio = len(matched) / len(family["terms"]) if family["terms"] else 0.0
        score = 0.7 * core_ratio + 0.3 * total_ratio
        if not has_proof:
            score *= 0.5
        if score >= 0.60 and core_ratio >= 0.5:
            tier = "Strong"
        elif score >= 0.40:
            tier = "Worth exploring"
        elif score >= 0.25:
            tier = "Stretch"
        else:
            tier = "Not yet"
        missing = [term for term in family["core"] if term not in core_matched]
        if missing:
            build_plan = (
                f"Build or surface one proof point using {', '.join(missing[:3])}; "
                "make it small, real, and measurable."
            )
        else:
            build_plan = "Strengthen the existing proof with a scope or outcome number; rehearse the decisions behind it."
        results.append(
            FamilyFit(
                id=family_id,
                label=family["label"],
                score=score,
                tier=tier,
                matched=matched,
                missing=missing,
                build_plan=build_plan,
            )
        )
    results.sort(key=lambda item: (-item.score, item.id))
    top = results[:3]
    notes = []
    if not has_proof:
        notes.append("No experience or project is recorded; every family is capped until one real proof point exists.")
    if profile.is_student(persona):
        notes.append("For a student, a family becomes credible when one project shows your own change and a result.")
    notes.append("These are role families, not live job listings. No job board is scraped in v1.")
    return RecommendationReport(market=market, persona=persona, families=top, notes=notes)
