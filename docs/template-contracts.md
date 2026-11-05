# Template Contracts

A template is a renderer contract, not a design file. The manifest declares slots and budgets; the HTML contains slots; the CSS styles them. Content never lives in a template.

## 1. Shared contract

Every template must:

1. Validate against `schema/template.schema.json`.
2. Declare all required slots; a missing slot at render time is a hard error.
3. Use only `data-slot` markers listed in `schema/README.md` §3.
4. Keep all content out of markup; no hard-coded names, schools, or sample bullets in the shipped template.
5. Use an external `styles.css` with CSS variables; no inline style attributes except variables set by the renderer.
6. Use a system font stack. No external fonts, icon fonts, or CDN assets.
7. Avoid tables for layout; no text in images; no critical text in pseudo-elements.
8. Collapse empty optional sections completely — no heading, border, or blank block remains.
9. Never print "N/A", "—", or an empty label.
10. Print safely at A4 with the declared margins; no content outside the page.
11. Be tested for extracted text order, not only visual appearance.
12. Produce byte-stable HTML for the same input.
13. Reserve an optional `identity.photo` slot in the header. When no photo is set, the slot must collapse completely: no border, no background, no blank box. `intl_en` suppresses photos by policy; CN markets may show one.

## 2. Typography floor

| Element | Size | Weight |
|---|---|---|
| Name | 16–20pt | 600–700 |
| Section heading | 10.5–12pt | 600–700 |
| Entry title | 10.5–11pt | 600 |
| Body / bullets | 10–10.5pt | 400 |
| Dates / meta | 9–10pt | 400 |
| Absolute minimum | 9pt | — |

- Line height: 1.3–1.45 for body, 1.15–1.25 for headings.
- At most two font families.
- Margins: 15–20mm; never below 12mm.
- Accent color: at most one, plus black/gray. Must remain legible in grayscale.
- No light gray body text below `#555` on white.

## 3. The template library

The library contains **six templates**. Each one has a different structural idea; none is a renamed copy of another. The split by language is organizational, not visual: no "CN"/"EN" badge is ever rendered into a resume. The manifest carries `language` only for routing and validation.

```
templates/
├── cn/
│   ├── campus/              # single-column campus sheet
│   └── zh-professional/     # left sidebar + experience-first main column
├── en/
│   ├── ats-classic/         # bare single-column ATS sheet
│   ├── modern-sidebar/      # main column + right sidebar
│   ├── editorial/           # magazine-style one page
│   └── executive/           # centered letterhead, two pages
└── user-<hash>/             # private learned templates, not part of the public library
```

### 3.0 Language families

- **Chinese family:** `campus`, `zh-professional`. Chinese-first font stacks (`Source Han Sans SC`, `Noto Sans CJK SC`, `PingFang SC`, `Microsoft YaHei`), line-height 1.5–1.55, no uppercase transform, `YYYY.MM` dates, no 求职意向, optional portrait.
- **English family:** `ats-classic`, `modern-sidebar`, `editorial`, `executive`. Latin-first stacks (`Calibri`, `Arial`, `Georgia`), 1.3–1.4 leading, uppercase headings, `YYYY-MM` dates, no CJK fonts in the primary stack.
- Cross-language use is rejected with `render.language_mismatch`. `resume templates` prints each template's language. A Chinese resume gets a Chinese template; an English resume gets an English template. This avoids mixed font metrics and inconsistent line spacing.

| ID | Lang | Market | Personas | Size / pages | Structure | Photo | ATS posture |
|---|---|---|---|---|---|---|---|
| `ats-classic` | en | `intl_en` | experienced, new_grad, student_with_internship, student_with_projects, career_switcher | A4 · 1–2 | single | slot, suppressed by market policy | highest |
| `modern-sidebar` | en | `intl_en` | experienced, career_switcher | A4 · 1–2 | main + right sidebar | slot, suppressed by market policy | medium, with single-column fallback |
| `editorial` | en | `intl_en` | student_with_projects, new_grad, student_with_internship, career_switcher | A4 · 1 | single, magazine | slot, suppressed by market policy | medium-high |
| `executive` | en | `intl_en` | senior_manager, experienced | A4 · 2 | single, centered letterhead | slot, suppressed by market policy | high |
| `campus` | zh | `cn_internet`, `cn_soe`, `cn_finance`, `cn_creative` | student_with_projects, student_with_internship, new_grad | A4 · 1–2 | single, campus order | optional portrait | high |
| `zh-professional` | zh | `cn_internet`, `cn_soe`, `cn_finance`, `cn_creative` | experienced, career_switcher, senior_manager | A4 · 2–3 | left sidebar + main | optional portrait | high |

### 3.1 `ats-classic`

- Purpose: the safe default. Recruiter- and parser-friendly.
- Order: name/contact → summary → experience → projects → skills → education → awards.
- Required: `identity.name`, `identity.contact`, `section.education`, `section.experience`, `section.skills`.
- Optional: `identity.links`, `identity.photo`, `section.summary`, `section.projects`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: single column, black text, one rule under section headings, no icons, no tables. The photo slot exists for cross-market reuse but `intl_en` policy suppresses rendering.

### 3.2 `campus`

