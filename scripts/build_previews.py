# SPDX-License-Identifier: MIT
"""Build all twelve baseline previews from fictional, locale-matched samples.

Golden snapshots are written only with --update-golden. This script does not
change profiles, source vaults, template approval, or legacy golden filenames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
# Support `python /path/to/scripts/build_previews.py` without an editable install.
sys.path.insert(0, str(ROOT / "src"))

from resume_pro.application import create_application, page_budget, save_application
from resume_pro.render import render_application
from resume_pro.select import select_facts

TEMPLATES = ROOT / "templates"
EXAMPLES = ROOT / "schema" / "examples"
GOLDEN = ROOT / "tests" / "golden"

# Folders identify language, not layout or writing policy. Markets here belong
# only to the fictional preview applications.
LOCALES = {
    "cn": ("zh", "cn_internet", {
        "student": "vault-student-cn.yaml", "experienced": "vault-experienced-cn.yaml",
    }),
    "en": ("en", "intl_en", {
        "student": "vault-student.yaml", "experienced": "vault-experienced.yaml",
    }),
}
CASES = {
    "ats-classic": ("experienced", "experienced", {"zh": "高级后端工程师", "en": "Senior Backend Engineer"}),
    "campus": ("student", "student_with_internship", {"zh": "后端开发工程师", "en": "Backend Engineer"}),
    "modern-sidebar": ("experienced", "experienced", {"zh": "高级后端工程师", "en": "Senior Backend Engineer"}),
    "editorial": ("student", "student_with_internship", {"zh": "后端开发工程师", "en": "Backend Engineer"}),
    "executive": ("experienced", "senior_manager", {"zh": "工程经理", "en": "Engineering Manager"}),
    "zh-professional": ("experienced", "experienced", {"zh": "高级后端工程师", "en": "Senior Backend Engineer"}),
}


def localize_sample(value: Any, language: str) -> Any:
    """Keep only the requested translations in an in-memory fictional sample.

    In particular, bilingual student summaries must not fall back to Chinese in
    English previews. Missing translations fail rather than mix languages.
    """
    if isinstance(value, list):
        return [localize_sample(item, language) for item in value]
    if isinstance(value, dict):
        if {"zh", "en"}.intersection(value):
            if language not in value:
                raise ValueError(f"Fictional sample is missing its {language!r} translation")
            return {language: localize_sample(value[language], language)}
        return {key: localize_sample(item, language) for key, item in value.items()}
    return value


def constrain_sample(vault: dict, manifest: dict) -> None:
    """Fit fictional skill content to the layout, never edit the source vault."""
    remaining = manifest["budgets"]["max_skills"]
    for group in vault.get("skills", []):
        group["items"] = group.get("items", [])[:remaining]
        remaining -= len(group["items"])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update-golden", action="store_true",
        help="Also write all 12 cn-ID.sha256/en-ID.sha256 golden hashes (does not remove legacy hashes).",
    )
    args = parser.parse_args(argv)
    for folder, (language, market, samples) in LOCALES.items():
        for template_id, (sample, persona, roles) in CASES.items():
            directory = TEMPLATES / folder / template_id
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            if manifest["language"] != language or manifest["id"] != template_id:
                raise ValueError(f"Manifest does not match {folder}/{template_id}")
            vault = localize_sample(
                yaml.safe_load((EXAMPLES / samples[sample]).read_text(encoding="utf-8")), language,
            )
            vault["identity"]["locale"] = language
            constrain_sample(vault, manifest)
            budget = page_budget(market, persona)
            role = roles[language]
            selection = select_facts(
                vault, market=market, persona=persona, target_role=role, page_max=budget["max"],
            )
            application = create_application(
                vault=vault, selection=selection, role=role, market=market, persona=persona,
                framework="result_first", template_id=template_id,
            )
            application["writing"]["locale"] = language
            application["page_budget"] = budget
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                save_application(root, application)
                result = render_application(root, vault, application)
                preview = Path(result.html_path).read_text(encoding="utf-8").encode("utf-8")
            (directory / "preview.html").write_bytes(preview)
            if args.update_golden:
                GOLDEN.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256(preview).hexdigest()
                (GOLDEN / f"{folder}-{template_id}.sha256").write_bytes((digest + "\n").encode("ascii"))
            print("preview", f"{folder}/{template_id}", len(preview))


if __name__ == "__main__":
    main()
