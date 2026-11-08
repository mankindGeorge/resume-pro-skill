# Changelog

All notable changes to this project are documented here. The format follows Keep a Changelog; versions use SemVer.

## [Unreleased]

### Fixed

- Selection keeps each item's bullets in vault order rather than score order, so a declared framework's recipe order (for example STAR background → framework → solution → result) survives `resume new`/`tailor` and is no longer falsely rejected by `lint.framework_order`; the project bullet budget no longer silently truncates a recipe slot.
- `qa.layout.short_line` now flags only tiny orphan lines under 10 characters, superseding the earlier 2/5 printable-width rule; English resumes are currently exempt (a 10-character cutoff misflags complete English word tails), and `qa.layout.text_balance` is advisory and never blocks a build.
- Build requires confirmed facts, refreshes parity on rebuild, and snapshots the delivered output; version history is bounded and pruning is reported.
- CLI redacts phone/email/ID/address from stdout JSON and logs by default (`--include-pii` opts out); `--jd` is persisted as an absolute path and `--cwd` path resolution is documented; internal errors exit `7` with a report path.
- Scanned/image-only files are refused; unreadable intake sessions are backed up and warned instead of silently reset; the academic research blocker maps to a targeted question.
- Line endings are normalized to LF via `.gitattributes` so byte-sensitive golden preview hashes stay stable across checkouts.

### Changed

- Bump the package version to 0.2.0.

- Change requests follow the same standards: before applying any user-requested change, re-read the user's input and the governing rules (framework recipe and label set, market rules, the short-tail line rule, naming and monolingual rules) and write strictly to those standards.
- The compact templates render one award per line: the awards list is single-column so each honor reads on its own row.
- STAR packaging keeps merged content inside the recipe: an integrated tool or open-source artifact belongs within the four STAR points instead of extra bullets.
- Point labels (`项目背景：` / `Background:` and friends) render bold in every resume, so the point structure is visible at a glance in both languages.
- The workspace keeps only the deliverable resume files (the final HTML and its editable copy). QA, lint, render, and parity reports stay under `.resume/applications/<slug>/` and are never copied into the workspace.
- Write writing frameworks and content packaging in one document (`references/writing-engine.md`): each of the six frameworks — STAR, XYZ, FAB, CAR, result-first, user voice — carries its own packaging recipe with labeled points and examples. Packaging is no longer shaped like one framework only; lint and skill instructions refer to the chosen framework's recipe.
- Require the agent to use a host interactive question tool across all resume routes, continuing the same conversation and task after each answer rather than ending with a questionnaire. Preserve free-text answers and pause/resume; report unavailable or denied tools without a silent fallback.
- Require explicit fact confirmation independently of intake completion and sufficiency. Clarify collection-correction semantics and the boundary between host-tool instructions and CLI enforcement.
- Complete Chinese and English coverage for all five designs (`ats-classic`, `campus`, `modern-sidebar`, `editorial`, `executive`): 10 public variants. The `cn`/`en` folders denote resume language only, with manifest `language: zh`/`en`.
- Resolve rendering and QA templates by `writing.locale`, falling back to the market profile's `language`. Require an explicit language for multilingual `load_template` calls rather than preferring `cn`; list all 10 public variants.
- Preserve the source design ID during target-market localization unless `--template` explicitly overrides it. Missing target-language learned templates fail clearly without a silent design fallback; legacy flat learned templates remain supported with language validation. Restyling changes appearance, not market or fact selection.
- Keep existing default recommendations, market/persona selection and writing rules, page/photo policies, fact confirmation, layout capacity budgets, and fixed two-column regions. Recommendations are not exclusive design restrictions. Template review status is unchanged; bilingual coverage is not approval or release.
- Require the agent to ask the user which layout to use before rendering during creation and optimization, recommending the default but never accepting it silently, and to show where to preview each design (`templates/<cn|en>/<id>/preview.html`).
- Reframe the project as China-first with international support: Chinese-market profiles lead, while `intl_en` and English resume variants remain fully available. Market and persona rules are unchanged.
- Remove italic and alternative serif/variant typography from all resume templates: editorial headings now use the standard sans stack, and every variant disables synthetic styles, ligatures, contextual alternates, and old-style figures.
- Order sections by HR priority: students lead with education → experience → projects → skills; professionals lead with summary → experience → projects → education → skills. `modern-sidebar` moves education into the main column and reorders within each column.
- Provide six layouts and twelve language variants, including the compact campus design; recommend `modern-sidebar` for Chinese-market professional profiles.
- Correct `schema/README.md` to describe locale-based template resolution instead of the removed market-locked match.