- Purpose: CN campus and intern applications.
- Order: name/contact → education → skills → experience (实习) → projects → awards → open source.
- Required: `identity.name`, `identity.contact`, `section.education`, `section.skills`.
- Optional: `identity.links`, `identity.photo`, `section.experience`, `section.projects`, `section.awards`, `section.open_source`, `section.certificates`, `section.languages`, `section.publications`, `section.summary`.
- Rules: education before experience; 1–2 pages; an optional portrait slot collapses completely when empty; CS fundamentals group rendered with the same weight as AI skills; no 求职意向 and no "自我评价" block.
- CN page counts: student and <3 years 1–2 pages; 3+ years 2–3 pages.

### 3.3 `modern-sidebar`

- Purpose: a restrained two-column layout for experienced candidates who want visual identity without losing parseability.
- Layout: main column = summary, experience, projects, publications, open source; right sidebar = skills, education, awards, certificates, languages.
- Required: `identity.name`, `identity.contact`, `section.summary`, `section.experience`, `section.skills`, `section.education`.
- Optional: `identity.links`, `identity.photo`, `section.projects`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: DOM order is single-column and logical; CSS grid creates the visual columns. `ats.parse_fallback` points to a single-column variant. Sidebar background must be light enough for grayscale printing. The photo slot exists but `intl_en` policy suppresses rendering.

### 3.4 `editorial`

- Purpose: a distinctive one-page layout for early-career candidates in international markets.
- Order: name/contact → summary → selected projects → experience → skills → education → awards.
- Required: `identity.name`, `identity.contact`, `section.summary`, `section.projects`, `section.education`.
- Optional: `identity.links`, `identity.photo`, `section.experience`, `section.skills`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: one accent color, generous whitespace, serif headings, no decorative graphics, exactly one page. The photo slot exists but `intl_en` policy suppresses rendering. Projects may lead when stronger than experience.

### 3.5 `executive`

- Purpose: two-page senior/manager resume with a centered letterhead.
- Order: name/contact → executive summary → experience → leadership & skills → education → awards/publications.
- Required: `identity.name`, `identity.contact`, `section.summary`, `section.experience`, `section.education`.
- Optional: `identity.links`, `identity.photo`, `section.skills`, `section.projects`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: outcome-first bullets, scope and team size visible, no photo, no decorative timeline. Page 2 must not be filler; the two-page target is enforced by QA. The photo slot exists but `intl_en` policy suppresses rendering.

### 3.6 `zh-professional`

- Purpose: experienced Chinese-market candidates. This is a **left-sidebar** design, not a renamed campus sheet.
- Layout: header spans the page; left sidebar = portrait, 专业技能, 教育经历, 证书, 语言能力; main column = 个人简介, 工作经历, 项目经历, 荣誉奖项, 论文 / 发表, 开源项目.
- Required: `identity.name`, `identity.contact`, `section.summary`, `section.experience`, `section.education`, `section.skills`.
- Optional: `identity.links`, `identity.photo`, `section.projects`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: Chinese-first fonts, 1.55 line-height, no uppercase, no 求职意向, 2–3 pages, optional portrait slot that collapses when empty. Experience and projects lead; the sidebar carries credentials and skills.

## 4. Content budgets

| Item | Limit |
|---|---|
| Summary | 240 EN chars / 120 ZH chars |
| Bullets per role | 3–5 |
| Bullets per project | 2–4 |
| Skills shown | 8–16 EN / 6–12 ZH |
| Roles | 1–5 |
| Projects | 1–4 |

Budgets are enforced before render. The renderer trims the weakest bullets only when the application's selection marks them as trimmable; it never silently drops a verified result.

## 5. Print rules

- `@page` declares A4 and the margins from the manifest.
- On screen, the page is framed at 210 × 297 mm with a shadow; `@media print` removes the frame and lets `@page` supply the A4 margins.
- No content in browser headers/footers; no reliance on browser page numbers.
- Links are visible as text when the target market expects it; URLs are not hidden behind icons.
- Colors are grayscale-safe: removing color must not remove meaning.
- A two-page template must break at a section boundary, never mid-entry.

## 6. Editable variant

- A separate `resume-editable.html` with `contenteditable` only on text slots.
- A floating toolbar for font size, bold, and spacing; no structural editing.
- Clearly labeled "Editable preview — the vault remains the source of truth."
- Browser edits are not merged back in v1.
- The locked HTML is the only file considered deliverable.

## 7. User-learned templates

- Stored under `templates/user-<hash>/`, `status: private`, `provenance.kind: user_learned`.
- Never added to the public library, never redistributed, never committed by default.
- Must satisfy the same slot contract and QA gates as library templates.
- Preserve the original visual language, not pixel-perfect PDF reproduction.

## 8. Failure behavior

| Failure | Behavior |
|---|---|
| Missing required slot | Exit `3`; name the slot and the application field. |
| Invalid manifest | Exit `3`; name the failing field. |
| Budget exceeded | Exit `4`; name the section and the overage. |
| Overflow / clipping | Exit `4`; name the page and element. |
| Unreadable extracted text | Exit `4`; offer the fallback template. |
| Unsupported photo in market | Exit `4`; remove photo or switch template. |
