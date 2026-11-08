# SPDX-License-Identifier: MIT
"""Selection must keep the vault's point order; scores only decide retention.

render.py renders bullets in selection order and lint checks framework recipe
order against that same sequence, so a score-sorted selection silently rewrites
(or breaks) a correctly ordered STAR/XYZ/... recipe from the vault.
"""

from __future__ import annotations

from resume_pro.select import select_facts


def _vault(collection: str, bullets: list[dict]) -> dict:
    vault = {
        "identity": {"full_name": "Li Ming"},
        "education": [{"id": "edu_001", "school": "Example University"}],
        "experience": [],
        "projects": [],
        "skills": [],
        "evidence": {"ev": {"status": "verified"}},
    }
    vault[collection] = [
        {
            "id": f"{collection[:4]}_001",
            "name": "Course QA with RAG",
            "company": "Acme Cloud",
            "context": "course",
            "bullets": bullets,
        }
    ]
    return vault


def _bullets(prefix: str, texts: list[str]) -> list[dict]:
    return [
        {"id": f"{prefix}_{index}", "text": {"en": text}, "evidence": ["ev"]}
        for index, text in enumerate(texts)
    ]


def test_project_bullet_ids_keep_vault_order():
    """The result point scores highest, but the recipe order must survive."""
    texts = [
        "项目背景：课程资料分散，找答案要翻很久。",
        "解决方案：按标题层级分块并调权重。",
        "核心成果：在 120 条回归问题上把 Recall@5 从 62% 提升到 81%。",
    ]
    bullets = [
        {"id": f"bul_proj_{index}", "text": {"zh": text}, "evidence": ["ev"]}
        for index, text in enumerate(texts)
    ]
    selection = select_facts(
        _vault("projects", bullets),
        market="cn_internet",
        persona="student_with_internship",
        target_role="Backend Engineer",
        page_max=2,
    )
    assert selection["bullet_ids"] == ["bul_proj_0", "bul_proj_1", "bul_proj_2"]


def test_experience_bullet_ids_keep_vault_order_when_trimmed():
    """Budget trimming keeps the strongest points, displayed in vault order."""
    bullets = _bullets(
        "bul_exp",
        [
            "Short duty.",  # weakest: dropped
            "Cut latency 20%.",
            "Cut latency 20% across the order service.",
            "Owned the order service design and reviews.",  # no metric: dropped
            "Built a Kafka pipeline that cut latency 30%.",
            "Built a Kafka and Redis pipeline cut latency 30%.",
        ],
    )
    selection = select_facts(
        _vault("experience", bullets),
        market="cn_internet",
        persona="student_with_internship",
        target_role="Backend Engineer",
        jd_terms={"kafka", "redis"},
        page_max=2,
    )
    assert selection["bullet_ids"] == ["bul_exp_1", "bul_exp_2", "bul_exp_4", "bul_exp_5"]
    dropped = {item["fact_id"] for item in selection["dropped"]}
    assert {"bul_exp_0", "bul_exp_3"} <= dropped


def test_project_trimming_keeps_the_strongest_in_vault_order():
    """Whatever the budget keeps, the kept ids follow the vault sequence."""
    bullets = _bullets(
        "bul_proj",
        [
            "Short duty.",
            "Cut latency 20%.",
            "Cut latency 20% across the order service.",
            "Built a Kafka pipeline that cut latency 30%.",
            "Built a Kafka and Redis pipeline cut latency 30%.",
            "Built a Kafka Redis and MySQL pipeline cut latency 30%.",
        ],
    )
    vault = _vault("projects", bullets)
    selection = select_facts(
        vault,
        market="cn_internet",
        persona="student_with_internship",
        target_role="Backend Engineer",
        jd_terms={"kafka", "redis", "mysql"},
        page_max=2,
    )
    kept = selection["bullet_ids"]
    vault_order = [bullet["id"] for bullet in bullets]
    assert kept == [bullet_id for bullet_id in vault_order if bullet_id in set(kept)]
    assert 3 <= len(kept) <= 4  # the page budget still trims
    assert "bul_proj_0" not in kept  # the weakest point is still dropped
    assert "bul_proj_1" not in kept
    assert selection["dropped"]