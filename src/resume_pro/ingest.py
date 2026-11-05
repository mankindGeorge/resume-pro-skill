# SPDX-License-Identifier: MIT
"""Resume ingestion: extract text, facts, and layout DNA from common formats."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .errors import ResumeProError
from .vault import next_id

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{4}")
DATE_RANGE_RE = re.compile(
    r"((?:19|20)\d{2})(?:[./-](\d{1,2}))?\s*(?:[-–—~至到]|to)\s*((?:19|20)\d{2}|present|now|至今|现在|目前)(?:[./-](\d{1,2}))?",
    re.IGNORECASE,
)
DATE_RANGE_ZH_RE = re.compile(r"((?:19|20)\d{2})[./年-](\d{1,2})?月?\s*[-–—~至到]\s*((?:19|20)\d{2}|至今|现在|目前)[./年-]?(\d{1,2})?月?")
GPA_RE = re.compile(r"(?:GPA|绩点)\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[-•*·▪◦●○–—]\s+")

SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "summary": (r"summary", r"profile", r"about me", r"about", r"个人简介", r"自我评价", r"个人总结", r"个人优势"),
    "job_intent": (r"job intent", r"objective", r"career objective", r"求职意向", r"目标岗位"),
    "education": (r"education", r"education & training", r"academic background", r"教育经历", r"教育背景", r"学历"),
    "experience": (
        r"experience",
        r"work experience",
        r"professional experience",
        r"employment history",
        r"employment",
        r"工作经历",
        r"实习经历",
        r"职业经历",
    ),
    "projects": (r"projects", r"project experience", r"selected projects", r"项目经历", r"项目经验", r"项目"),
    "skills": (r"skills", r"technical skills", r"core skills", r"专业技能", r"技能", r"技能清单"),
    "awards": (r"awards", r"honors", r"honours", r"荣誉奖项", r"获奖经历", r"奖项"),
    "certificates": (r"certifications", r"certificates", r"证书", r"资格证书"),
    "languages": (r"languages", r"语言", r"语言能力"),
    "publications": (r"publications", r"papers", r"论文", r"发表论文"),
    "open_source": (r"open source", r"开源", r"开源项目"),
}

SCHOOL_RE = re.compile(r"university|college|institute|school|academy|大学|学院|学校|中学", re.IGNORECASE)
DEGREE_RE = re.compile(
    r"bachelor|master|doctor|ph\.?d|b\.?s\.?|m\.?s\.?|b\.?eng|m\.?eng|mba|本科|硕士|博士|学士|大专|研究生",
    re.IGNORECASE,
)
ROLE_RE = re.compile(
    r"engineer|developer|intern|manager|analyst|designer|scientist|consultant|lead|architect|director|"
    r"工程师|开发|实习生|经理|分析师|设计师|科学家|顾问|负责人|架构师|主管",
    re.IGNORECASE,
)
COMPANY_RE = re.compile(r"inc|ltd|llc|corp|corporation|company|group|technologies|labs|公司|科技|集团|有限", re.IGNORECASE)
DEFAULT_FONTS = {"times new roman", "arial", "helvetica", "calibri", "georgia", "garamond", "sans-serif", "serif"}


class IngestError(ResumeProError):
    pass


@dataclass
class LayoutDNA:
    format: str
    page_size: str | None = None
    page_width_mm: float | None = None
    page_height_mm: float | None = None
    margins_mm: dict[str, float] = field(default_factory=dict)
    columns: int = 1
    font_families: list[str] = field(default_factory=list)
    font_sizes_pt: list[float] = field(default_factory=list)
    body_font_size_pt: float | None = None
    line_height: float | None = None
    colors: list[str] = field(default_factory=list)
    images: int = 0
    photo_likely: bool = False
    tables: int = 0
    absolute_positioned: int = 0
    overflow_hidden: int = 0
    text_outside_page: int = 0
    editable_source: bool = True
    visual_identity: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "page_size": self.page_size,
            "page_width_mm": self.page_width_mm,
            "page_height_mm": self.page_height_mm,
            "margins_mm": self.margins_mm,
            "columns": self.columns,
            "font_families": self.font_families,
            "font_sizes_pt": self.font_sizes_pt,
            "body_font_size_pt": self.body_font_size_pt,
            "line_height": self.line_height,
            "colors": self.colors,
            "images": self.images,
            "photo_likely": self.photo_likely,
            "tables": self.tables,
            "absolute_positioned": self.absolute_positioned,
            "overflow_hidden": self.overflow_hidden,
            "text_outside_page": self.text_outside_page,
            "editable_source": self.editable_source,
            "visual_identity": self.visual_identity,
            "notes": self.notes,
        }


@dataclass
class IngestResult:
    path: Path
    format: str
    text: str
    fields: dict[str, Any]
    layout: LayoutDNA
    confidence: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    needs_confirmation: list[str] = field(default_factory=list)
    scanned: bool = False
    page_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "format": self.format,
            "page_count": self.page_count,
            "scanned": self.scanned,
            "characters": len(self.text),
            "confidence": self.confidence,
            "warnings": self.warnings,
            "needs_confirmation": self.needs_confirmation,
            "layout": self.layout.to_dict(),
            "fields": self.fields,
        }


def ingest_file(path: Path | str) -> IngestResult:
    path = Path(path)
    if not path.is_file():
        raise IngestError("ingest.not_found", f"No file at {path}.", fix="Check the path and try again.")
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _ingest_docx(path)
    if suffix == ".pdf":
        return _ingest_pdf(path)
    if suffix in {".html", ".htm"}:
        return _ingest_html(path)
    if suffix in {".md", ".markdown", ".txt"}:
        return _ingest_text(path)
    if suffix in {".doc", ".rtf"}:
        return _ingest_legacy(path)
    raise IngestError(
        "ingest.unsupported_format",
        f"Unsupported format {suffix or '(none)'}.",
        fix="Use DOCX, text-based PDF, HTML, MD, or TXT. Images/OCR are not supported in v1.",
    )


def _read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def _ingest_text(path: Path) -> IngestResult:
    text = _read_text(path)
    layout = LayoutDNA(format=path.suffix.lstrip(".") or "txt", notes=["Layout cannot be audited from plain text."])
    fields, confidence, notes = extract_fields(text)
    return IngestResult(
        path=path,
        format=layout.format,
        text=text,
        fields=fields,
        layout=layout,
        confidence=confidence,
        warnings=notes + ["Plain text has no layout information; template audit will be limited."],
        needs_confirmation=_needs_confirmation(fields, confidence, market=None),
    )


def _html_to_text(soup) -> str:
    from bs4.element import Doctype, NavigableString

    blocks = {
        "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6",
        "tr", "section", "article", "header", "footer", "br", "table",
    }
    parts: list[str] = []
    for element in soup.descendants:
        if isinstance(element, Doctype):
            continue
        if isinstance(element, NavigableString):
            value = str(element).strip()
            if value:
                parts.append(value + " ")
        elif getattr(element, "name", None) in blocks:
            parts.append("\n")
    text = "".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def _ingest_html(path: Path) -> IngestResult:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise IngestError(
            "ingest.dependency_missing",
            "HTML ingestion needs beautifulsoup4.",
            fix="Install it with `pip install beautifulsoup4` or reinstall the project.",
        ) from exc

    raw = _read_text(path)
    soup = BeautifulSoup(raw, "html.parser")
    css = "\n".join(style.get_text(" ") for style in soup.find_all("style"))
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel") or []).lower()
        href = link.get("href") or ""
        if "stylesheet" in rel and not href.startswith(("http://", "https://", "//")):
            css_path = (path.parent / href).resolve()
            if css_path.is_file():
                css += "\n" + _read_text(css_path)

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for item in soup.find_all("li"):
        item.insert(0, "- ")
    text = _html_to_text(soup)
    fields, confidence, notes = extract_fields(text)
    layout = _layout_from_html(soup, css, path)
    return IngestResult(
        path=path,
        format="html",
        text=text,
        fields=fields,
        layout=layout,
        confidence=confidence,
        warnings=notes,
        needs_confirmation=_needs_confirmation(fields, confidence, market=None),
    )


def _ingest_docx(path: Path) -> IngestResult:
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.shared import RGBColor  # noqa: F401
    except ImportError as exc:
        raise IngestError(
            "ingest.dependency_missing",
            "DOCX ingestion needs python-docx.",
            fix="Install it with `pip install python-docx` or reinstall the project.",
        ) from exc

    document = Document(str(path))
    lines = []
    for paragraph in document.paragraphs:
        if not paragraph.text or not paragraph.text.strip():
            continue
        style_name = (paragraph.style.name if paragraph.style is not None else "") or ""
        text = paragraph.text.strip()
        if "list" in style_name.lower() or "bullet" in style_name.lower():
            text = "- " + text
        lines.append(text)
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    text = "\n".join(lines)
    fields, confidence, notes = extract_fields(text)

    section = document.sections[0] if document.sections else None
    width_mm = section.page_width.mm if section and section.page_width else None
    height_mm = section.page_height.mm if section and section.page_height else None
    margins = {}
    if section:
        margins = {
            "top": round(section.top_margin.mm, 1) if section.top_margin else 18,
            "right": round(section.right_margin.mm, 1) if section.right_margin else 18,
            "bottom": round(section.bottom_margin.mm, 1) if section.bottom_margin else 18,
            "left": round(section.left_margin.mm, 1) if section.left_margin else 18,
        }
    columns = 1
    if section is not None:
        cols = section._sectPr.find(qn("w:cols"))
        if cols is not None:
            columns = int(cols.get(qn("w:num")) or 1)

    fonts: list[str] = []
    sizes: list[float] = []
    colors: list[str] = []
    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            if run.font.name:
                fonts.append(run.font.name)
            if run.font.size:
                sizes.append(round(run.font.size.pt, 1))
            if run.font.color and run.font.color.rgb:
                colors.append(str(run.font.color.rgb))
    normal = document.styles["Normal"] if "Normal" in document.styles else None
    if normal is not None:
        if normal.font.name:
            fonts.insert(0, normal.font.name)
        if normal.font.size:
            sizes.insert(0, round(normal.font.size.pt, 1))
    body_size = _most_common_number(sizes)
    layout = LayoutDNA(
        format="docx",
        page_size=_page_size_name(width_mm, height_mm),
        page_width_mm=round(width_mm, 1) if width_mm else None,
        page_height_mm=round(height_mm, 1) if height_mm else None,
        margins_mm=margins or {"top": 18, "right": 18, "bottom": 18, "left": 18},
        columns=columns,
        font_families=_dedupe(fonts),
        font_sizes_pt=_dedupe(sizes),
        body_font_size_pt=body_size,
        colors=_dedupe(colors),
        images=len(document.inline_shapes),
        photo_likely=len(document.inline_shapes) > 0,
        tables=len(document.tables),
        editable_source=True,
        visual_identity=_visual_identity(_dedupe(fonts), _dedupe(colors), 0, 0),
        notes=["DOCX layout is approximated from styles and section properties."],
    )
    warnings = notes
    if layout.images:
        warnings.append("Images exist in the DOCX; confirm whether one is a photo.")
    return IngestResult(
        path=path,
        format="docx",
        text=text,
        fields=fields,
        layout=layout,
        confidence=confidence,
        warnings=warnings,
        needs_confirmation=_needs_confirmation(fields, confidence, market=None),
    )


def _ingest_pdf(path: Path) -> IngestResult:
    try:
        import pdfplumber
    except ImportError as exc:
        raise IngestError(
            "ingest.dependency_missing",
            "PDF ingestion needs pdfplumber.",
            fix="Install it with `pip install pdfplumber` or reinstall the project.",
        ) from exc

    pages_text: list[str] = []
    char_count = 0
    image_count = 0
    page_count = 0
    width_pt = height_pt = 0.0
    fonts: list[str] = []
    sizes: list[float] = []
    outside = 0
    table_count = 0
    word_xs: list[float] = []
    page_widths: list[float] = []

    with pdfplumber.open(str(path)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            pages_text.append(page_text)
            chars = page.chars or []
            char_count += len(chars)
            image_count += len(page.images or [])
            width_pt = max(width_pt, page.width or 0)
            height_pt = max(height_pt, page.height or 0)
            page_widths.append(page.width or 0)
            for char in chars:
                if char.get("fontname"):
                    fonts.append(char["fontname"])
                if char.get("size"):
                    sizes.append(round(float(char["size"]), 1))
                x0 = char.get("x0", 0)
                x1 = char.get("x1", 0)
                top = char.get("top", 0)
                bottom = char.get("bottom", 0)
                if x0 < -1 or x1 > (page.width or 0) + 1 or top < -1 or bottom > (page.height or 0) + 1:
                    outside += 1
            for word in page.extract_words() or []:
                word_xs.append(word.get("x0", 0))
            try:
                table_count += len(page.find_tables() or [])
            except Exception:
                pass

    text = "\n".join(pages_text)
    scanned = char_count < max(20, 20 * page_count) and image_count > 0
    if char_count < 50:
        scanned = True
    fields, confidence, notes = extract_fields(text)
    if scanned:
        notes.append("This PDF has little or no extractable text; it is probably scanned or image-only.")
        fields = {}
        confidence = {}

    width_mm = width_pt * 0.352778 if width_pt else None
    height_mm = height_pt * 0.352778 if height_pt else None
    margins = _pdf_margins(path) if not scanned else {}
    columns = _estimate_pdf_columns(word_xs, page_widths)
    body_size = _most_common_number(sizes)
    layout = LayoutDNA(
        format="pdf",
        page_size=_page_size_name(width_mm, height_mm),
        page_width_mm=round(width_mm, 1) if width_mm else None,
        page_height_mm=round(height_mm, 1) if height_mm else None,
        margins_mm=margins,
        columns=columns,
        font_families=_dedupe(fonts),
        font_sizes_pt=_dedupe(sizes),
        body_font_size_pt=body_size,
        images=image_count,
        photo_likely=image_count > 0,
        tables=table_count,
        text_outside_page=outside,
        editable_source=False,
        visual_identity=_visual_identity(_dedupe(fonts), [], 0, 0),
        notes=["PDF layout is approximated from text positions; fonts and columns may be imprecise."],
    )
    return IngestResult(
        path=path,
        format="pdf",
        text=text,
        fields=fields,
        layout=layout,
        confidence=confidence,
        warnings=notes,
        needs_confirmation=_needs_confirmation(fields, confidence, market=None) if not scanned else ["document"],
        scanned=scanned,
        page_count=page_count,
    )


def _ingest_legacy(path: Path) -> IngestResult:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise IngestError(
            "ingest.dependency_missing",
            f"{path.suffix} needs LibreOffice for conversion.",
            fix="Install LibreOffice, export to DOCX or PDF, or paste the content as text.",
        )
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", tmp, str(path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        converted = next(Path(tmp).glob("*.docx"), None)
        if converted is None:
            raise IngestError(
                "ingest.conversion_failed",
                f"LibreOffice could not convert {path.name}.",
                fix="Open the file, export it as DOCX or PDF, and retry.",
            )
        return _ingest_docx(converted)


# ---------------------------------------------------------------------------
# Field extraction
# ---------------------------------------------------------------------------


def _lines(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    result = []
    for raw in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw).strip()
        if line:
            result.append(line)
    return result


def _section_key(line: str) -> str | None:
    cleaned = line.strip().lstrip("#").strip().rstrip(":：").strip().lower()
    if not cleaned or len(cleaned) > 50:
        return None
    for key, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if cleaned == pattern or cleaned.startswith(pattern + " ") or cleaned.startswith(pattern + "&"):
                return key
    return None


def _split_sections(lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    prelude: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current: str | None = None
    buffer: list[str] = []
    seen_heading = False
    for line in lines:
        key = _section_key(line)
        if key:
            if current:
                sections.append((current, buffer))
            current = key
            buffer = []
            seen_heading = True
        elif current:
            buffer.append(line)
        else:
            prelude.append(line)
    if current:
        sections.append((current, buffer))
    if not seen_heading:
        prelude = lines
    return prelude, sections


def _looks_like_contact(line: str) -> bool:
    return bool(EMAIL_RE.search(line) or URL_RE.search(line) or PHONE_RE.search(line)) and len(line) < 160


def _looks_like_bullet(line: str) -> bool:
    return bool(BULLET_RE.match(line))


def _clean_bullet(line: str) -> str:
    return BULLET_RE.sub("", line).strip()


def _looks_like_school(line: str) -> bool:
    return bool(SCHOOL_RE.search(line)) and len(line) < 120


def _clean_school(line: str) -> str:
    cleaned = DATE_RANGE_RE.sub("", line)
    cleaned = DATE_RANGE_ZH_RE.sub("", cleaned)
    cleaned = GPA_RE.sub("", cleaned)
    parts = [part.strip(" ,，-—:：") for part in re.split(r"[,，|·;；]|\s{2,}", cleaned) if part.strip()]
    for part in parts:
        if SCHOOL_RE.search(part):
            return part
    return parts[0] if parts else cleaned.strip(" ,，-—:：")


def _looks_like_degree(line: str) -> bool:
    return bool(DEGREE_RE.search(line)) and len(line) < 120


def _looks_like_role(line: str) -> bool:
    return bool(ROLE_RE.search(line)) and len(line) < 120


def _looks_like_company(line: str) -> bool:
    return bool(COMPANY_RE.search(line)) and len(line) < 120


def _looks_like_header(line: str) -> bool:
    return len(line) < 80 and not line.rstrip().endswith(".") and (
        _looks_like_company(line) or _looks_like_role(line)
    )


def _parse_date_range(line: str) -> tuple[str, str] | None:
    match = DATE_RANGE_RE.search(line)
    if not match:
        match = DATE_RANGE_ZH_RE.search(line)
        if not match:
            return None
    start_year, start_month, end, end_month = match.groups()
    start = f"{start_year}-{int(start_month or 1):02d}"
    if str(end).lower() in {"present", "now", "至今", "现在", "目前"}:
        return start, "present"
    end_month = end_month or 1
    return start, f"{end}-{int(end_month):02d}"


def _extract_gpa(line: str) -> dict[str, Any] | None:
    match = GPA_RE.search(line)
    if not match:
        return None
    return {"value": float(match.group(1)), "scale": float(match.group(2))}


def _split_degree_major(line: str) -> tuple[str | None, str | None]:
    cleaned = DATE_RANGE_RE.sub("", line)
    cleaned = DATE_RANGE_ZH_RE.sub("", cleaned)
    cleaned = GPA_RE.sub("", cleaned)
    match = DEGREE_RE.search(cleaned)
    if not match:
        return None, None
    degree = match.group(0).strip(" .")
    rest = cleaned[match.end():].strip(" .,，|·-—:：")
    rest = re.sub(r"^(in|of)\s+", "", rest, flags=re.IGNORECASE).strip(" .,，|·-—:：")
    major = rest if rest and len(rest) < 80 else None
    if major:
        major = re.split(r"[|·,，]", major)[0].strip(" .,，|·-—:：")
    return degree, major


def _split_company_title(line: str) -> tuple[str | None, str | None]:
    cleaned = DATE_RANGE_RE.sub("", line)
    cleaned = DATE_RANGE_ZH_RE.sub("", cleaned).strip(" |,，·—–-")
    parts = [p.strip() for p in re.split(r"\s*[|—–·]\s*|\s{2,}", cleaned) if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if _looks_like_company(cleaned):
        return cleaned, None
    if _looks_like_role(cleaned):
        return None, cleaned
    if len(parts) == 1:
        return parts[0], None
    return None, None


def _extract_education(section_lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for index, line in enumerate(section_lines):
        is_school = _looks_like_school(line)
        is_degree = _looks_like_degree(line)
        if not (is_school or is_degree):
            continue
        if is_degree and not is_school and entries:
            last = entries[-1]
            degree, major = _split_degree_major(line)
            if degree and last.get("degree") == degree and (not major or last.get("major") == major):
                continue
            if not last.get("degree"):
                entry = last
            else:
                entry = {}
                entries.append(entry)
        elif is_school and entries and not entries[-1].get("school"):
            entry = entries[-1]
        elif is_school and entries and entries[-1].get("school") == _clean_school(line):
            entry = entries[-1]
        else:
            entry = {}
            entries.append(entry)
        window = [line] + section_lines[index + 1 : index + 3]
        if is_school:
            entry["school"] = _clean_school(line) or line.strip()
        for candidate in window:
            dates = _parse_date_range(candidate)
            if dates and "start" not in entry:
                entry["start"], entry["end"] = dates
            gpa = _extract_gpa(candidate)
            if gpa:
                entry["gpa"] = gpa
            if _looks_like_degree(candidate):
                degree, major = _split_degree_major(candidate)
                if degree and "degree" not in entry:
                    entry["degree"] = degree
                if major and "major" not in entry:
                    entry["major"] = major
            if _looks_like_school(candidate) and "school" not in entry:
                entry["school"] = _clean_school(candidate) or candidate.strip()
    unique: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for entry in entries:
        key = (entry.get("school"), entry.get("degree"), entry.get("start"))
        if entry and key not in seen:
            seen.add(key)
            unique.append(entry)
    return unique[:3]


def _extract_experience(section_lines: list[str], *, section_name: str = "experience") -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in section_lines:
        if _looks_like_bullet(line):
            if current is not None:
                current.setdefault("bullets", []).append(_clean_bullet(line))
            continue
        dates = _parse_date_range(line)
        if dates:
            if current is None or current.get("start"):
                company, title = _split_company_title(line)
                current = {"bullets": []}
                if company:
                    current["company"] = company
                if title:
                    current["title"] = title
                current["start"], current["end"] = dates
                entries.append(current)
            else:
                current["start"], current["end"] = dates
            continue
        if current is None:
            if _looks_like_header(line):
                company, title = _split_company_title(line)
                current = {"bullets": []}
                if company:
                    current["company"] = company
                if title:
                    current["title"] = title
                entries.append(current)
            continue
        if _looks_like_header(line) and (current.get("bullets") or (current.get("company") and current.get("title"))):
            company, title = _split_company_title(line)
            current = {"bullets": []}
            if company:
                current["company"] = company
            if title:
                current["title"] = title
            entries.append(current)
        elif not current.get("company") and _looks_like_company(line):
            current["company"] = line.strip()
        elif not current.get("title") and _looks_like_role(line):
            current["title"] = line.strip()
        elif len(line) > 12:
            current.setdefault("bullets", []).append(_clean_bullet(line))
    for entry in entries:
        title = str(entry.get("title") or "").lower()
        company = str(entry.get("company") or "").lower()
        bullets = " ".join(str(b).lower() for b in entry.get("bullets", []))
        if (
            "intern" in section_name.lower()
            or "intern" in title
            or "intern" in company
            or "实习" in title
            or "实习" in company
            or "实习" in bullets
        ):
            entry["type"] = "internship"
        else:
            entry.setdefault("type", "full_time")
        entry["bullets"] = [b for b in entry.get("bullets", []) if len(b) > 2][:8]
    return [e for e in entries if e.get("company") or e.get("title")][:8]


def _extract_projects(section_lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in section_lines:
        if _looks_like_bullet(line):
            if current is not None:
                current.setdefault("bullets", []).append(_clean_bullet(line))
            continue
        dates = _parse_date_range(line)
        if dates:
            if current is None or current.get("start"):
                name = DATE_RANGE_RE.sub("", line)
                name = DATE_RANGE_ZH_RE.sub("", name).strip(" |,，·—–-")
                current = {"name": name or "Project", "start": dates[0], "end": dates[1], "bullets": []}
                entries.append(current)
            else:
                current["start"], current["end"] = dates
            continue
        if current is None:
            current = {"name": line.strip(" |,，·—–-") or "Project", "bullets": []}
            entries.append(current)
            continue
        tech = re.search(r"(?:tech|技术栈|技术)\s*[:：]\s*(.+)", line, re.IGNORECASE)
        if tech:
            current["tech"] = [t.strip() for t in re.split(r"[,，、;；/]", tech.group(1)) if t.strip()]
        elif line.rstrip().endswith(".") or len(line) > 60 or current.get("bullets"):
            current.setdefault("bullets", []).append(_clean_bullet(line))
        else:
            current = {"name": line.strip(" |,，·—–-") or "Project", "bullets": []}
            entries.append(current)
    for entry in entries:
        entry["bullets"] = [b for b in entry.get("bullets", []) if len(b) > 2][:6]
    return entries[:6]


def _extract_skills(section_lines: list[str]) -> list[str]:
    skills: list[str] = []
    for line in section_lines:
        if _section_key(line):
            continue
        content = line.split(":", 1)[-1] if ":" in line else line.split("：", 1)[-1]
        for part in re.split(r"[,，、|;；/]|\s{3,}", content):
            value = part.strip(" .。-—")
            if 1 < len(value) < 50 and not _looks_like_bullet(value):
                skills.append(value)
    return _dedupe(skills)[:30]


def extract_fields(text: str) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    lines = _lines(text)
    prelude, sections = _split_sections(lines)
    section_map: dict[str, list[str]] = {}
    for key, content in sections:
        section_map.setdefault(key, []).extend(content)

    warnings: list[str] = []
    if not sections:
        warnings.append("No standard section headings were detected; extraction is heuristic.")
    if len(text.strip()) < 200:
        warnings.append("Very little text was extracted; the file may be incomplete or image-based.")
    if re.search(r"(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}", text) and not re.search(r"(?:19|20)\d{2}[./-]\d{1,2}", text):
        warnings.append("Some dates contain a year but no month; confirm the normalized month.")

    name = None
    for line in prelude:
        if _looks_like_contact(line) or _looks_like_role(line) or _section_key(line):
            continue
        if re.fullmatch(r"(resume|curriculum vitae|cv|简历)", line.strip(), re.IGNORECASE):
            continue
        if 2 <= len(line) <= 40 and not re.search(r"\d{3,}", line):
            name = line
            break

    email = EMAIL_RE.search(text)
    phone = None
    for match in PHONE_RE.finditer(text):
        candidate = match.group(0)
        compact = re.sub(r"[^\d+]", "", candidate)
        if len(compact) >= 8:
            phone = candidate.strip()
            break
    links = []
    for url in _dedupe(URL_RE.findall(text)):
        kind = "github" if "github.com" in url else "linkedin" if "linkedin.com" in url else "portfolio"
        links.append({"label": kind.capitalize(), "url": url, "kind": kind})

    summary = " ".join(section_map.get("summary", [])).strip() or None
    target_role = None
    if section_map.get("job_intent"):
        target_role = section_map["job_intent"][0].strip(":： ")
    elif prelude:
        for line in prelude:
            if re.search(r"(求职意向|目标岗位|objective)", line, re.IGNORECASE):
                target_role = re.split(r"[:：]", line, maxsplit=1)[-1].strip()
                break

    education = _extract_education(section_map.get("education", []))
    experience = _extract_experience(section_map.get("experience", []))
    projects = _extract_projects(section_map.get("projects", []))
    skills = _extract_skills(section_map.get("skills", []))
    awards = [_clean_bullet(line) for line in section_map.get("awards", []) if len(line) > 2][:10]
    certificates = [_clean_bullet(line) for line in section_map.get("certificates", []) if len(line) > 2][:10]
    languages = [_clean_bullet(line) for line in section_map.get("languages", []) if len(line) > 2][:10]

    fields = {
        "name": name,
        "email": email.group(0) if email else None,
        "phone": phone,
        "links": links,
        "summary": summary,
        "target_role": target_role,
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skills,
        "awards": awards,
        "certificates": certificates,
        "languages": languages,
    }

    confidence = {
        "identity": "high" if name and (email or phone) else "medium" if name else "low",
        "summary": "high" if summary else "low",
        "education": "high" if education and all(e.get("school") and e.get("start") for e in education) else "medium" if education else "low",
        "experience": "high" if experience and all(e.get("company") and e.get("title") and e.get("start") for e in experience) else "medium" if experience else "low",
        "projects": "high" if projects and all(p.get("name") and p.get("bullets") for p in projects) else "medium" if projects else "low",
        "skills": "high" if len(skills) >= 5 else "medium" if skills else "low",
    }
    if not education:
        warnings.append("No education section was found; education must not be omitted.")
    if not experience and not projects:
        warnings.append("No experience or project section was found.")
    return fields, confidence, warnings


def _needs_confirmation(fields: dict[str, Any], confidence: dict[str, str], market: str | None) -> list[str]:
    needed: list[str] = []
    if not fields.get("name"):
        needed.append("identity.full_name")
    if not fields.get("email") and not fields.get("phone"):
        needed.append("identity.email")
    if not fields.get("education"):
        needed.append("education")
    else:
        for index, entry in enumerate(fields["education"]):
            for key in ("school", "degree", "major", "start", "end"):
                if not entry.get(key):
                    needed.append(f"education[{index}].{key}")
    for index, entry in enumerate(fields.get("experience") or []):
        for key in ("company", "title", "start"):
            if not entry.get(key):
                needed.append(f"experience[{index}].{key}")
        if not entry.get("bullets"):
            needed.append(f"experience[{index}].bullets")
    for index, entry in enumerate(fields.get("projects") or []):
        if not entry.get("bullets"):
            needed.append(f"projects[{index}].bullets")
        needed.append(f"projects[{index}].context")
    if len(fields.get("skills") or []) < 3:
        needed.append("skills")
    if market == "cn_internet":
        fundamentals = {"operating systems", "networks", "data structures", "algorithms", "databases", "操作系统", "计算机网络", "数据结构", "算法", "数据库"}
        if not any(skill.lower() in fundamentals for skill in fields.get("skills") or []):
            needed.append("skills.cs_fundamentals")
    return _dedupe(needed)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _dedupe(values: list[Any]) -> list[Any]:
    seen = set()
    result = []
    for value in values:
        key = str(value).strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _most_common_number(values: list[float]) -> float | None:
    if not values:
        return None
    counts: dict[float, int] = {}
    for value in values:
        key = round(float(value), 1)
        counts[key] = counts.get(key, 0) + 1
    return max(counts, key=counts.get)


def _page_size_name(width_mm: float | None, height_mm: float | None) -> str | None:
    if not width_mm or not height_mm:
        return None
    width, height = sorted((width_mm, height_mm))
    if abs(width - 210) <= 5 and abs(height - 297) <= 5:
        return "a4"
    if abs(width - 215.9) <= 5 and abs(height - 279.4) <= 5:
        return "letter"
    return "custom"


def _parse_css_length(value: str, *, default: float = 0.0) -> float | None:
    match = re.match(r"^\s*(-?[0-9.]+)\s*(mm|cm|in|pt|px|rem|em)?\s*$", value.strip())
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    factors = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 0.352778, "px": 0.264583, "rem": 4.23333, "em": 4.23333}
    return number * factors.get(unit, 1.0)


def _css_font_sizes(css: str) -> list[float]:
    sizes = []
    for match in re.finditer(r"font-size\s*:\s*([0-9.]+)\s*(pt|px|rem|em)", css, re.IGNORECASE):
        value = float(match.group(1))
        unit = match.group(2).lower()
        sizes.append(round(value if unit == "pt" else value * 0.75 if unit == "px" else value * 12, 1))
    return sizes


def _css_fonts(css: str) -> list[str]:
    fonts = []
    for match in re.finditer(r"font-family\s*:\s*([^;}]+)", css, re.IGNORECASE):
        for part in match.group(1).split(","):
            cleaned = part.strip().strip("'\"")
            if cleaned:
                fonts.append(cleaned)
    return _dedupe(fonts)


def _css_colors(css: str) -> list[str]:
    colors = []
    for match in re.finditer(r"(?<!background-)(?:color|background-color)\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)|[a-zA-Z]+)", css):
        value = match.group(1).lower()
        if value not in {"black", "#000", "#000000", "white", "#fff", "#ffffff", "transparent", "inherit", "initial"}:
            colors.append(value)
    return _dedupe(colors)


def _layout_from_html(soup, css: str, path: Path) -> LayoutDNA:
    text = soup.get_text(" ")
    fonts = _css_fonts(css)
    sizes = _css_font_sizes(css)
    colors = _css_colors(css)
    columns = 1
    for match in re.finditer(r"column-count\s*:\s*([2-9])", css, re.IGNORECASE):
        columns = max(columns, int(match.group(1)))
    for match in re.finditer(r"grid-template-columns\s*:\s*([^;}]+)", css, re.IGNORECASE):
        tracks = [t for t in match.group(1).split() if t.strip()]
        if len(tracks) >= 2:
            columns = max(columns, len(tracks))
    if soup.find("aside") or soup.find(attrs={"class": re.compile(r"sidebar|side-bar", re.I)}):
        columns = max(columns, 2)

    margins = {"top": 18.0, "right": 18.0, "bottom": 18.0, "left": 18.0}
    page_size = None
    page_match = re.search(r"@page\s*\{([^}]*)\}", css, re.IGNORECASE | re.DOTALL)
    if page_match:
        page_body = page_match.group(1)
        size_match = re.search(r"size\s*:\s*([^;}]+)", page_body, re.IGNORECASE)
        if size_match:
            raw_size = size_match.group(1).lower()
            if "a4" in raw_size:
                page_size = "a4"
            elif "letter" in raw_size:
                page_size = "letter"
            else:
                dims = re.findall(r"([0-9.]+)\s*(mm|cm|in|pt)", raw_size)
                if len(dims) >= 2:
                    width = _parse_css_length(f"{dims[0][0]}{dims[0][1]}")
                    height = _parse_css_length(f"{dims[1][0]}{dims[1][1]}")
                    page_size = _page_size_name(width, height)
        margin_match = re.search(r"margin\s*:\s*([^;}]+)", page_body, re.IGNORECASE)
        if margin_match:
            parts = margin_match.group(1).split()
            parsed = [_parse_css_length(part) for part in parts]
            parsed = [p for p in parsed if p is not None]
            if len(parsed) == 1:
                margins = {k: parsed[0] for k in margins}
            elif len(parsed) == 2:
                margins = {"top": parsed[0], "bottom": parsed[0], "left": parsed[1], "right": parsed[1]}
            elif len(parsed) >= 4:
                margins = {"top": parsed[0], "right": parsed[1], "bottom": parsed[2], "left": parsed[3]}
    if page_size is None:
        body_match = re.search(r"body\s*\{([^}]*)\}", css, re.IGNORECASE | re.DOTALL)
        if body_match:
            margin_match = re.search(r"margin\s*:\s*([^;}]+)", body_match.group(1), re.IGNORECASE)
            if margin_match:
                parsed = [_parse_css_length(part) for part in margin_match.group(1).split()]
                parsed = [p for p in parsed if p is not None]
                if len(parsed) >= 1:
                    margins = {k: parsed[0] for k in margins}

    absolute = len(re.findall(r"position\s*:\s*(?:absolute|fixed)", css, re.IGNORECASE))
    overflow = len(re.findall(r"overflow\s*:\s*hidden", css, re.IGNORECASE))
    images = len(soup.find_all("img"))
    photo = False
    for image in soup.find_all("img"):
        marker = " ".join(
            str(image.get(attr) or "") for attr in ("class", "id", "alt", "src")
        ).lower()
        if any(word in marker for word in ("photo", "avatar", "portrait", "headshot", "证件照")):
            photo = True
            break
    tables = len(soup.find_all("table"))
    body_size = _most_common_number(sizes)
    line_height = None
    match = re.search(r"line-height\s*:\s*([0-9.]+)", css, re.IGNORECASE)
    if match:
        line_height = float(match.group(1))
    identity = _visual_identity(fonts, colors, absolute, len(re.findall(r"border-(?:bottom|top)\s*:", css, re.IGNORECASE)))
    return LayoutDNA(
        format="html",
        page_size=page_size,
        page_width_mm=210 if page_size == "a4" else 215.9 if page_size == "letter" else None,
        page_height_mm=297 if page_size == "a4" else 279.4 if page_size == "letter" else None,
        margins_mm={k: round(v, 1) for k, v in margins.items()},
        columns=columns,
        font_families=fonts,
        font_sizes_pt=sizes,
        body_font_size_pt=body_size,
        line_height=line_height,
        colors=colors,
        images=images,
        photo_likely=photo,
        tables=tables,
        absolute_positioned=absolute,
        overflow_hidden=overflow,
        editable_source=True,
        visual_identity=identity,
        notes=[f"CSS parsed from {len(css)} characters; layout is approximated."],
    )


def _visual_identity(fonts: list[str], colors: list[str], absolute: int, rules: int) -> int:
    score = 0
    if fonts and any(f.lower() not in DEFAULT_FONTS for f in fonts):
        score += 1
    if colors:
        score += 1
    if rules:
        score += 1
    if absolute == 0:
        score += 1
    return min(score, 4)


def _pdf_margins(path: Path) -> dict[str, float]:
    try:
        import pdfplumber
    except ImportError:
        return {}
    with pdfplumber.open(str(path)) as pdf:
        xs0, xs1, tops, bottoms = [], [], [], []
        width = height = 0.0
        for page in pdf.pages:
            width = max(width, page.width or 0)
            height = max(height, page.height or 0)
            for char in page.chars or []:
                xs0.append(char.get("x0", 0))
                xs1.append(char.get("x1", 0))
                tops.append(char.get("top", 0))
                bottoms.append(char.get("bottom", 0))
    if not xs0:
        return {}
    pt = 0.352778
    return {
        "left": round(min(xs0) * pt, 1),
        "right": round(max(0.0, width - max(xs1)) * pt, 1),
        "top": round(min(tops) * pt, 1),
        "bottom": round(max(0.0, height - max(bottoms)) * pt, 1),
    }


def _estimate_pdf_columns(word_xs: list[float], page_widths: list[float]) -> int:
    if not word_xs or not page_widths:
        return 1
    width = max(page_widths)
    if width <= 0:
        return 1
    bins: dict[int, int] = {}
    for x in word_xs:
        bins[int(x // 10)] = bins.get(int(x // 10), 0) + 1
    dense = [bin_index for bin_index, count in bins.items() if count >= max(3, len(word_xs) // 50)]
    if len(dense) < 2:
        return 1
    dense.sort()
    biggest_gap = 0
    for left, right in zip(dense, dense[1:]):
        biggest_gap = max(biggest_gap, right - left)
    return 2 if biggest_gap * 10 > width * 0.25 else 1


# ---------------------------------------------------------------------------
# Vault conversion
# ---------------------------------------------------------------------------


def detect_lang(text: str) -> str:
    return "zh" if len(CJK_RE.findall(text)) >= max(5, len(text) // 50) else "en"


def to_vault(result: IngestResult, *, lang: str | None = None) -> tuple[dict[str, Any], list[str]]:
    """Convert extracted fields into a collecting vault fragment with evidence."""
    lang = lang or detect_lang(result.text)
    fields = result.fields or {}
    evidence: dict[str, Any] = {}
    needs: list[str] = list(result.needs_confirmation)
    locator = str(result.path)

    def add_evidence(claim: str) -> str:
        ev_id = next_id({"evidence": evidence}, "ev")
        evidence[ev_id] = {
            "id": ev_id,
            "claim": claim,
            "status": "user_asserted",
            "source": "document",
            "locator": locator,
            "captured_at": date.today().isoformat(),
            "notes": f"Extracted from {result.path.name}; confirm before submission.",
        }
        return ev_id

    identity: dict[str, Any] = {}
    if fields.get("name"):
        identity["full_name"] = fields["name"]
    if fields.get("email"):
        identity["email"] = fields["email"]
    if fields.get("phone"):
        identity["phone"] = fields["phone"]
    if fields.get("links"):
        identity["links"] = fields["links"]
    identity["locale"] = lang
    if fields.get("summary"):
        identity["summary"] = {lang: fields["summary"]}
        identity["summary_evidence"] = [add_evidence(fields["summary"])]

    education = []
    for index, entry in enumerate(fields.get("education") or []):
        item: dict[str, Any] = {"id": f"edu_{index + 1:03d}", "school": entry.get("school") or ""}
        if entry.get("degree"):
            item["degree"] = {lang: entry["degree"]}
        if entry.get("major"):
            item["major"] = {lang: entry["major"]}
        if entry.get("start"):
            item["start"] = entry["start"]
        if entry.get("end"):
            item["end"] = entry["end"]
        if entry.get("gpa"):
            item["gpa"] = entry["gpa"]
        education.append(item)

    experience = []
    for index, entry in enumerate(fields.get("experience") or []):
        exp_id = f"exp_{index + 1:03d}"
        item = {
            "id": exp_id,
            "company": entry.get("company") or "",
            "title": {lang: entry.get("title") or ""},
            "employment_type": entry.get("type") or "full_time",
        }
        if entry.get("start"):
            item["start"] = entry["start"]
        if entry.get("end"):
            item["end"] = entry["end"]
        bullets = []
        for b_index, text in enumerate(entry.get("bullets") or []):
            bullets.append(
                {
                    "id": f"bul_{exp_id}_{b_index + 1}",
                    "text": {lang: text},
                    "evidence": [add_evidence(text)],
                }
            )
        item["bullets"] = bullets
        experience.append(item)

    projects = []
    for index, entry in enumerate(fields.get("projects") or []):
        proj_id = f"proj_{index + 1:03d}"
        item = {
            "id": proj_id,
            "name": entry.get("name") or f"Project {index + 1}",
            "context": "personal",
        }
        if entry.get("start"):
            item["start"] = entry["start"]
        if entry.get("end"):
            item["end"] = entry["end"]
        if entry.get("tech"):
            item["tech"] = entry["tech"]
        bullets = []
        for b_index, text in enumerate(entry.get("bullets") or []):
            bullets.append(
                {
                    "id": f"bul_{proj_id}_{b_index + 1}",
                    "text": {lang: text},
                    "evidence": [add_evidence(text)],
                }
            )
        item["bullets"] = bullets
        if bullets:
            item["own_contribution"] = {lang: bullets[0]["text"][lang]}
            item["outcome"] = {lang: bullets[-1]["text"][lang]}
            if len(bullets) >= 2:
                item["optimizations"] = {lang: [bullets[1]["text"][lang]]}
            else:
                item["approach"] = {lang: bullets[0]["text"][lang]}
            project_text = " ".join(str(b["text"].get(lang, "")) for b in bullets).lower()
            inferred_tech = [
                skill for skill in (fields.get("skills") or []) if str(skill).lower() in project_text
            ]
            if inferred_tech:
                item["tech"] = inferred_tech[:8]
        projects.append(item)
        needs.append(f"projects[{index}].context")

    skills: list[dict[str, Any]] = []
    fundamentals = {
        "operating systems", "networks", "data structures", "algorithms", "databases",
        "操作系统", "计算机网络", "数据结构", "算法", "数据库",
    }
    fundamentals_items = [s for s in fields.get("skills") or [] if s.lower() in fundamentals]
    other_items = [s for s in fields.get("skills") or [] if s.lower() not in fundamentals]
    if fundamentals_items:
        skills.append({"id": "skl_001", "name": {"en": "CS Fundamentals", "zh": "计算机基础"}, "kind": "fundamentals", "items": [{"name": s, "level": "unknown"} for s in fundamentals_items]})
    if other_items:
        skills.append({"id": f"skl_{len(skills) + 1:03d}", "name": {"en": "Skills", "zh": "技能"}, "kind": "other", "items": [{"name": s, "level": "unknown"} for s in other_items]})

    awards = [
        {"id": f"awd_{index + 1:03d}", "title": {lang: title}}
        for index, title in enumerate(fields.get("awards") or [])
    ]
    certificates = [
        {"id": f"cert_{index + 1:03d}", "name": {lang: name}}
        for index, name in enumerate(fields.get("certificates") or [])
    ]
    languages = [
        {"id": f"lang_{index + 1:03d}", "name": {lang: name}, "proficiency": "professional"}
        for index, name in enumerate(fields.get("languages") or [])
    ]

    fragment: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "collecting",
        "identity": identity,
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skills,
        "awards": awards,
        "certificates": certificates,
        "languages": languages,
        "publications": [],
        "evidence": evidence,
        "needs_confirmation": [
            {
                "path": path,
                "reason": "Extracted from a document; confirm the value before submission.",
                "severity": "blocker" if path in {"identity.full_name", "education", "skills"} else "warning",
                "question": f"Please confirm {path}.",
                "resolved": False,
            }
            for path in _dedupe(needs)
        ],
    }
    if fields.get("target_role"):
        fragment["preferences"] = {"target_roles": [fields["target_role"]]}
    return fragment, _dedupe(needs)
