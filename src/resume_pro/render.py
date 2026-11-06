# SPDX-License-Identifier: MIT
"""Deterministic HTML renderer. No LLM touches the markup."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from .errors import ResumeProError
from . import profile
from .layout import LayoutError, LayoutReport, check_layout
from .paths import schema_dir, templates_dir

TEMPLATE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SECTION_IDS = (
    "summary",
    "education",
    "experience",
    "projects",
    "skills",
    "awards",
    "certificates",
    "languages",
    "publications",
    "open_source",
)
_TEXT_SLOTS = (
    "identity.name",
    "identity.contact",
    "identity.links",
    "section.summary",
)
_SKILL_KIND_LABELS = {
    "language": {"en": "Languages", "zh": "编程语言"},
    "framework": {"en": "Frameworks", "zh": "框架"},
    "fundamentals": {"en": "CS Fundamentals", "zh": "计算机基础"},
    "ai_ml": {"en": "AI / ML", "zh": "AI / 机器学习"},
    "tool": {"en": "Tools", "zh": "工具"},
    "other": {"en": "Skills", "zh": "技能"},
}


class RenderError(ResumeProError):
    pass


@dataclass
class RenderResult:
    template_id: str
    fingerprint: str
    html_path: Path
    editable_path: Path
    report_path: Path
    layout: LayoutReport
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "fingerprint": self.fingerprint,
            "html": str(self.html_path),
            "editable_html": str(self.editable_path),
            "report": str(self.report_path),
            "layout": self.layout.to_dict(),
            "warnings": self.warnings,
            "format": "html",
        }


def _schema() -> dict[str, Any]:
    return json.loads((schema_dir() / "template.schema.json").read_text(encoding="utf-8"))


def _localized(value: Any, locale: str) -> str:
    if isinstance(value, dict):
        if value.get(locale):
            return str(value[locale])
        for candidate in value.values():
            if candidate:
                return str(candidate)
        return ""
    return str(value or "")


def _dates(entry: dict[str, Any], locale: str) -> str:
    start = str(entry.get("start") or "")
    end = str(entry.get("end") or "")
    present = "至今" if locale == "zh" else "Present"
    if locale == "zh":
        start = start.replace("-", ".")
        end = present if end == "present" else end.replace("-", ".")
    else:
        end = present if end == "present" else end
    if start and end:
        return f"{start} – {end}"
    return start or end


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _safe_url(url: str) -> str | None:
    value = str(url or "").strip()
    if re.match(r"^(https?://|mailto:)", value, re.IGNORECASE):
        return value
    return None


def _link(link: dict[str, Any]) -> str:
    url = _safe_url(link.get("url", ""))
    if not url:
        return ""
    label = _escape(link.get("label") or url)
    return f'<a href="{_escape(url)}" rel="noopener">{label}</a>'


def _filtered(vault: dict[str, Any], collection: str, selected: set[str]) -> list[dict[str, Any]]:
    items = [item for item in vault.get(collection) or [] if item.get("id") in selected]
    for item in items:
        if not item.get("id"):
            raise RenderError(
                "render.missing_id",
                f"An entry in {collection} has no id.",
                fix="Run `resume check` and repair the vault; every fact needs a stable id.",
            )
    return items


def _selected_bullets(item: dict[str, Any], selected: set[str], order: dict[str, int]) -> list[dict[str, Any]]:
    bullets = [b for b in item.get("bullets") or [] if b.get("id") in selected]
    bullets.sort(key=lambda b: order.get(b.get("id"), 9999))
    return bullets


def application_locale(application: dict[str, Any]) -> str:
    """Use the resume's writing language, defaulting to its market profile."""
    return (application.get("writing") or {}).get("locale") or profile.load_market(application["market"])["language"]


