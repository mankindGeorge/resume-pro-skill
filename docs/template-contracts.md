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

The library contains **six distinct designs × two resume languages = 12 variants**. Each design has a different structure; its Chinese and English variants share that structure, with language-appropriate typography. Both `templates/cn/` and `templates/en/` contain all six IDs below. Private learned templates remain under `templates/user-<hash>/`, outside the public library.

### 3.0 Language variants and routing

- `templates/cn/<id>/` means Chinese resume text, with manifest `language: zh`; `templates/en/<id>/` means English, with `language: en`. These folders are not market restrictions. No "CN"/"EN" badge is rendered.
- Chinese variants use CJK-first font stacks and Chinese heading/date conventions; English variants use Latin-first typography and English conventions. Preserve each design's font hierarchy and capacity limits rather than treating the variants as renamed copies.
- Resolve a design with `load_template(id, language=zh|en)`. When the ID has multiple language variants, omitting language is an explicit ambiguity error; never search `cn` first and silently accept it. A requested but missing language variant also fails explicitly.
- Rendering and QA use the application's `writing.locale`, falling back to the market profile's `language` only when it is absent. Validate the selected manifest against that resolved language, not against a presumed market-exclusive design ID. `--lang` changes CLI messages, not resume language.
- `resume templates` lists 12 public variants, including each ID, its manifest language, and its `preview.html` path (printed in human output and a `preview` field in `--json`), plus private learned templates. Open `templates/<cn|en>/<id>/preview.html` in a browser to view a design. Keep the historical `zh-professional` ID compatible in both languages; its name does not restrict it to Chinese.
- During creation and optimization the agent asks the user which layout to use through the interactive question tool before rendering: present the six designs in the resume's language, recommend the market/persona default, show the preview paths, and pass the choice with `--template <id>`. Never accept the default silently when the user has not been asked.
- Existing defaults remain recommendations: `campus` for Chinese-market campus profiles, `zh-professional` for Chinese-market professional profiles, `ats-classic` for international default profiles, and `executive` for international senior profiles. They are not exclusive eligibility lists. Market/persona still govern fact selection, writing, page policy, photos, and fact confirmation.
- `restyle` changes appearance only, not market, persona, selection, or writing locale. `localize` retains its target-market reselection and rewriting workflow; it keeps the source design ID by default, unless an explicit `--template <id>` overrides it. Neither route translates rendered HTML.

| ID | Languages | Layout capacity | Structure | ATS posture |
|---|---|---|---|---|
| `ats-classic` | zh, en | A4 · 1–2 pages | single | highest |
| `campus` | zh, en | A4 · 1–2 pages | single, education-first | high |
| `modern-sidebar` | zh, en | A4 · 1–2 pages | main + right sidebar | medium, with single-column fallback |
| `editorial` | zh, en | A4 · 1 page | single, magazine | medium-high |
| `executive` | zh, en | A4 · 2 pages | single, centered letterhead | high |
| `zh-professional` | zh, en | A4 · 2–3 pages | left sidebar + main | high |

All designs reserve an optional photo slot; the market determines whether it is shown (`intl_en` suppresses it regardless of resume language). Layout capacity does not replace market/persona page policy: both remain binding, and bilingual availability does not authorize overflow, filler, or automatic redesign. Main/sidebar region assignments stay fixed; market-driven ranking and ordering must operate within those regions. The section orders below describe design structure, not new market-writing rules. ATS posture is a design aim, not a universal compatibility guarantee. Review status is unchanged; language coverage and signed manifests do not constitute design approval or release.

### 3.1 `ats-classic`

- Purpose: the safe default. Recruiter- and parser-friendly.
- Order: name/contact → summary → experience → projects → skills → education → awards.
- Required: `identity.name`, `identity.contact`, `section.education`, `section.experience`, `section.skills`.
- Optional: `identity.links`, `identity.photo`, `section.summary`, `section.projects`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: single column, black text, one rule under section headings, no icons, no tables. The photo slot exists for cross-market reuse but `intl_en` policy suppresses rendering.

### 3.2 `campus`