### Added

- School and project names accept per-locale text (`localizedText`), so the Chinese and English resumes each keep their own name; `localize` now requires target-language names like every other localized field. When sourcing them: look up the school's official English name on the web if the user has not provided one, and propose 2–3 project-name candidates interactively for the user to pick or edit.
- QA check `qa.layout.short_line`: every rendered line of a project or experience intro must fill at least 2/5 of the printable width. A wrap that leaves only a few characters alone on a line is a hard failure; the fix expands the sentence with real detail (preferred) or tightens the wording. Line measurements use the template's real margins, and the rule is written into the writing engine shared rules.
- Add a qualified-project content-sufficiency standard: a project presentation covers background/role/trade-offs/difficulties/evaluation/deployment/outcomes/feedback, and guided interaction proactively asks, one question at a time, for the dimensions the user may not have thought to mention instead of waiting for more input.
- Five regression tests for the mandatory interaction instructions, multi-round CLI answers, invalid-input recovery, read-only summary/resume, unknown answers, multiline Chinese input, and confirmation recovery. These are not live host-UI tests.
- `resume templates` now prints each variant's `preview.html` path in human output and a `preview` field in `--json`, so users can open a design in a browser before choosing. A contract test guards the create/optimize template-choice and preview-location instructions, and listing tests assert the preview paths.
- Add `scripts/package_skill.py`, which builds a deterministic, private-safe skill ZIP with one top-level folder, excludes private review material, learned templates, local workspaces, caches, and secret-like files, and unzips/bootstrap-checks the archive before reporting success.
- Add the root `resume.py` launcher and `bootstrap.py` runtime check/install. They verify Python, dependencies, and all 12 template variants; `--install` performs an editable install for the `resume` command, while `--deps-only` supports environments where pip cannot install the package.
- Add packaging documentation and regression tests for archive completeness, determinism, private-path exclusion, and bootstrap readiness.
- Add template preview thumbnails to both READMEs and `scripts/build_readme_previews.py` to regenerate them; packaging includes the preview assets.
- Add the `compact` layout: a one-page campus design with ruled headings, centered entry headers, and a two-column awards list.
- Publish user-facing files to `workspace/<project-slug>/`: builds copy the resume, editable copy, and reports; reviews publish their report to a review subfolder. Each application or review gets its own folder; `.resume/` remains internal state.
- Keep Chinese previews Chinese: the compact Chinese preview uses the Chinese student sample, with only proper nouns and technical terms left in English.
- Render education as major on the entry line and degree/GPA as a smaller note below, instead of one combined line.
- Place workspace outputs under the skill root's `workspace/`; one subfolder per application or review.
- After a diagnosis, ask whether to start fixing; if yes, offer one multi-select P0/P1/P2 choice, ask the writing framework, then work through the selected priorities one question at a time and re-run build/QA. The rest of the flow mirrors Create from zero.
- Enforce content sufficiency: every kept role/project answers background, role, action, and result; ask for outcomes when only tools are given; use the selected framework's question ladder; and run silent depth mining for thin student/intern profiles, packaging only real contributions without inventing facts. When no number exists, offer to package the existing work with a stronger narrative instead of treating "keep" and "skip" as the same choice.
- Flag `至今` / `present` end dates during lint and ask for a concrete end month before delivery; render education as `major · degree` on the entry line with GPA/rank only as a smaller note below.
- Require each kept project to read as 3–4 labeled STAR points with substantial real detail. Lint flags thin bullets and thin projects; if a project cannot be packaged to that depth, the skill excludes it rather than keeping a weak block.
- Templates render points as labeled paragraphs or plain lines, never `<ul>` / `<ol>` / `<li>` with a leading dot.
- Strengthen packaging rules: solutions must explain the pain point and why the approach fits; results must state the problem solved and the change created, not repeat technology or filler dates. QA now checks horizontal text balance so sparse left-biased layouts do not pass silently.

- Add project packaging for thin projects: classify the project, summarize the framework/难点/成果 it usually needs, and ask the user to keep and deepen it or remove it before writing.
- Require measurable data wherever it strengthens the story: missing numbers now warn, and the skill proposes plausible candidate values for user confirmation before writing them. Real data is always requested first; candidate values are only offered after the user chooses no data.

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