def build_render_model(vault: dict[str, Any], application: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    selection = application.get("selection") or {}
    fact_ids = set(selection.get("fact_ids") or [])
    bullet_ids = set(selection.get("bullet_ids") or [])
    bullet_order = {bullet_id: index for index, bullet_id in enumerate(selection.get("bullet_ids") or [])}
    locale = application_locale(application)

    identity = vault.get("identity") or {}
    contact_parts = [identity.get("email"), identity.get("phone")]
    location = identity.get("location") or {}
    location_keys = ("city", "region") if str(application.get("market", "")).startswith("cn_") else ("city", "region", "country")
    location_text = " · ".join(str(location.get(key)) for key in location_keys if location.get(key))
    if location_text:
        contact_parts.append(location_text)
    contact = " · ".join(str(part) for part in contact_parts if part)
    links = " · ".join(filter(None, (_link(link) for link in identity.get("links") or [])))
    photo_uri = ""
    photo_value = identity.get("photo")
    policy = profile.load_market(application.get("market", "intl_en")).get("photo_policy")
    if photo_value and policy != "forbidden":
        photo_path = Path(str(photo_value))
        if not photo_path.is_absolute() and root is not None:
            photo_path = Path(root) / photo_path
        if not photo_path.is_file():
            raise RenderError(
                "render.photo_missing",
                f"Photo not found at {photo_path}.",
                fix="Run `resume photo <file>` again or remove `identity.photo` from the vault.",
            )
        mime = mimetypes.guess_type(photo_path.name)[0] or "image/jpeg"
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise RenderError(
                "render.photo_format",
                f"Unsupported photo type {mime!r}.",
                fix="Use JPEG, PNG, or WebP.",
            )
        photo_uri = f"data:{mime};base64,{base64.b64encode(photo_path.read_bytes()).decode('ascii')}"

    education = []
    for item in _filtered(vault, "education", fact_ids):
        degree = _localized(item.get("degree"), locale)
        major = _localized(item.get("major"), locale)
        note = [degree] if degree else []
        if item.get("gpa"):
            gpa = item["gpa"]
            gpa_label = "绩点" if locale == "zh" else "GPA"
            note.append(f"{gpa_label} {gpa.get('value')}/{gpa.get('scale')}")
        education.append(
            {
                "title": item.get("school") or "",
                "dates": _dates(item, locale),
                "sub": major,
                "note": " · ".join(note),
            }
        )
    education.sort(key=lambda entry: str(entry.get("dates", "")), reverse=True)

    experience = []
    for item in _filtered(vault, "experience", fact_ids):
        bullets = _selected_bullets(item, bullet_ids, bullet_order)
        experience.append(
            {
                "title": " — ".join(
                    part for part in (item.get("company"), _localized(item.get("title"), locale)) if part
                ),
                "dates": _dates(item, locale),
                "bullets": [ _localized(b.get("text"), locale) for b in bullets ],
            }
        )
    experience.sort(key=lambda entry: str(entry.get("dates", "")), reverse=True)

    projects = []
    for item in _filtered(vault, "projects", fact_ids):
        bullets = _selected_bullets(item, bullet_ids, bullet_order)
        projects.append(
            {
                "title": item.get("name") or "",
                "dates": _dates(item, locale),
                "sub": _localized(item.get("role"), locale),
                "bullets": [ _localized(b.get("text"), locale) for b in bullets ],
                "context": item.get("context"),
                "links": item.get("links") or [],
            }
        )

    skills = []
    for group in _filtered(vault, "skills", fact_ids):
        name = _localized(group.get("name"), locale) or _SKILL_KIND_LABELS.get(group.get("kind"), {}).get(locale, "")
        items = [str(item.get("name")) for item in group.get("items") or [] if item.get("name")]
        if items:
            skills.append({"label": name, "items": items, "kind": group.get("kind")})

    awards = [
        _localized(item.get("title"), locale)
        for item in _filtered(vault, "awards", fact_ids)
        if _localized(item.get("title"), locale)
    ]
    certificates = [
        " — ".join(part for part in (_localized(item.get("name"), locale), item.get("issuer")) if part)
        for item in _filtered(vault, "certificates", fact_ids)
    ]
    languages = [
        " — ".join(part for part in (_localized(item.get("name"), locale), item.get("proficiency")) if part)
        for item in _filtered(vault, "languages", fact_ids)
    ]
    publications = [
        " — ".join(part for part in (item.get("title"), item.get("venue"), item.get("date")) if part)
        for item in _filtered(vault, "publications", fact_ids)
    ]
    open_source = [
        project
        for project in projects
        if project.get("context") == "open_source"
    ]

    sections = sorted(
        application.get("selection", {}).get("sections") or [],
        key=lambda section: int(section.get("order", 99)),
    )
    return {
        "locale": locale,
        "identity": {
            "name": identity.get("full_name") or "",
            "contact": contact,
            "links": links,
            "photo": photo_uri,
        },
        "summary": _localized(selection.get("summary"), locale),
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skills,
        "awards": awards,
        "certificates": certificates,
        "languages": languages,
        "publications": publications,
        "open_source": open_source,
        "sections": sections,
    }


def _entry_head(title: str, dates: str) -> str:
    return (
        '<div class="entry-head">'
        f'<span class="entry-title">{_escape(title)}</span>'
        f'<span class="entry-meta">{_escape(dates)}</span>'
        "</div>"
    )


def _bullets(bullets: list[str]) -> str:
    if not bullets:
        return ""
    items = "".join(f"<li>{_escape(text)}</li>" for text in bullets if text)
    return f"<ul>{items}</ul>"


def _list(items: list[str]) -> str:
    values = "".join(f"<li>{_escape(item)}</li>" for item in items if item)
    return f'<ul class="simple-list">{values}</ul>' if values else ""


def _section_content(section: str, model: dict[str, Any]) -> str:
    locale = model["locale"]
    if section == "summary":
        text = model.get("summary") or ""
        return f"<p>{_escape(text).replace(chr(10), '<br>')}</p>" if text else ""
    if section == "education":
        return "".join(
            f'<div class="entry">{_entry_head(entry["title"], entry["dates"])}'
            + (f'<div class="entry-sub">{_escape(entry["sub"])}</div>' if entry.get("sub") else "")
            + (f'<div class="entry-note">{_escape(entry["note"])}</div>' if entry.get("note") else "")
            + "</div>"
            for entry in model.get("education") or []
        )
    if section == "experience":
        return "".join(
            f'<div class="entry">{_entry_head(entry["title"], entry["dates"])}{_bullets(entry["bullets"])}</div>'
            for entry in model.get("experience") or []
        )
    if section == "projects":
        return "".join(
            f'<div class="entry">{_entry_head(entry["title"], entry["dates"])}'
            + (f'<div class="entry-sub">{_escape(entry["sub"])}</div>' if entry.get("sub") else "")
            + f'{_bullets(entry["bullets"])}</div>'
            for entry in model.get("projects") or []
        )
    if section == "skills":
        rows = []
        for group in model.get("skills") or []:
            separator = "、" if locale == "zh" else ", "
            rows.append(
                f'<div class="skill-row"><span class="skill-label">{_escape(group["label"])}</span>'
                f'<span class="skill-values">{_escape(separator.join(group["items"]))}</span></div>'
            )
        return "".join(rows)
    if section == "awards":
        return _list(model.get("awards") or [])
    if section == "certificates":
        return _list(model.get("certificates") or [])
    if section == "languages":
        return _list(model.get("languages") or [])
    if section == "publications":
        return _list(model.get("publications") or [])
    if section == "open_source":
        rows = []
        for project in model.get("open_source") or []:
            links = " ".join(filter(None, (_link(link) for link in project.get("links") or [])))
            rows.append(f'<li>{_escape(project["title"])}{(" " + links) if links else ""}</li>')
        return f'<ul class="simple-list">{"".join(rows)}</ul>' if rows else ""
    return ""


def _replace_slot(source: str, slot: str, content: str) -> str:
    pattern = re.compile(
        r'(<(?P<tag>[a-zA-Z][a-zA-Z0-9]*)\b[^>]*\bdata-slot="' + re.escape(slot) + r'"[^>]*>)(?P<inner>.*?)(</(?P=tag)>)',
        re.DOTALL,
    )
    if not pattern.search(source):
        raise RenderError(
            "render.missing_slot",
            f"Template is missing the required slot {slot!r}.",
            fix="Repair the template manifest/html, or choose another template.",
        )
    return pattern.sub(lambda match: match.group(1) + content + match.group(4), source, count=1)


def _remove_section(source: str, section: str) -> str:
    pattern = re.compile(
        r'<section\b[^>]*\bdata-section="' + re.escape(section) + r'"[^>]*>.*?</section>',
        re.DOTALL,
    )
    return pattern.sub("", source)


def load_template(
    template_id: str, *, root: Path | None = None, language: str | None = None,
) -> dict[str, Any]:
    """Resolve a layout and language; never silently pick between language variants."""
    if language is not None and language not in {"zh", "en"}:
        raise RenderError(
            "render.invalid_language",
            f"Unsupported template language {language!r}.",
            fix="Use `zh` (templates/cn) or `en` (templates/en).",
        )
    if not TEMPLATE_ID_RE.match(template_id):
        raise RenderError(
            "render.invalid_template_id",
            f"Invalid template id {template_id!r}.",
            fix="Use a lowercase id such as `ats-classic` or a learned `user-*` template.",
        )
    base = Path(root) / "templates" if template_id.startswith("user-") and root is not None else templates_dir()
    folders = [{"zh": "cn", "en": "en"}[language]] if language else ["cn", "en"]
    candidates = [base / folder / template_id for folder in folders]
    candidates.append(base / template_id)  # Legacy flat learned templates remain supported.
    existing = [candidate for candidate in candidates if (candidate / "manifest.json").is_file()]
    if not existing:
        raise RenderError(
            "render.template_missing",
            f"No template named {template_id!r} for language {language!r}.",
            fix="Run `resume templates` and select a layout available in the requested language.",
        )
    if language is None and len(existing) > 1:
        raise RenderError(
            "render.template_language_required",
            f"Template {template_id!r} has multiple language variants.",
            fix="Pass language='zh' or language='en' when loading this layout.",
        )
    directory = existing[0]
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(_schema()).iter_errors(manifest), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        raise RenderError(
            "render.manifest_invalid",
            f"Template manifest is invalid: {first.message}",
            path=".".join(str(part) for part in first.path),
            fix="Repair the manifest before rendering.",
        )
    if manifest.get("id") != template_id:
        raise RenderError(
            "render.template_id_mismatch",
            f"Manifest id {manifest.get('id')!r} does not match {template_id!r}.",
            fix="Make the directory and manifest id identical.",
        )
    if language is not None and manifest.get("language") != language:
        raise RenderError(
            "render.language_mismatch",
            f"Template {template_id!r} is for {manifest.get('language')!r}, not {language!r}.",
            fix="Choose or provide a template variant in the requested resume language.",
        )
    html_path = directory / manifest["files"]["html"]
    css_path = directory / manifest["files"]["css"]
    if not html_path.is_file() or not css_path.is_file():
        raise RenderError(
            "render.template_files_missing",
            f"Template {template_id!r} is missing its HTML or CSS file.",
            fix="Restore the template files.",
        )
    template_html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")
    for slot in manifest["slots"]["required"]:
        if f'data-slot="{slot["name"]}"' not in template_html:
            raise RenderError(
                "render.missing_slot",
                f"Template {template_id!r} declares {slot['name']!r} but does not contain it.",
                fix="Repair the template HTML or manifest.",
            )
    fingerprint = hashlib.sha256((template_html + "\n" + css).encode("utf-8")).hexdigest()
    if fingerprint != manifest.get("fingerprint"):
        raise RenderError(
            "render.fingerprint_mismatch",
            f"Template {template_id!r} has changed since its manifest was signed.",
            fix="Recompute the fingerprint or restore the template.",
        )
    clean = BeautifulSoup(template_html, "html.parser")
    for tag in clean.find_all("template"):
        tag.decompose()
    return {
        "id": template_id,
        "directory": directory,
        "manifest": manifest,
        "html": str(clean),
        "css": css,
        "fingerprint": fingerprint,
    }


def _reorder_sections(source: str, model: dict[str, Any]) -> str:
    soup = BeautifulSoup(source, "html.parser")
    tags = {
        tag.get("data-section"): tag
        for tag in soup.find_all("section", attrs={"data-section": True})
    }
    if not tags:
        return source
    ordering = [section["id"] for section in model.get("sections") or [] if section.get("enabled")]
    groups: dict[int, tuple[Any, list[Any]]] = {}
    for section in ordering:
        tag = tags.get(section)
        if tag is None or tag.parent is None:
            continue
        parent = tag.parent
        groups.setdefault(id(parent), (parent, []))[1].append(tag)
    if not groups:
        return source
    for parent, group in groups.values():
        for tag in group:
            tag.extract()
        for tag in group:
            parent.append(tag)
    return str(soup)


def _banner_styles() -> str:
    return """<style>
.draft-banner{position:fixed;top:0;left:0;right:0;background:#b00020;color:#fff;text-align:center;
font:600 10pt Arial,sans-serif;padding:4pt;z-index:9999;letter-spacing:.04em}
body[data-draft="true"]{padding-top:24pt}
@media print{.draft-banner{position:fixed;top:0;left:0;right:0}.edit-toolbar{display:none}body.editable{padding-top:0}}
.edit-toolbar{position:fixed;top:0;left:0;right:0;background:#111;color:#fff;padding:5pt 8pt;
font:10pt Arial,sans-serif;display:flex;gap:8pt;align-items:center;z-index:9999}
.edit-toolbar button{font:10pt Arial,sans-serif;padding:2pt 6pt;cursor:pointer}
.edit-note{font-size:9pt;color:#ddd;margin-left:auto}
body.editable{padding-top:34pt}
</style>"""


def render_html(
    template: dict[str, Any],
    model: dict[str, Any],
    application: dict[str, Any],
    *,
    draft: bool = False,
    editable: bool = False,
) -> str:
    source = template["html"]
    source = re.sub(
        r'<link\b[^>]*href="styles.css"[^>]*>',
        lambda match: "<style>\n" + template["css"] + "\n</style>",
        source,
        count=1,
    )
    enabled = {
        section["id"]
        for section in model.get("sections") or []
        if section.get("enabled")
    }
    for section in SECTION_IDS:
        if section not in enabled:
            source = _remove_section(source, section)
            continue
        content = _section_content(section, model)
        if not content:
            source = _remove_section(source, section)
            continue
        if section == "summary":
            source = _replace_slot(source, "section.summary", content)
        else:
            source = _replace_slot(source, f"section.{section}", content)

    source = _replace_slot(source, "identity.name", _escape(model["identity"]["name"]))
    source = _replace_slot(source, "identity.contact", _escape(model["identity"]["contact"]))
    if 'data-slot="identity.links"' in source:
        source = _replace_slot(source, "identity.links", model["identity"]["links"])
    if 'data-slot="identity.photo"' in source:
        photo = model["identity"].get("photo") or ""
        alt = "照片" if model.get("locale") == "zh" else "Portrait"
        source = _replace_slot(
            source,
            "identity.photo",
            f'<img src="{_escape(photo)}" alt="{_escape(alt)}">' if photo else "",
        )
        if photo:
            source = re.sub(r"(<body[^>]*)(>)", r'\1 data-photo="true"\2', source, count=1)

    source = _reorder_sections(source, model)

    extra_styles = _banner_styles()
    source = source.replace("</head>", extra_styles + "</head>", 1)
    if draft:
        source = re.sub(r"(<body[^>]*)(>)", r'\1 data-draft="true"\2', source, count=1)
        source = re.sub(r"(<body[^>]*>)", r'\1<div class="draft-banner">DRAFT — NOT FOR SUBMISSION</div>', source, count=1)

    if editable:
        if re.search(r'<body[^>]*class="', source):
            source = re.sub(r'(<body[^>]*class=")', r'\1editable ', source, count=1)
        else:
            source = re.sub(r"<body", '<body class="editable"', source, count=1)
        for slot in _TEXT_SLOTS:
            source = re.sub(
                r'(<[a-zA-Z][a-zA-Z0-9]*\b[^>]*\bdata-slot="' + re.escape(slot) + r'"[^>]*)(>)',
                r'\1 contenteditable="true"\2',
                source,
            )
        toolbar = (
            '<div class="edit-toolbar" contenteditable="false">'
            "<strong>EDITABLE PREVIEW</strong>"
            "<button type=\"button\" onclick=\"document.execCommand('bold')\"><b>B</b></button>"
            "<button type=\"button\" onclick=\"var b=document.body;var s=parseFloat(getComputedStyle(b).fontSize);b.style.fontSize=(s+0.5)+'px'\">A+</button>"
            "<button type=\"button\" onclick=\"var b=document.body;var s=parseFloat(getComputedStyle(b).fontSize);b.style.fontSize=Math.max(8,s-0.5)+'px'\">A−</button>"
            '<span class="edit-note">The vault is the source of truth; browser edits are not merged back.</span>'
            "</div>"
        )
        source = re.sub(r"(<body[^>]*>)", r"\1" + toolbar, source, count=1)
    return source


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def render_application(
    root: Path,
    vault: dict[str, Any],
    application: dict[str, Any],
    *,
    template_id: str | None = None,
    draft: bool = False,
) -> RenderResult:
    chosen = template_id or application["template"]["id"]
    template = load_template(chosen, root=root, language=application_locale(application))
    app_size = (application.get("page_budget") or {}).get("size")
    if app_size and app_size not in (template["manifest"].get("page") or {}).get("sizes", []):
        raise RenderError(
            "render.page_size_mismatch",
            f"Template {chosen!r} does not support the application page size {app_size!r}.",
            fix="Choose a template with the right page size, or change the application market.",
        )
    model = build_render_model(vault, application, root=root)
    layout = check_layout(model, template["manifest"], application)
    html_output = render_html(template, model, application, draft=draft, editable=False)
    editable_output = render_html(template, model, application, draft=draft, editable=True)
    directory = root / ".resume" / "applications" / application["slug"]
    directory.mkdir(parents=True, exist_ok=True)
    html_path = directory / application["output"].get("html", "resume.html")
    editable_path = directory / application["output"].get("editable_html", "resume-editable.html")
    report_path = directory / "render.json"
    _atomic_write(html_path, html_output)
    _atomic_write(editable_path, editable_output)
    result = RenderResult(
        template_id=chosen,
        fingerprint=template["fingerprint"],
        html_path=html_path,
        editable_path=editable_path,
        report_path=report_path,
        layout=layout,
        warnings=list(layout.warnings),
    )
    _atomic_write(report_path, json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n")
    return result