- Purpose: education-first campus and intern applications in either resume language.
- Order: name/contact → education → skills → experience → projects → awards → open source; labels follow the resume language.
- Required: `identity.name`, `identity.contact`, `section.education`, `section.skills`.
- Optional: `identity.links`, `identity.photo`, `section.experience`, `section.projects`, `section.awards`, `section.open_source`, `section.certificates`, `section.languages`, `section.publications`, `section.summary`.
- Rules: education before experience; 1–2-page layout capacity; an optional portrait slot collapses completely when empty; for CN campus profiles, render CS fundamentals with the same weight as AI skills; no 求职意向 and no "自我评价" block.
- CN market page policy remains student and <3 years 1–2 pages; 3+ years 2–3 pages. It does not expand this design's capacity.

### 3.3 `modern-sidebar`

- Purpose: a restrained two-column layout for experienced candidates who want visual identity without losing parseability.
- Layout: main column = summary, experience, projects, publications, open source; right sidebar = skills, education, awards, certificates, languages.
- Required: `identity.name`, `identity.contact`, `section.summary`, `section.experience`, `section.skills`, `section.education`.
- Optional: `identity.links`, `identity.photo`, `section.projects`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: DOM order is single-column and logical; CSS grid creates the visual columns. `ats.parse_fallback` points to a single-column variant. Sidebar background must be light enough for grayscale printing. The photo slot exists but `intl_en` policy suppresses rendering.

### 3.4 `editorial`

- Purpose: a distinctive one-page layout for early-career candidates in either resume language, not restricted to international markets.
- Order: name/contact → summary → selected projects → experience → skills → education → awards.
- Required: `identity.name`, `identity.contact`, `section.summary`, `section.projects`, `section.education`.
- Optional: `identity.links`, `identity.photo`, `section.experience`, `section.skills`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: one accent color, generous whitespace, serif headings, no decorative graphics, exactly one page. The photo slot exists but `intl_en` policy suppresses rendering. Projects may lead when stronger than experience.

### 3.5 `executive`

- Purpose: two-page senior/manager resume with a centered letterhead.
- Order: name/contact → executive summary → experience → leadership & skills → education → awards/publications.
- Required: `identity.name`, `identity.contact`, `section.summary`, `section.experience`, `section.education`.
- Optional: `identity.links`, `identity.photo`, `section.skills`, `section.projects`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: show verified outcomes, scope, and team size using the consented writing framework; no decorative timeline. Page 2 must not be filler; the two-page target is enforced by QA. The optional photo follows market policy: `intl_en` suppresses it, not the design itself.

### 3.6 `zh-professional`

- Purpose: an experience-first **left-sidebar** design in either resume language, not a renamed campus sheet. Preserve the historical ID for compatibility; `zh-` does not mean English is excluded.
- Layout: header spans the page; left sidebar = portrait, skills, education, certificates, languages; main column = summary, experience, projects, awards, publications, open source. Translate labels for the resume language without moving sections between regions.
- Required: `identity.name`, `identity.contact`, `section.summary`, `section.experience`, `section.education`, `section.skills`.
- Optional: `identity.links`, `identity.photo`, `section.projects`, `section.awards`, `section.certificates`, `section.languages`, `section.publications`, `section.open_source`.
- Rules: language-appropriate fonts and leading, no 求职意向, 2–3-page layout capacity, optional portrait slot that collapses when empty. Experience and projects lead; the sidebar carries credentials and skills.

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
- Legacy flat learned templates remain loadable, but their manifest language must match the requested resume language. Do not assume private templates have both variants merely because the public library does.
- If localization retains a learned ID with no target-language variant, fail explicitly; do not silently replace it with a recommended public design. An explicit `--template <id>` may select an available alternative.

## 8. Failure behavior

| Failure | Behavior |
|---|---|
| Multilingual ID without an explicit loader language | Report ambiguity; require `load_template(id, language=zh|en)`, never prefer `cn`. |
| Missing language variant or mismatched manifest language | Fail explicitly, including for flat learned templates; never silently change design. |
| Missing required slot | Exit `3`; name the slot and the application field. |
| Invalid manifest | Exit `3`; name the failing field. |
| Budget exceeded | Exit `4`; name the section and the overage. |
| Overflow / clipping | Exit `4`; name the page and element. |
| Unreadable extracted text | Exit `4`; offer the fallback template without silently applying it. |
| Unsupported photo in market | Exit `4` if forbidden content reaches QA; remove it. Switching designs or language does not change market policy. |
