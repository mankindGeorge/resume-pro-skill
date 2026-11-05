# SPDX-License-Identifier: MIT
"""Generate preview.html for the library templates from fictional sample vaults."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from resume_pro.application import create_application, page_budget, save_application
from resume_pro.render import render_application
from resume_pro.select import select_facts

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
EXAMPLES = ROOT / "schema" / "examples"

CASES = {
    "ats-classic": ("vault-experienced.yaml", "intl_en", "experienced", "Senior Backend Engineer"),
    "campus": ("vault-student-cn.yaml", "cn_internet", "student_with_internship", "后端开发工程师"),
    "modern-sidebar": ("vault-experienced.yaml", "intl_en", "experienced", "Senior Backend Engineer"),
    "editorial": ("vault-student-projects.yaml", "intl_en", "student_with_projects", "Backend Engineer"),
    "executive": ("vault-experienced.yaml", "intl_en", "senior_manager", "Engineering Manager"),
    "zh-professional": ("vault-experienced-cn.yaml", "cn_internet", "experienced", "高级后端工程师"),
}


def main() -> None:
    for template_id, (vault_file, market, persona, role) in CASES.items():
        vault = yaml.safe_load((EXAMPLES / vault_file).read_text(encoding="utf-8"))
        budget = page_budget(market, persona)
        selection = select_facts(
            vault,
            market=market,
            persona=persona,
            target_role=role,
            page_max=budget["max"],
        )
        application = create_application(
            vault=vault,
            selection=selection,
            role=role,
            market=market,
            persona=persona,
            framework="result_first",
            template_id=template_id,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_application(root, application)
            result = render_application(root, vault, application)
            preview = Path(result.html_path).read_text(encoding="utf-8")
        folder = "cn" if market.startswith("cn_") else "en"
        (TEMPLATES / folder / template_id / "preview.html").write_text(preview, encoding="utf-8")
        print("preview", template_id, len(preview))


if __name__ == "__main__":
    main()
