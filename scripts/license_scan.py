# SPDX-License-Identifier: MIT
"""Simple release-time license and asset scan."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPDX = "# SPDX-License-Identifier: MIT"
EXTERNAL_ASSET = re.compile(r"(?:src|href)\s*=\s*[\"']https?://|@import\s+url\(\s*[\"']?https?://|url\(\s*[\"']?https?://", re.IGNORECASE)


def main() -> int:
    failures: list[str] = []

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8") if (ROOT / "LICENSE").is_file() else ""
    if "MIT License" not in license_text:
        failures.append("LICENSE is missing the MIT text.")
    for required in ("ATTRIBUTIONS.md", "SKILL.md", "docs/open-source-policy.md", "docs/evaluation.md"):
        if not (ROOT / required).is_file():
            failures.append(f"Missing {required}.")

    for directory in ("src", "tests", "scripts"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            first = path.read_text(encoding="utf-8").splitlines()[0] if path.stat().st_size else ""
            if first.strip() != SPDX:
                failures.append(f"{path.relative_to(ROOT)}: missing SPDX header.")
            text = path.read_text(encoding="utf-8")
            if re.search(r"write_(?:text|bytes)\([^\n]*\.(pdf|docx)", text, re.IGNORECASE):
                failures.append(f"{path.relative_to(ROOT)}: writes a PDF/DOCX resume; output must be HTML only.")

    template_dirs = sorted(
        {path.parent for path in (ROOT / "templates").rglob("manifest.json")}
        | {path.parent for path in (ROOT / "templates").rglob("template.html")}
    )
    for template_dir in template_dirs:
        manifest = template_dir / "manifest.json"
        html = template_dir / "template.html"
        css = template_dir / "styles.css"
        if not template_dir.name.startswith("user-") and not manifest.is_file():
            failures.append(f"{template_dir.name}: missing manifest.")
        for path in (html, css):
            if path.is_file():
                text = path.read_text(encoding="utf-8")
                if EXTERNAL_ASSET.search(text):
                    failures.append(f"{path.relative_to(ROOT)}: external asset reference.")
        if html.is_file() and "data-slot" not in html.read_text(encoding="utf-8"):
            failures.append(f"{html.relative_to(ROOT)}: no data-slot markers.")

    if failures:
        print("LICENSE SCAN: FAIL")
        for failure in failures:
            print(" -", failure)
        return 1
    print("LICENSE SCAN: PASS")
    print(
        f"Checked {sum(1 for d in ('src','tests','scripts') for _ in (ROOT/d).rglob('*.py'))} Python files "
        f"and {len(template_dirs)} templates."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
