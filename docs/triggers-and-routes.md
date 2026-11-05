# Triggers & Routes

> The skill must decide what the user actually wants before doing anything. Creating from scratch and optimizing an existing resume are different pipelines. "Keep my template" is allowed only after a template-quality audit.

## 1. Trigger matrix

| User intent | Route | First action | Output |
|---|---|---|---|
| "Make me a resume" / no file | `create` | Guided intake from zero | New resume |
| "Optimize / improve / fix my resume" + file | `optimize` | Ingest → extract → audit → template decision | Improved resume + change report |
| "Tailor my resume to this JD" | `tailor` | Load vault or ingest → JD match → optimize | Targeted resume + fit report |
| "Review my resume" / "what's wrong with it" | `review` | Ingest → diagnostic audit | Report only; no rewrite unless asked |
| "Change the template / make it prettier" | `restyle` | Load vault → template selection → render | Restyled resume |
| "Translate to English/Chinese" / "make a bilingual version" | `localize` | Load vault → transcreation → parity check | Target-market resume + parity report |
| "Add my new internship/job" | `update` | Ingest → merge into vault → preserve template | Updated resume + diff |
| "What jobs should I apply for?" | `recommend` | Build capability profile → role families | Fit tiers + gaps + build plan |
| "I have a template I like, use it" | `template-import` | Audit → learn or reject | Private template + resume |
| "I have no experience / no projects" | `create` + build mode | Intake → honesty gate → proof plan | Starter resume + 2–4 week plan |
| "Write a cover letter / prep interviews / compare offers" | out of scope | Explain scope | Route elsewhere |

## 2. Routing rules

