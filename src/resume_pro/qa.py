# SPDX-License-Identifier: MIT
"""Post-render QA: parseability, layout, content, market, and privacy."""

from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from . import profile
from .application import application_dir
from .errors import ResumeProError
from .ingest import EMAIL_RE, PHONE_RE
from .lint import CLICHES, FIRST_PERSON, WEAK_START
from .paths import schema_dir
from .render import load_template
from .template_audit import PERSONAL_MARKERS

BROWSER_CANDIDATES = (
    os.environ.get("RESUME_PRO_BROWSER"),
    shutil.which("msedge"),
    shutil.which("chrome"),
    shutil.which("chromium"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
CS_TERMS = (
    "operating systems", "operating system", "networks", "network", "data structures", "data structure",
    "algorithms", "algorithm", "databases", "database",
    "操作系统", "计算机网络", "网络", "数据结构", "算法", "数据库",
)


class QAError(ResumeProError):
    pass


@dataclass
class QACheck:
    id: str
    status: str  # pass | warn | fail
    detail: str
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status, "detail": self.detail, "fix": self.fix}


@dataclass
class QAResult:
    status: str
    checks: list[QACheck]
    metrics: dict[str, Any]
    browser: str | None = None

    @property
    def hard_failures(self) -> list[QACheck]:
        return [check for check in self.checks if check.status == "fail"]

    @property
    def warnings(self) -> list[QACheck]:
        return [check for check in self.checks if check.status == "warn"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "browser": self.browser,
            "checks": [check.to_dict() for check in self.checks],
            "hard_failures": [check.to_dict() for check in self.hard_failures],
            "warnings": [check.to_dict() for check in self.warnings],
            "metrics": self.metrics,
        }


def find_browser() -> str | None:
    for candidate in BROWSER_CANDIDATES:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value or "")).lower()


def _html_info(html_text: str) -> dict[str, Any]:
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["style", "script", "noscript"]):
        tag.decompose()
    sections = []
    headings = {}
    for tag in soup.find_all("section", attrs={"data-section": True}):
        section_id = tag.get("data-section")
        heading = tag.find("h2")
        heading_text = heading.get_text(" ", strip=True) if heading else ""
        sections.append(section_id)
        headings[section_id] = heading_text
    items = [item.get_text(" ", strip=True) for item in soup.find_all("li")]
    return {
        "sections": sections,
        "headings": headings,
        "text": soup.get_text(" ", strip=True),
        "items": [item for item in items if item],
        "images": len(soup.find_all("img")),
    }


def _font_size(html_text: str) -> float | None:
    match = re.search(r"--size-body:\s*([0-9.]+)pt", html_text)
    if match:
        return float(match.group(1))
    match = re.search(r"body\s*\{[^}]*?font-size\s*:\s*([0-9.]+)pt", html_text, re.DOTALL)
    if match:
        return float(match.group(1))
    return None


def _browser_pdf(html_path: Path, browser: str) -> tuple[int, list[str], list[dict[str, Any]], float] | None:
    try:
        import pdfplumber
    except ImportError:
        return None
    with tempfile.TemporaryDirectory(prefix="resume-qa-") as tmp:
        tmp_path = Path(tmp)
        pdf_path = tmp_path / "resume.pdf"
        profile_dir = tmp_path / "profile"
        profile_dir.mkdir()
        command = [
            browser,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile_dir}",
            f"--print-to-pdf={pdf_path}",
            html_path.resolve().as_uri(),
        ]
        try:
            subprocess.run(command, timeout=90, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
            return None
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                texts = [(page.extract_text() or "") for page in pdf.pages]
                chars = []
                for page in pdf.pages:
                    for char in page.chars or []:
                        chars.append(
                            {
                                "x0": char.get("x0", 0),
                                "x1": char.get("x1", 0),
                                "top": char.get("top", 0),
                                "bottom": char.get("bottom", 0),
                                "page_height": page.height or 0,
                                "page_width": page.width or 0,
                            }
                        )
                height = pdf.pages[-1].height if pdf.pages else 0
                return len(pdf.pages), texts, chars, height
        except Exception:
            return None


def _redact(value: Any, vault: dict[str, Any]) -> Any:
    identity = vault.get("identity") or {}
    secrets = [str(identity.get("email") or ""), str(identity.get("phone") or "")]
    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "[redacted]")
        return result
    if isinstance(value, list):
        return [_redact(item, vault) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item, vault) for key, item in value.items()}
    return value


