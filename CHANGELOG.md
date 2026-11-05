# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog; versions use SemVer.

## [Unreleased]

### Changed

- Require the agent to use a host interactive question tool across all resume routes, continuing the same conversation and task after each answer rather than ending with a questionnaire. Preserve free-text answers and pause/resume; report unavailable or denied tools without a silent fallback.
- Require explicit fact confirmation independently of intake completion and sufficiency. Clarify collection-correction semantics and the boundary between host-tool instructions and CLI enforcement.

### Added

- Five regression tests for the mandatory interaction instructions, multi-round CLI answers, invalid-input recovery, read-only summary/resume, unknown answers, multiline Chinese input, and confirmation recovery. These are not live host-UI tests.

## [0.1.0] — 2026-11-05

### Added

- Career vault with evidence ids, per-locale phrasing, atomic saves, merge/dedupe, and stable ids.
- Guided intake with one question at a time, persona/market branching, session resume, and skip/unknown handling.
- Seven-dimension sufficiency gate (`blocked | minimum | strong`) with targeted questions and a draft label.
- DOCX, text-based PDF, HTML, MD, and TXT ingestion; scanned-PDF detection; layout DNA; seven-dimension template audit; private template learning with side-by-side preview.
- Per-application model, fact selection/ordering, writing-framework registry and explicit consent, 10-second skim test.
- Global + Chinese lint rules, JD parsing and fit scoring with ranges/tiers/gaps/risks, role-family recommendation.
- Deterministic, self-contained HTML renderer with strict slots, inlined CSS, signed manifests, layout budgets, and an editable non-canonical variant.
- Six structurally distinct A4 templates split into `templates/cn/` and `templates/en/`: `campus`, `zh-professional`, `ats-classic`, `modern-sidebar`, `editorial`, `executive`, with previews and signed manifests.
- Optional portrait slot in every template; embedded as a data URI; completely invisible when empty; `intl_en` suppresses photos.
- Mass-vs-targeted application mode; targeted resumes classify experiences/projects by role family, ask for a preferred role, rank relevant facts first, and include the role in the HTML filename unless `--no-role-in-filename` is used.
- No 求职意向/job-intent section is rendered; the target role is used only for targeting and naming.
- EN↔ZH transcreation from facts, locale-gap blocking/draft markers, parity checks with 万→K normalization.
- Browser-backed QA (pages, extracted text, bullets, headings, font floor, sensitive fields, privacy), `audit`, version snapshots, and `diff`.
- `SKILL.md`, install guide, walkthrough, evaluation notes, license scan, and 190 tests.

### Notes

- Output is HTML only. PDF is produced by the user's browser print dialog (A4).
- No OCR, DOCX/LaTeX export, live job-board scraping, auto-apply, cover letters, interview prep, offer comparison, or salary negotiation.
- Experimental markets are configuration stubs, not validated profiles.

[0.1.0]: https://github.com/your-org/resume-pro-skill/releases/tag/v0.1.0