1. **A file means `optimize`, not `create`.** If the user uploads an existing resume, do not start a from-scratch interview. Ingest first.
2. **"Review" means no rewrite by default.** Diagnose and report; ask before changing content.
3. **"Tailor" implies a target.** If no JD is supplied, ask for one or use the target role.
4. **"Translate" means `localize`, never literal translation.** Re-derive from facts for the target market.
5. **"Make it prettier" means `restyle`.** Do not rewrite content unless asked.
6. **Ambiguous intent gets one interactive question.** Example: "你是想保持内容只换版式，还是连内容一起优化？"
7. **Out-of-scope requests are declined clearly** and, if useful, mapped to the right tool.
8. **All routes require continuous interactive questioning when input is missing.** Follow the [mandatory host-tool protocol](../SKILL.md#mandatory-continuous-interaction): use `AskUserQuestion` or an available equivalent, wait for the answer, and continue the same conversation and task. This includes extraction confirmation, evidence follow-ups, template selection, framework consent, localization gaps, and minimum-gate acceptance. Do not end a task with a questionnaire or require "continue" after each answer. Preserve free-text input and pause/resume; if the tool is unavailable or denied, report the limitation without silently switching to final-message questions.

## 3. Route A — Create from scratch

1. Guided intake (`docs/intake-and-sufficiency.md`): target → identity → education → experience → projects → skills → proof → preferences.
2. Sufficiency gate: `blocked` / `minimum` / `strong`.
3. Writing-framework consent.
4. Market + persona routing.
5. Template selection.
6. Render + QA.

No file ingestion. No template audit. No "keep original" option.

## 4. Route B — Optimize an existing resume

### 4.1 Supported inputs

| Format | Extraction | Fidelity |
|---|---|---|
| `.docx` | python-docx: text, styles, tables, headers/footers | Medium-high |
| `.pdf` | pdfplumber/pypdf: text, fonts, positions; detect scanned/image-only | Medium |
| `.html` / `.htm` | BeautifulSoup + CSS parsing | High |
| `.md` / `.txt` | Plain text | Low (content only) |
| `.doc` / `.rtf` | Convert with LibreOffice first | Medium |
| Image (`.png`, `.jpg`) | OCR only; not v1 | Low |
| JSON Resume | Schema import | High |
| LinkedIn | Export PDF or paste; no login scraping | Medium |

If the file is scanned or image-only, say so and ask for a text-based version. Do not pretend to preserve a layout you cannot read.

### 4.2 Extraction

Extract into the vault:

- identity and contact;
- education: school, degree, major, dates, GPA;
- experience: company, role, dates, bullets;
- projects: name, role, dates, tech, bullets;
- skills, awards, certificates, languages;
- links;
- layout DNA (for the template audit): page size, margins, columns, fonts, colors, section order, heading style, entry layout, bullet style, photo/QR.

Show the extracted facts for confirmation. Mark missing or ambiguous fields.

### 4.3 Template audit (must run before "keep my template")

The original template is judged on seven dimensions:

| Dimension | Checks | Hard fail examples |
|---|---|---|
| Parseability | Text selectable, single reading order, standard headings, no key text in images | Scanned PDF, text in images, multi-column scramble |
| Structure | Contact, education, experience, projects, skills; consistent dates | Missing education, unparseable dates |
| Typography | Body ≥ 9pt, readable line-height, ≤ 2 font families, consistent weights | 7pt body, five fonts, light-weight paragraphs |
| Layout | Margins, alignment, spacing rhythm, no overlap/clipping | Overlapping text, orphan headings, clipped lines |
| Market fit | Photo policy, personal fields, page size, section set | Photo in `intl_en`; missing education in CN campus |
| Print safety | A4, safe margins, no cropped content, links visible | Content outside the page |
| Maintainability | Editable source, consistent styles, no manual positioning everywhere | Flattened PDF, hundreds of absolute boxes |

### 4.4 Verdicts

| Verdict | Meaning | Action |
|---|---|---|
| `excellent` | Passes all dimensions and has a clear visual identity | Offer to keep and learn it |
| `good_with_fixes` | Minor spacing/typography issues | Offer to keep after fixes, or switch |
| `replace` | Fails one or more hard gates | Recommend our templates; explain why |
| `unmaintainable` | Cannot be reliably reproduced (scanned, flattened, unknown fonts) | Recommend our templates |

Never let the user keep a template that fails parseability or market fit without an explicit warning and a recorded override.

### 4.5 Keep-original protocol

If the verdict is `excellent` or `good_with_fixes`, and the user chooses to keep it:

1. **Extract layout DNA:**
   - page size and margins;
   - column grid;
   - font families, sizes, weights, line-height;
   - colors and rules;
   - header/contact layout;
   - section heading style;
   - entry layout (company/role/date alignment);
   - bullet style;
   - photo/QR slots;
   - section order and titles.
2. **Rebuild as a private HTML template** under `templates/user-<hash>/`:
   - `template.html`, `styles.css`, `manifest.json`;
   - `data-slot` markers for the renderer.
3. **Do not edit the original file.** The rebuild is derivative, for this user only.
4. **Preserve the visual language, not pixel-perfect PDF reproduction.** State this expectation explicitly.
5. **Show a side-by-side comparison** and ask for approval.
6. **Run the same QA gates.** If the original design cannot pass parseability, warn and offer a safe variant.

Fidelity expectations:

- HTML input: highest fidelity; reuse CSS where possible.
- DOCX input: medium-high; map styles and structure.
- PDF input: medium; positions and fonts can be approximated, not guaranteed.
- Image input: not supported in v1.

### 4.6 Replace protocol

If the verdict is `replace` or the user chooses to switch:

1. Explain the specific failure (one or two concrete reasons, not "it's ugly").
2. Recommend 2–3 templates by market, persona, and ATS priority.
3. Show previews with the user's actual content.
4. Render with the chosen template.
5. Keep the original file untouched; save the new output separately.

## 5. Additional routes worth supporting

These are natural extensions of the same engine. Recommended for v1 or v1.5:

### 5.1 `review` — diagnostic only

Input: existing resume. Output: a prioritized report (truth, targeting, structure, legibility, parsability, market fit) with before/after examples for the top issues. No rewrite unless the user asks.

### 5.2 `tailor` — one JD, one version

Input: vault or existing resume + JD. Output: selected facts, reordered bullets, keyword coverage, fit tier, gaps, risks, and a targeted resume. Never invent experience for a must-have.

### 5.3 `restyle` — content unchanged

Input: vault or existing resume. Output: same facts in a different template. Useful when the content is good but the design is weak.

### 5.4 `localize` — market switch, not translation

Input: vault. Output: a new resume for the target market and language, plus a parity report. See `docs/market-matrix.md`.

### 5.5 `update` — incremental change

Input: existing resume + new experience. Output: merged vault, updated resume, and a diff. Preserve the template if it passed the audit.

### 5.6 `recommend` — job fit

Input: vault + preferences. Output: role families, fit tiers, gaps, and next actions. No live job scraping in v1.

### 5.7 `template-import` — user-supplied template

Input: HTML/DOCX/PDF template or resume. Output: audit verdict; if acceptable, a private learned template. Never publish or redistribute a user-provided template.

### 5.8 `build-mode` — thin profile

Input: student with no internship/projects. Output: an honest starter resume + a 2–4 week proof-building plan. Never invent projects.

## 6. Out of scope

Decline and route away:

- cover letters;
- interview preparation / behavioral stories;
- offer comparison / salary negotiation;
- job-board scraping / auto-apply;
- visa or immigration advice;
- legal advice.

## 7. CLI mapping

```
resume create                  # Route A
resume optimize <file>         # Route B: ingest → audit → template decision
resume review <file>           # diagnostic only
resume tailor <file|app> --jd jd.md
resume restyle <file|app> --template <id>
resume localize <app> --to zh --market cn_internet
resume update <file|app>       # merge new facts
resume recommend
resume template-import <file>  # audit + learn
resume check                   # sufficiency
resume build <app> [--draft]
```

## 8. Template quality rubric (summary)

A template is `excellent` only if:

- text is selectable and reading order is correct;
- standard headings and complete sections;
- body ≥ 9pt, readable line-height, ≤ 2 font families;
- no overlap, clipping, or orphan headings;
- market-appropriate photo/personal fields/page size;
- print-safe at A4;
- editable and maintainable;
- has a coherent visual identity, not a generic default.

Anything less is `good_with_fixes`, `replace`, or `unmaintainable`.

## 9. Privacy and licensing for user templates

- User-provided templates and resumes are processed locally.
- Rebuilt private templates live under `templates/user-<hash>/` and are never published.
- Do not add a user's template to the public library without explicit permission.
- Do not clone a known commercial template into the public library; personal-use reconstruction only.
- Do not upload or redistribute user files.

## 10. Recommended v1 scope

Include:

- `create`, `optimize`, `review`, `restyle`, `tailor`, `localize`, `recommend`.
- Format ingestion: DOCX, PDF (text-based), HTML, MD/TXT.
- Template audit and keep-original for HTML/DOCX.
- Replace-with-our-template for failed audits.

Defer:

- image/OCR ingestion;
- PDF template reconstruction at high fidelity;
- `template-import` for arbitrary commercial templates;
- `update` with automatic merge (start with manual confirmation).
