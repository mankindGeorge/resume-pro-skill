# SPDX-License-Identifier: MIT
"""Learn a passing user template as a private, deterministic HTML template."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .errors import ResumeProError
from .ingest import IngestResult, detect_lang
from .paths import schema_dir
from .template_audit import TemplateAudit

SAFE_FALLBACK_FONTS = 'Arial, "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif'
HEADINGS = {
    "en": {
        "summary": "Summary",
        "education": "Education",
        "experience": "Experience",
        "projects": "Projects",
        "skills": "Skills",
        "awards": "Awards",
    },
    "zh": {
        "summary": "个人简介",
        "education": "教育经历",
        "experience": "实习经历",
        "projects": "项目经历",
        "skills": "专业技能",
        "awards": "荣誉奖项",
    },
}


class LearnError(ResumeProError):
    pass


@dataclass
class LearnResult:
    template_id: str
    directory: Path
    manifest_path: Path
    preview_path: Path
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "directory": str(self.directory),
            "manifest": str(self.manifest_path),
            "preview": str(self.preview_path),
            "warnings": self.warnings,
        }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _accent(layout) -> str:
    for color in layout.colors:
        value = color.strip().lower()
        if value in {"#000", "#000000", "black", "#222", "#1a1a1a", "#333"}:
            continue
        if re.fullmatch(r"#[0-9a-f]{3,8}", value) or value.startswith("rgb"):
            return value
    return "#1f3a5f"


def _font_stack(layout) -> str:
    candidates = [f for f in layout.font_families if f.strip() and f.strip().lower() not in {"sans-serif", "serif", "monospace"}]
    if candidates:
        first = candidates[0].strip().strip("'\"")
        return f'"{first}", {SAFE_FALLBACK_FONTS}'
    return SAFE_FALLBACK_FONTS


def _margins(layout) -> dict[str, float]:
    defaults = {"top": 18.0, "right": 18.0, "bottom": 18.0, "left": 18.0}
    result = {}
    for key, default in defaults.items():
        value = layout.margins_mm.get(key, default) if layout.margins_mm else default
        result[key] = round(max(12.0, float(value or default)), 1)
    return result


def _build_html(market: str, lang: str) -> str:
    h = HEADINGS[lang]
    return f'''<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Resume</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="resume-header">
    <h1 data-slot="identity.name"></h1>
    <div class="contact" data-slot="identity.contact"></div>
    <div class="links" data-slot="identity.links"></div>
  </header>

  <section class="section">
    <h2>{h["summary"]}</h2>
    <div data-slot="section.summary"></div>
  </section>

  <section class="section">
    <h2>{h["education"]}</h2>
    <div data-slot="section.education"></div>
  </section>

  <section class="section">
    <h2>{h["experience"]}</h2>
    <div data-slot="section.experience"></div>
  </section>

  <section class="section">
    <h2>{h["projects"]}</h2>
    <div data-slot="section.projects"></div>
  </section>

  <section class="section">
    <h2>{h["skills"]}</h2>
    <div data-slot="section.skills"></div>
  </section>

  <section class="section">
    <h2>{h["awards"]}</h2>
    <div data-slot="section.awards"></div>
  </section>

  <template data-slot="education.item">
    <article class="entry">
      <div class="entry-head">
        <span data-slot="education.item.school"></span>
        <span data-slot="education.item.dates"></span>
      </div>
      <div data-slot="education.item.degree"></div>
    </article>
  </template>

  <template data-slot="experience.item">
    <article class="entry">
      <div class="entry-head">
        <span data-slot="experience.item.company"></span>
        <span data-slot="experience.item.title"></span>
        <span data-slot="experience.item.dates"></span>
      </div>
      <ul>
        <template data-slot="experience.item.bullet">
          <li data-slot="experience.item.bullet.text"></li>
        </template>
      </ul>
    </article>
  </template>

  <template data-slot="project.item">
    <article class="entry">
      <div class="entry-head">
        <span data-slot="project.item.name"></span>
        <span data-slot="project.item.dates"></span>
      </div>
      <ul>
        <template data-slot="project.item.bullet">
          <li data-slot="project.item.bullet.text"></li>
        </template>
      </ul>
    </article>
  </template>

  <template data-slot="skill.item">
    <li data-slot="skill.item.name"></li>
  </template>
</body>
</html>
'''


def _build_css(layout, margins: dict[str, float], page_size: str) -> str:
    body_size = layout.body_font_size_pt or 10.5
    body_size = min(11.5, max(10.0, float(body_size)))
    line_height = layout.line_height or 1.35
    line_height = min(1.6, max(1.25, float(line_height)))
    return f''':root {{
  --font-body: {_font_stack(layout)};
  --font-heading: {_font_stack(layout)};
  --size-body: {body_size:.1f}pt;
  --line-height: {line_height:.2f};
  --accent: {_accent(layout)};
  --margin-top: {margins["top"]}mm;
  --margin-right: {margins["right"]}mm;
  --margin-bottom: {margins["bottom"]}mm;
  --margin-left: {margins["left"]}mm;
}}

@page {{
  size: {page_size.upper() if page_size == "a4" else "Letter"};
  margin: var(--margin-top) var(--margin-right) var(--margin-bottom) var(--margin-left);
}}

* {{ box-sizing: border-box; }}

html, body {{ margin: 0; padding: 0; }}

body {{
  font-family: var(--font-body);
  font-size: var(--size-body);
  line-height: var(--line-height);
  color: #1a1a1a;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}

.resume-header {{ text-align: center; margin-bottom: 6pt; }}
.resume-header h1 {{
  font-family: var(--font-heading);
  font-size: 1.7em;
  font-weight: 700;
  margin: 0 0 3pt;
  letter-spacing: 0.01em;
}}
.contact, .links {{ font-size: 0.92em; margin: 1pt 0; }}

.section {{ margin-top: 9pt; }}
.section h2 {{
  font-family: var(--font-heading);
  font-size: 1.05em;
  font-weight: 700;
  color: var(--accent);
  border-bottom: 0.8pt solid var(--accent);
  padding-bottom: 2pt;
  margin: 0 0 4pt;
  letter-spacing: 0.02em;
}}
.section:empty {{ display: none; }}

.entry {{ margin: 0 0 6pt; break-inside: avoid; }}
.entry-head {{
  display: flex;
  justify-content: space-between;
  gap: 8pt;
  font-weight: 600;
  margin-bottom: 1pt;
}}
.entry-head .dates {{ font-weight: 400; white-space: nowrap; color: #444; }}
ul {{ margin: 2pt 0 0 14pt; padding: 0; }}
li {{ margin: 1pt 0; }}

a {{ color: var(--accent); text-decoration: none; }}

@media print {{
  body {{ margin: 0; }}
  .section {{ break-inside: avoid; }}
}}
'''


def _build_manifest(
    *,
    template_id: str,
    market: str,
    persona: str,
    page_size: str,
    margins: dict[str, float],
    fingerprint: str,
    source_hash: str,
    source_name: str,
    lang: str,
) -> dict[str, Any]:
    return {
        "id": template_id,
        "name": "Learned user template",
        "language": "zh" if market.startswith("cn_") else "en",
        "version": "1.0.0",
        "status": "private",
        "description": f"Private template learned from {source_name}; not for redistribution.",
        "markets": [market],
        "personas": [persona],
        "page": {
            "sizes": [page_size],
            "margins_mm": margins,
            "target_pages": {"min": 1, "max": 2},
            "columns": "single",
        },
        "slots": {
            "required": [
                {"name": "identity.name", "selector": "[data-slot='identity.name']", "kind": "text"},
                {"name": "identity.contact", "selector": "[data-slot='identity.contact']", "kind": "text"},
                {"name": "section.education", "selector": "[data-slot='section.education']", "kind": "section"},
                {"name": "section.experience", "selector": "[data-slot='section.experience']", "kind": "section"},
                {"name": "section.projects", "selector": "[data-slot='section.projects']", "kind": "section"},
                {"name": "section.skills", "selector": "[data-slot='section.skills']", "kind": "section"},
            ],
            "optional": [
                {"name": "identity.links", "selector": "[data-slot='identity.links']", "kind": "list"},
                {"name": "section.summary", "selector": "[data-slot='section.summary']", "kind": "rich_text"},
                {"name": "section.awards", "selector": "[data-slot='section.awards']", "kind": "section"},
                {"name": "education.item", "selector": "[data-slot='education.item']", "kind": "list", "repeatable": True},
                {"name": "experience.item", "selector": "[data-slot='experience.item']", "kind": "list", "repeatable": True},
                {"name": "experience.item.bullet", "selector": "[data-slot='experience.item.bullet']", "kind": "list", "repeatable": True},
                {"name": "project.item", "selector": "[data-slot='project.item']", "kind": "list", "repeatable": True},
                {"name": "project.item.bullet", "selector": "[data-slot='project.item.bullet']", "kind": "list", "repeatable": True},
                {"name": "skill.item", "selector": "[data-slot='skill.item']", "kind": "list", "repeatable": True},
            ],
        },
        "budgets": {
            "summary_chars": {"en": 240, "zh": 120},
            "bullets_per_role": 5,
            "bullets_per_project": 4,
            "max_roles": 5,
            "max_projects": 4,
            "max_skills": 16,
        },
        "files": {
            "html": "template.html",
            "css": "styles.css",
            "preview": "preview.html",
            "print_css": "styles.css",
        },
        "print": {
            "safe_margin_mm": min(margins.values()),
            "bleed_mm": 0,
            "color_mode": "grayscale_safe",
        },
        "ats": {
            "single_column": True,
            "text_selectable": True,
            "tables_allowed": False,
            "standard_headings": [
                HEADINGS[lang]["education"],
                HEADINGS[lang]["experience"],
                HEADINGS[lang]["projects"],
                HEADINGS[lang]["skills"],
            ],
        },
        "editable_variant": False,
        "fingerprint": fingerprint,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "provenance": {
            "kind": "user_learned",
            "source_hash": source_hash,
            "note": f"Learned from {source_name}. Visual language is approximated; original file is unchanged. Private, non-redistributable.",
        },
    }


def _preview_resume(result: IngestResult, lang: str) -> str:
    fields = result.fields or {}
    h = HEADINGS[lang]
    parts: list[str] = []
    name = html.escape(str(fields.get("name") or "Your Name"))
    contact_bits = [fields.get("email"), fields.get("phone")]
    contact = " | ".join(html.escape(str(x)) for x in contact_bits if x)
    links = " · ".join(
        f'<a href="{html.escape(link["url"])}">{html.escape(link["url"])}</a>'
        for link in fields.get("links") or []
    )
    parts.append(f'<header class="resume-header"><h1>{name}</h1><div class="contact">{contact}</div><div class="links">{links}</div></header>')
    if fields.get("summary"):
        parts.append(f'<section class="section"><h2>{h["summary"]}</h2><p>{html.escape(str(fields["summary"]))}</p></section>')
    if fields.get("education"):
        parts.append(f'<section class="section"><h2>{h["education"]}</h2>')
        for entry in fields["education"]:
            title = " · ".join(str(entry.get(k)) for k in ("school", "degree", "major") if entry.get(k))
            dates = " – ".join(str(entry.get(k)) for k in ("start", "end") if entry.get(k))
            parts.append(f'<article class="entry"><div class="entry-head"><span>{html.escape(title)}</span><span class="dates">{html.escape(dates)}</span></div></article>')
        parts.append("</section>")
    if fields.get("experience"):
        parts.append(f'<section class="section"><h2>{h["experience"]}</h2>')
        for entry in fields["experience"]:
            head = " · ".join(str(entry.get(k)) for k in ("company", "title") if entry.get(k))
            dates = " – ".join(str(entry.get(k)) for k in ("start", "end") if entry.get(k))
            bullets = "".join(f"<li>{html.escape(str(b))}</li>" for b in entry.get("bullets") or [])
            parts.append(f'<article class="entry"><div class="entry-head"><span>{html.escape(head)}</span><span class="dates">{html.escape(dates)}</span></div><ul>{bullets}</ul></article>')
        parts.append("</section>")
    if fields.get("projects"):
        parts.append(f'<section class="section"><h2>{h["projects"]}</h2>')
        for entry in fields["projects"]:
            dates = " – ".join(str(entry.get(k)) for k in ("start", "end") if entry.get(k))
            bullets = "".join(f"<li>{html.escape(str(b))}</li>" for b in entry.get("bullets") or [])
            parts.append(f'<article class="entry"><div class="entry-head"><span>{html.escape(str(entry.get("name") or "Project"))}</span><span class="dates">{html.escape(dates)}</span></div><ul>{bullets}</ul></article>')
        parts.append("</section>")
    if fields.get("skills"):
        parts.append(f'<section class="section"><h2>{h["skills"]}</h2><p>{html.escape(", ".join(str(s) for s in fields["skills"]))}</p></section>')
    if fields.get("awards"):
        parts.append(f'<section class="section"><h2>{h["awards"]}</h2><ul>{"".join(f"<li>{html.escape(str(a))}</li>" for a in fields["awards"])}</ul></section>')
    return "".join(parts)


def build_preview(result: IngestResult, css_text: str, lang: str, source_name: str) -> str:
    original = html.escape(result.text or "")
    rebuilt = _preview_resume(result, lang)
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<title>Template preview</title>
<style>
{css_text}
body {{ background: #f3f4f6; margin: 0; padding: 16px; }}
.compare {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; max-width: 1400px; margin: 0 auto; }}
.pane {{ background: #fff; padding: 14px; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,.12); }}
.pane h3 {{ margin: 0 0 8px; font-size: 12pt; }}
pre {{ white-space: pre-wrap; font-size: 9pt; line-height: 1.35; color: #333; }}
.note {{ max-width: 1400px; margin: 0 auto 12px; font-size: 10pt; color: #444; }}
@media print {{ body {{ background: #fff; padding: 0; }} .compare {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="note"><strong>Preview only.</strong> Left: extracted text from {html.escape(source_name)}. Right: the learned layout with extracted content. The original file is unchanged; the vault remains the source of truth.</div>
<div class="compare">
  <div class="pane"><h3>Original text</h3><pre>{original}</pre></div>
  <div class="pane"><h3>Learned layout</h3><div class="resume">{rebuilt}</div></div>
</div>
</body>
</html>
'''


def _schema() -> dict[str, Any]:
    return json.loads((schema_dir() / "template.schema.json").read_text(encoding="utf-8"))


def learn_template(
    result: IngestResult,
    audit: TemplateAudit,
    *,
    project_root: Path,
    market: str,
    persona: str,
    force: bool = False,
    allow_failed: bool = False,
) -> LearnResult:
    if not audit.keep_allowed and not allow_failed:
        details = "; ".join(f"{d.id}: {d.detail}" for d in audit.hard_fails) or "the audit failed"
        raise LearnError(
            "template.audit_failed",
            f"Cannot keep this template: {details}",
            fix="Use one of the recommended templates, or record an explicit override.",
            details=audit.to_dict(),
        )

    source_bytes = result.path.read_bytes() if result.path.is_file() else (result.text or "").encode("utf-8")
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    template_id = f"user-{source_hash[:12]}"
    directory = Path(project_root) / "templates" / template_id
    if directory.exists() and not force:
        raise LearnError(
            "template.exists",
            f"A learned template already exists at {directory}.",
            fix="Use --force to rebuild it, or reuse the existing template.",
        )
    directory.mkdir(parents=True, exist_ok=True)

    lang = "zh" if market.startswith("cn_") else detect_lang(result.text or "")
    page_size = result.layout.page_size or ("a4" if market == "cn_internet" else "letter")
    if page_size not in {"a4", "letter"}:
        page_size = "a4" if market == "cn_internet" else "letter"
    margins = _margins(result.layout)
    html_text = _build_html(market, lang)
    css_text = _build_css(result.layout, margins, page_size)
    fingerprint = _sha256(html_text + "\n" + css_text)
    manifest = _build_manifest(
        template_id=template_id,
        market=market,
        persona=persona,
        page_size=page_size,
        margins=margins,
        fingerprint=fingerprint,
        source_hash=source_hash,
        source_name=result.path.name,
        lang=lang,
    )

    validator = Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        raise LearnError(
            "template.manifest_invalid",
            f"Learned template manifest is invalid: {first.message}",
            path=".".join(str(p) for p in first.path),
            fix="This is a bug in template_learn.py; report it.",
        )

    (directory / "template.html").write_text(html_text, encoding="utf-8")
    (directory / "styles.css").write_text(css_text, encoding="utf-8")
    preview = build_preview(result, css_text, lang, result.path.name)
    (directory / "preview.html").write_text(preview, encoding="utf-8")
    (directory / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    warnings = list(result.warnings)
    if not audit.keep_allowed:
        warnings.append("The template audit failed; this learned template exists because an explicit override was recorded.")
    if result.layout.columns >= 2:
        warnings.append("The original used multiple columns; the learned template is single-column for parseability.")
    if not result.layout.editable_source:
        warnings.append("The source was a PDF; spacing and fonts are approximated.")

    return LearnResult(
        template_id=template_id,
        directory=directory,
        manifest_path=directory / "manifest.json",
        preview_path=directory / "preview.html",
        warnings=warnings,
    )


def load_learned_template(directory: Path | str) -> dict[str, Any]:
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise LearnError(
            "template.not_found",
            f"No learned template at {directory}.",
            fix="Run `resume template-import` or `resume optimize --keep-template` first.",
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(_schema())
    errors = sorted(validator.iter_errors(manifest), key=lambda e: list(e.path))
    if errors:
        raise LearnError(
            "template.invalid_manifest",
            f"Invalid learned template manifest: {errors[0].message}",
            path=".".join(str(p) for p in errors[0].path),
            fix="Rebuild the template with `resume template-import --force`.",
        )
    if manifest.get("id") != directory.name:
        raise LearnError(
            "template.id_mismatch",
            f"Manifest id {manifest.get('id')!r} does not match directory {directory.name!r}.",
            fix="Rename the directory or rebuild the template.",
        )
    html_path = directory / manifest["files"]["html"]
    css_path = directory / manifest["files"]["css"]
    return {
        "manifest": manifest,
        "html": html_path.read_text(encoding="utf-8") if html_path.is_file() else "",
        "css": css_path.read_text(encoding="utf-8") if css_path.is_file() else "",
    }
