# SPDX-License-Identifier: MIT
"""Fixture builders for ingestion and template-audit tests."""

from __future__ import annotations

from pathlib import Path

STRONG_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 18mm; }
body { font-family: Calibri, Arial, sans-serif; font-size: 10.5pt; line-height: 1.35; color: #222; }
h1 { font-size: 20pt; text-align: center; margin: 0 0 4pt; }
.contact { text-align: center; font-size: 10pt; margin-bottom: 10pt; }
h2 { font-size: 11.5pt; border-bottom: 1px solid #1f4e79; color: #1f4e79; margin: 10pt 0 4pt; }
ul { margin: 2pt 0 6pt 16pt; }
</style></head><body>
<h1>Li Ming</h1>
<div class="contact">liming@example.com | +86 138 0000 0000 | Hangzhou | https://github.com/example-liming</div>
<h2>Summary</h2><p>Computer science student with a backend internship and a RAG project.</p>
<h2>Education</h2><p>Example University, B.Eng. in Computer Science, 2023-09 - 2027-06</p><p>GPA: 3.7/4.0</p>
<h2>Experience</h2><p><strong>Acme Cloud</strong> | Backend Intern | 2026-06 - 2026-09</p>
<ul><li>Cut order-query P95 latency from 480ms to 190ms across 300K daily requests.</li>
<li>Shipped bulk export, removing 6 hours of manual work per week.</li></ul>
<h2>Projects</h2><p><strong>Course QA with RAG</strong> | 2025-09 - 2026-03</p>
<ul><li>Built heading-aware chunking and hybrid BM25 retrieval.</li>
<li>Raised Recall@5 from 62% to 81% on 120 labeled questions.</li></ul>
<h2>Skills</h2><p>Java, Python, SQL, Spring Boot, MySQL, Redis, Operating Systems, Computer Networks, Data Structures, Algorithms, Databases</p>
</body></html>
"""

BAD_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
@page { size: letter; margin: 5mm; }
body { font-family: Arial; font-size: 7pt; }
.photo { width: 80px; }
</style></head><body>
<img class="photo" src="photo.jpg" alt="photo">
<h1>Jane Doe</h1>
<p>jane@example.com | +1 555 0100 | Date of Birth: 2000-01</p>
<h2>Experience</h2>
<p>Acme Corp | Engineer | 2022-01 - 2024-01</p>
<p>Built a service that improved latency from 500ms to 200ms for 10000 users.</p>
<p>This template intentionally has no education section, tiny body text, a photo, personal fields, and unsafe margins.</p>
<h2>Skills</h2>
<p>Python, Java, SQL</p>
</body></html>
"""

TWO_COLUMN_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 18mm; }
body { font-family: Calibri, sans-serif; font-size: 10.5pt; }
.wrap { display: grid; grid-template-columns: 2fr 1fr; gap: 12mm; }
h2 { border-bottom: 1px solid #1f4e79; color: #1f4e79; }
</style></head><body>
<h1>Li Ming</h1>
<p>liming@example.com | +86 138 0000 0000</p>
<div class="wrap">
<main>
<h2>Experience</h2><p>Acme Cloud | Backend Intern | 2026-06 - 2026-09</p>
<ul><li>Cut order-query P95 latency from 480ms to 190ms across 300K daily requests.</li></ul>
<h2>Projects</h2><p>Course QA with RAG | 2025-09 - 2026-03</p>
<ul><li>Raised Recall@5 from 62% to 81% on 120 labeled questions.</li></ul>
</main>
<aside>
<h2>Education</h2><p>Example University, B.Eng. in Computer Science, 2023-09 - 2027-06</p>
<h2>Skills</h2><p>Java, Python, SQL, MySQL, Redis</p>
</aside>
</div>
</body></html>
"""


def write_html(path: Path, content: str = STRONG_HTML) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def write_docx(path: Path) -> Path:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    doc = Document()
    section = doc.sections[0]
    section.top_margin = section.bottom_margin = section.left_margin = section.right_margin = Inches(0.75)
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10.5)

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("Li Ming")
    run.bold = True
    run.font.size = Pt(18)

    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.add_run("liming@example.com | +86 138 0000 0000 | Hangzhou | https://github.com/example-liming")

    doc.add_heading("Summary", level=2)
    doc.add_paragraph("Computer science student with a backend internship and a RAG project.")

    doc.add_heading("Education", level=2)
    doc.add_paragraph("Example University, B.Eng. in Computer Science, 2023-09 - 2027-06")
    doc.add_paragraph("GPA: 3.7/4.0")

    doc.add_heading("Experience", level=2)
    doc.add_paragraph("Acme Cloud | Backend Intern | 2026-06 - 2026-09")
    for bullet in (
        "Cut order-query P95 latency from 480ms to 190ms across 300K daily requests.",
        "Shipped bulk export, removing 6 hours of manual work per week.",
    ):
        doc.add_paragraph(bullet, style="List Bullet")

    doc.add_heading("Projects", level=2)
    doc.add_paragraph("Course QA with RAG | 2025-09 - 2026-03")
    for bullet in (
        "Built heading-aware chunking and hybrid BM25 retrieval.",
        "Raised Recall@5 from 62% to 81% on 120 labeled questions.",
    ):
        doc.add_paragraph(bullet, style="List Bullet")

    doc.add_heading("Skills", level=2)
    doc.add_paragraph("Java, Python, SQL, Spring Boot, MySQL, Redis, Operating Systems, Computer Networks, Data Structures, Algorithms, Databases")
    doc.save(str(path))
    return path


def write_pdf(path: Path) -> Path:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 60
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawCentredString(width / 2, y, "Li Ming")
    y -= 22
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(width / 2, y, "liming@example.com | +86 138 0000 0000 | Hangzhou")
    y -= 24
    sections = [
        ("Summary", ["Computer science student with a backend internship and a RAG project."]),
        ("Education", ["Example University, B.Eng. in Computer Science, 2023-09 - 2027-06", "GPA: 3.7/4.0"]),
        (
            "Experience",
            [
                "Acme Cloud | Backend Intern | 2026-06 - 2026-09",
                "Cut order-query P95 latency from 480ms to 190ms across 300K daily requests.",
                "Shipped bulk export, removing 6 hours of manual work per week.",
            ],
        ),
        (
            "Projects",
            [
                "Course QA with RAG | 2025-09 - 2026-03",
                "Built heading-aware chunking and hybrid BM25 retrieval.",
                "Raised Recall@5 from 62% to 81% on 120 labeled questions.",
            ],
        ),
        ("Skills", ["Java, Python, SQL, Spring Boot, MySQL, Redis"]),
    ]
    for heading, lines in sections:
        pdf.setFont("Helvetica-Bold", 11.5)
        pdf.drawString(60, y, heading)
        y -= 15
        pdf.setFont("Helvetica", 10.5)
        for line in lines:
            pdf.drawString(60, y, line)
            y -= 13
        y -= 6
    pdf.save()
    return path


def write_scanned_pdf(path: Path) -> Path:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    pdf.setFillColorRGB(0.85, 0.85, 0.85)
    pdf.rect(40, 40, width - 80, height - 80, fill=1, stroke=0)
    pdf.setFillColorRGB(0.2, 0.2, 0.2)
    pdf.rect(80, height - 160, 200, 24, fill=1, stroke=0)
    pdf.save()
    return path
