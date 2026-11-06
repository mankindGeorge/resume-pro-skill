# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog; versions use SemVer.

## [Unreleased]

### Changed

- Require the agent to use a host interactive question tool across all resume routes, continuing the same conversation and task after each answer rather than ending with a questionnaire. Preserve free-text answers and pause/resume; report unavailable or denied tools without a silent fallback.
- Require explicit fact confirmation independently of intake completion and sufficiency. Clarify collection-correction semantics and the boundary between host-tool instructions and CLI enforcement.
- Complete Chinese and English coverage for all six designs (`ats-classic`, `campus`, `modern-sidebar`, `editorial`, `executive`, `zh-professional`): 12 public variants. The `cn`/`en` folders denote resume language only, with manifest `language: zh`/`en`, not market restrictions; retain the historical `zh-professional` ID in both languages.
- Resolve rendering and QA templates by `writing.locale`, falling back to the market profile's `language`. Require an explicit language for multilingual `load_template` calls rather than preferring `cn`; list all 12 public variants.
- Preserve the source design ID during target-market localization unless `--template` explicitly overrides it. Missing target-language learned templates fail clearly without a silent design fallback; legacy flat learned templates remain supported with language validation. Restyling changes appearance, not market or fact selection.
- Keep existing default recommendations, market/persona selection and writing rules, page/photo policies, fact confirmation, layout capacity budgets, and fixed two-column regions. Recommendations are not exclusive design restrictions. Template review status is unchanged; bilingual coverage is not approval or release.
- Require the agent to ask the user which layout to use before rendering during creation and optimization, recommending the default but never accepting it silently, and to show where to preview each design (`templates/<cn|en>/<id>/preview.html`).
- Reframe the project as China-first with international support: Chinese-market profiles lead, while `intl_en` and English resume variants remain fully available. Market and persona rules are unchanged.
- Remove italic and alternative serif/variant typography from all resume templates: editorial headings now use the standard sans stack, and every variant disables synthetic styles, ligatures, contextual alternates, and old-style figures.
- Correct `schema/README.md` to describe locale-based template resolution instead of the removed market-locked match.

### Added

- Five regression tests for the mandatory interaction instructions, multi-round CLI answers, invalid-input recovery, read-only summary/resume, unknown answers, multiline Chinese input, and confirmation recovery. These are not live host-UI tests.
- `resume templates` now prints each variant's `preview.html` path in human output and a `preview` field in `--json`, so users can open a design in a browser before choosing. A contract test guards the create/optimize template-choice and preview-location instructions, and listing tests assert the preview paths.
- Add `scripts/package_skill.py`, which builds a deterministic, private-safe skill ZIP with one top-level folder, excludes private review material, learned templates, local workspaces, caches, and secret-like files, and unzips/bootstrap-checks the archive before reporting success.
- Add the root `resume.py` launcher and `bootstrap.py` runtime check/install. They verify Python, dependencies, and all 12 template variants; `--install` performs an editable install for the `resume` command, while `--deps-only` supports environments where pip cannot install the package.
- Add packaging documentation and regression tests for archive completeness, determinism, private-path exclusion, and bootstrap readiness.

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