def _selected_bullets(vault: dict[str, Any], application: dict[str, Any]) -> list[dict[str, Any]]:
    locale = application["writing"]["locale"]
    selected = set(application["selection"].get("bullet_ids") or [])
    rows = []
    for section in ("experience", "projects"):
        for item in vault.get(section) or []:
            for bullet in item.get("bullets") or []:
                if bullet.get("id") in selected:
                    text = (bullet.get("text") or {}).get(locale) if isinstance(bullet.get("text"), dict) else bullet.get("text")
                    if text:
                        rows.append({"id": bullet.get("id"), "text": str(text)})
    return rows


def run_qa(
    root: Path,
    vault: dict[str, Any],
    application: dict[str, Any],
    *,
    template_id: str | None = None,
    draft: bool = False,
    browser_path: str | None = None,
) -> QAResult:
    directory = application_dir(root, application["slug"])
    html_path = directory / (application.get("output") or {}).get("html", "resume.html")
    checks: list[QACheck] = []
    metrics: dict[str, Any] = {}
    if not html_path.is_file():
        checks.append(
            QACheck(
                "qa.output",
                "fail",
                "No rendered HTML exists.",
                "Run `resume build <application>` first.",
            )
        )
        return QAResult("fail", checks, metrics)

    render_report = directory / "render.json"
    render_data = {}
    if render_report.is_file():
        try:
            render_data = json.loads(render_report.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    chosen_template = template_id or render_data.get("template_id") or application["template"]["id"]
    try:
        template = load_template(chosen_template, root=root)
    except ResumeProError as error:
        checks.append(QACheck("qa.template", "fail", error.message, error.fix))
        return QAResult("fail", checks, metrics)

    html_text = html_path.read_text(encoding="utf-8")
    info = _html_info(html_text)
    sections = application.get("selection") or {}
    enabled = [
        section["id"]
        for section in sorted(sections.get("sections") or [], key=lambda item: item.get("order", 99))
        if section.get("enabled")
    ]
    locale = application["writing"]["locale"]
    bullets = _selected_bullets(vault, application)

    browser = browser_path or find_browser()
    pdf = _browser_pdf(html_path, browser) if browser else None
    pdf_text = "\n".join(pdf[1]) if pdf else info["text"]
    pdf_norm = _norm(pdf_text)
    pages = pdf[0] if pdf else int((render_data.get("layout") or {}).get("pages") or 0)
    page_chars = pdf[2] if pdf else []
    last_height = pdf[3] if pdf else 0

    browser_status = "pass" if pdf else "warn"
    checks.append(
        QACheck(
            "qa.browser",
            browser_status,
            f"Checked with {Path(browser).name}." if pdf else "No headless browser found; page checks use estimates.",
            "" if pdf else "Install Edge/Chrome or set RESUME_PRO_BROWSER for true pagination QA.",
        )
    )

    # Parseability: text, headings, bullets, sections.
    text_ratio = len(pdf_text) / max(1, len(info["text"]))
    checks.append(
        QACheck(
            "qa.parseability.text",
            "pass" if text_ratio >= 0.6 else "fail",
            f"Extracted {len(pdf_text)} characters from a {len(info['text'])}-character document.",
            "" if text_ratio >= 0.6 else "Some text is clipped, hidden, or image-based; rebuild with a text-based template.",
        )
    )
    section_tags = set(info["sections"])
    missing_sections = [section for section in enabled if section not in section_tags]
    checks.append(
        QACheck(
            "qa.parseability.sections",
            "pass" if not missing_sections else "fail",
            "All enabled sections are present." if not missing_sections else f"Missing sections: {', '.join(missing_sections)}.",
            "" if not missing_sections else "Rebuild; an enabled section was removed or not rendered.",
        )
    )
    missing_headings = [
        section for section in enabled
        if info["headings"].get(section) and _norm(info["headings"][section]) not in pdf_norm
    ]
    checks.append(
        QACheck(
            "qa.parseability.headings",
            "pass" if not missing_headings else "fail",
            "All section headings are extractable." if not missing_headings else f"Headings missing from extracted text: {', '.join(missing_headings)}.",
            "" if not missing_headings else "Use standard headings and keep them as real text.",
        )
    )
    missing_bullets = []
    for bullet in bullets:
        probe = _norm(bullet["text"])[:40]
        if probe and probe not in pdf_norm:
            missing_bullets.append(bullet["id"])
    checks.append(
        QACheck(
            "qa.parseability.bullets",
            "pass" if not missing_bullets else "fail",
            f"{len(bullets) - len(missing_bullets)}/{len(bullets)} selected bullets found in extracted text.",
            "" if not missing_bullets else f"Missing bullets: {', '.join(missing_bullets[:6])}. Check clipping/overflow.",
        )
    )
    metrics.update(
        {
            "pages": pages,
            "text_chars": len(pdf_text),
            "html_chars": len(info["text"]),
            "selected_bullets": len(bullets),
            "found_bullets": len(bullets) - len(missing_bullets),
            "sections": len(enabled),
            "headings_found": len([s for s in enabled if info["headings"].get(s) and _norm(info["headings"][s]) in pdf_norm]),
        }
    )

    # Name/contact/education.
    name = str((vault.get("identity") or {}).get("full_name") or "")
    contact_ok = bool(EMAIL_RE.search(pdf_text) or PHONE_RE.search(pdf_text))
    checks.append(
        QACheck(
            "qa.content.name_contact",
            "pass" if name and _norm(name) in pdf_norm and contact_ok else "fail",
            "Name and contact are extractable." if name and _norm(name) in pdf_norm and contact_ok else "Name or contact is missing from the extracted text.",
            "" if name and _norm(name) in pdf_norm and contact_ok else "Keep name and one contact method as real text in the header.",
        )
    )
    education_ok = True
    if "education" in enabled and vault.get("education"):
        school = str((vault["education"][0] or {}).get("school") or "")
        education_ok = bool(school) and _norm(school) in pdf_norm
    checks.append(
        QACheck(
            "qa.content.education",
            "pass" if education_ok else "fail",
            "Education is visible." if education_ok else "The education entry is missing from the extracted text.",
            "" if education_ok else "Never omit education; keep school and dates as text.",
        )
    )

    # Layout.
    app_budget = application.get("page_budget") or {}
    maximum = int(app_budget.get("max", 2))
    target = int(app_budget.get("target", maximum))
    if pages == 0:
        checks.append(QACheck("qa.layout.pages", "warn", "Page count could not be measured.", "Install a headless browser."))
    elif pages > maximum:
        checks.append(
            QACheck(
                "qa.layout.pages",
                "fail",
                f"Rendered {pages} page(s); the application allows {maximum}.",
                "Cut weaker bullets or roles; do not shrink below 9pt.",
            )
        )
    else:
        checks.append(
            QACheck(
                "qa.layout.pages",
                "warn" if pages < target else "pass",
                f"Rendered {pages} page(s); target {target}, max {maximum}.",
                "" if pages >= target else "The output is shorter than the target; consider adding proof.",
            )
        )
    font_size = _font_size(html_text)
    checks.append(
        QACheck(
            "qa.layout.font_size",
            "fail" if font_size is not None and font_size < 9 else "warn" if font_size is not None and font_size < 10 else "pass" if font_size else "warn",
            f"Body font is {font_size}pt." if font_size else "Body font size could not be read.",
            "Keep body text at 10pt or larger; 9pt is the hard floor." if not font_size or font_size < 10 else "",
        )
    )
    metrics["font_size_pt"] = font_size

    outside = 0
    for char in page_chars:
        if (
            char["x0"] < -1
            or char["x1"] > char["page_width"] + 1
            or char["top"] < -1
            or char["bottom"] > char["page_height"] + 1
        ):
            outside += 1
    checks.append(
        QACheck(
            "qa.layout.outside_page",
            "pass" if outside == 0 else "fail",
            "All text is inside the page." if outside == 0 else f"{outside} characters sit outside the page.",
            "" if outside == 0 else "Fix margins, fixed widths, or absolute positioning.",
        )
    )

    if pdf and len(pdf[1]) > 1:
        heading_values = {_norm(value) for value in info["headings"].values() if value}
        orphan_pages = []
        for index, page_text in enumerate(pdf[1][:-1], start=1):
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            if lines and _norm(lines[-1]) in heading_values:
                orphan_pages.append(index)
        checks.append(
            QACheck(
                "qa.layout.orphan_heading",
                "pass" if not orphan_pages else "warn",
                "No orphan headings detected." if not orphan_pages else f"Orphan heading on page(s): {orphan_pages}.",
                "" if not orphan_pages else "Add break-inside: avoid or adjust spacing.",
            )
        )
    else:
        checks.append(QACheck("qa.layout.orphan_heading", "warn", "Orphan-heading check needs a multi-page browser render.", "Install a headless browser."))

    if page_chars and last_height:
        bottom = max((char["bottom"] for char in page_chars if char["page_height"] == last_height), default=0)
        whitespace = round(max(0.0, (last_height - bottom) / last_height) * 100)
        checks.append(
            QACheck(
                "qa.layout.whitespace",
                "warn" if pages > 1 and whitespace > 45 else "pass",
                f"Last page bottom whitespace is about {whitespace}%.",
                "" if not (pages > 1 and whitespace > 45) else "Rebalance the last page.",
            )
        )
        metrics["bottom_whitespace_pct"] = whitespace

    # Content checks on rendered text.
    cliche_hits = [phrase for phrase in CLICHES if phrase in pdf_text]
    checks.append(
        QACheck(
            "qa.content.cliche",
            "pass" if not cliche_hits else "warn",
            "No cliché phrases found." if not cliche_hits else f"{len(cliche_hits)} cliché phrase(s) found.",
            "" if not cliche_hits else "Replace clichés with behavior and evidence.",
        )
    )
    first_person = [item for item in info["items"] if FIRST_PERSON.search(item)]
    weak = [item for item in info["items"] if WEAK_START.search(item)]
    checks.append(
        QACheck(
            "qa.content.bullet_voice",
            "pass" if not first_person and not weak else "warn",
            "Bullets use action-first voice." if not first_person and not weak else f"{len(first_person)} first-person and {len(weak)} weak-start bullet(s) found.",
            "" if not first_person and not weak else "Lead with the result or action; drop pronouns.",
        )
    )
    if application["market"].startswith("cn_") and profile.is_student(application["persona"]):
        has_fundamentals = any(term in pdf_text.lower() for term in CS_TERMS)
        checks.append(
            QACheck(
                "qa.content.cs_fundamentals",
                "pass" if has_fundamentals else "fail",
                "CS fundamentals are visible." if has_fundamentals else "No CS fundamentals are visible in the rendered resume.",
                "" if has_fundamentals else "Add OS, networks, data structures, algorithms, and databases; campus written tests check them.",
            )
        )
    markers = "[NEEDS " in pdf_text
    checks.append(
        QACheck(
            "qa.content.locale_markers",
            "warn" if markers and draft else "fail" if markers else "pass",
            "No incomplete localization markers." if not markers else "Localization markers are present.",
            "" if not markers or draft else "Complete the target-language facts before delivery.",
        )
    )

    # Market checks.
    checks.append(
        QACheck(
            "qa.market.photo",
            "fail" if application["market"] == "intl_en" and info["images"] else "pass",
            "No photo in the rendered HTML." if not (application["market"] == "intl_en" and info["images"]) else "A photo appears in an intl_en resume.",
            "" if not (application["market"] == "intl_en" and info["images"]) else "Remove the photo.",
        )
    )
    sensitive = bool(PERSONAL_MARKERS.search(pdf_text))
    checks.append(
        QACheck(
            "qa.market.sensitive",
            "fail" if sensitive and application["market"] == "intl_en" else "warn" if sensitive else "pass",
            "No sensitive fields found." if not sensitive else "Sensitive fields appear in the rendered text.",
            "" if not sensitive else "Remove age/gender/marital/political fields for the target market.",
        )
    )
    if template["manifest"]["page"]["columns"] == "single":
        present = [section for section in info["sections"] if section in enabled]
        order_ok = present == [section for section in enabled if section in present]
        checks.append(
            QACheck(
                "qa.market.section_order",
                "pass" if order_ok else "fail",
                "Section order matches the application." if order_ok else "Section order differs from the application.",
                "" if order_ok else "Rebuild; the renderer should reorder single-column sections.",
            )
        )
    else:
        checks.append(QACheck("qa.market.section_order", "pass", "Two-column template; section presence checked, visual order is by design."))

    app_size = (application.get("page_budget") or {}).get("size")
    size_ok = not app_size or app_size in template["manifest"]["page"]["sizes"]
    checks.append(
        QACheck(
            "qa.market.page_size",
            "pass" if size_ok else "fail",
            f"Page size {app_size} is supported." if size_ok else f"Page size {app_size} is not supported by the template.",
            "" if size_ok else "Choose a compatible template.",
        )
    )

    checks.append(QACheck("qa.privacy.report", "pass", "QA report contains no contact PII."))
    status = "fail" if any(check.status == "fail" for check in checks) else "warn" if any(check.status == "warn" for check in checks) else "pass"
    result = QAResult(status=status, checks=checks, metrics=metrics, browser=browser if pdf else None)
    data = _redact(result.to_dict(), vault)
    result.checks = [QACheck(**item) for item in data["checks"]]
    return result
