# Quickstart

Collect and confirm facts, check sufficiency, select and write for the target market, then render and audit HTML using a language-matched template variant.

## 1. Install for development

```bash
python -m pip install -e ".[dev]"
resume --version
```

Without installing:

```bash
PYTHONPATH=src python -m resume_pro.cli --version
```

## 2. Create a local workspace

```bash
resume init --market cn_internet --persona student_with_internship
```

This creates:

```
.resume/
├── vault.yaml            # facts + evidence
└── intake-session.json   # answers, skips, flags, artifacts
```

`--market` and `--persona` are optional; they are the first two intake questions.

## 3. Run the guided intake

```bash
resume intake
```

- One question at a time.
- The intake asks whether the resume is mainly for mass applications. If not, classify each experience/project by job family and choose a preferred role.
- Every question says why it is asked.
- Optional questions accept Enter or `skip`.
- `summary` shows what has been collected.
- `quit` saves and exits; `resume intake` continues.
- `I don't know` is accepted. It records a blocker instead of inventing a fact.

## 4. Check the gate

```bash
resume check
```

Exit codes:

| Code | Meaning |
|---|---|
| `0` | `minimum` or `strong` |
| `2` | `blocked` |
| `3` | invalid input or missing target context |

`check` writes `.resume/sufficiency.json` with dimensions, blockers, warnings, and targeted questions.

```bash
resume profile            # human summary
resume --json profile     # machine summary + gate
```

## 5. Agent-driven intake

The agent must use the host's interactive question tool (`AskUserQuestion` or an available equivalent), wait for each answer, save it, and immediately continue the same task. Do not end with a questionnaire or ask the user to say "continue". Free-text answers, explicit pause, and later resume must remain possible. If no suitable tool is available or permission is denied, report that limitation rather than silently falling back to final-message questions. See the [continuous interaction protocol](intake-and-sufficiency.md#13-continuous-agent-interaction).

The CLI is designed to be driven by an agent without a TTY. These are individual steps in the agent's loop, not a script to run without real user answers:

```bash
resume --json intake
# => {"ok": true, "question": {"id": "target.market", ...}, "progress": {...}}

resume --json intake --answer "cn_internet"
resume --json intake --answer "student_with_internship"
resume --json intake --skip            # skip an optional question
resume --json intake --answer "后端开发工程师（校招）"
```

To correct a specific answer:

```bash
resume --json intake --id identity.full_name --answer "Li Ming"
```

Re-answering after confirmation reopens the vault (`status: collecting`) and requires confirmation again.

## 6. Existing resume

```bash
# Diagnose only; never writes facts or rewrites the file.
resume review resume.pdf --market intl_en --persona experienced

# Extract facts, audit the template, and merge into the vault.
resume optimize resume.docx --market cn_internet --persona student_with_internship

# Keep the original template only if the audit allows it.
resume optimize resume.docx --market cn_internet --persona student_with_internship --keep-template

# Audit a template without touching the vault.
resume template-import my-template.html --market intl_en --persona experienced

# Preview the same facts in a learned template.
resume restyle resume.docx --template user-abc123 --market intl_en --persona experienced
```

Inputs: DOCX, text-based PDF, HTML, MD, TXT. DOC/RTF need LibreOffice. Scanned PDFs are detected and refused in v1; there is no OCR.

The audit has seven dimensions and four verdicts:

| Verdict | Meaning |
|---|---|
| `excellent` | Keep allowed; clear visual identity |
| `good_with_fixes` | Keep allowed; minor issues |
| `replace` | At least one hard failure |
| `unmaintainable` | Scanned, flattened, or unreadable |

A `replace`/`unmaintainable` verdict blocks `--keep-template` (exit `4`). `--override "reason"` records an explicit exception. Learned templates live under `templates/user-<hash>/` and are ignored by git.

Exit codes for ingestion routes:

| Code | Meaning |
|---|---|
| `0` | Report or merge succeeded |
| `3` | Invalid input or missing target context |
| `4` | Template audit hard failure / keep refused |
| `5` | Unsupported format |
| `6` | Missing external dependency (for example LibreOffice) |

## 7. Target, lint, and match

```bash
# Create an application with an explicit writing framework and a user-chosen layout.
resume new --role "Backend Engineer" --market cn_internet   --persona student_with_internship --framework result_first --template campus

# Content lint + CN rules + 10-second skim.
resume lint --app <slug>

# JD fit report: must/nice/hidden, gaps, risks, score range.
resume match --app <slug> --jd jd.md

# Select facts against the JD and create/update the application.
resume tailor --app <slug> --jd jd.md --framework result_first

# Role families and a 2–4 week proof plan.
resume recommend --app <slug>
```

The writing framework must be chosen explicitly: `star`, `xyz`, `fab`, `car`, `result_first`, or `user_voice`. The application stores the choice and `consent: true`; nothing is rewritten silently.

`match` always reports a range, never a single number. A missing gate requirement caps the score; a work-authorization unknown becomes a risk, not an invented fact.

## 8. Build

```bash
resume build <slug> --yes
resume build <slug> --draft
resume build <slug> --template modern-sidebar
resume templates
resume restyle --app <slug> --template modern-sidebar --yes
resume photo portrait.jpg --app <slug>
```

Build behavior:

- `blocked` → exit `2`, nothing is written.
- `minimum` → exit `2` unless `--yes`.
- Lint errors → exit `4`, nothing is rendered.
- Success → writes the rendered HTML, editable HTML, `render.json`, and `lint.json`. Targeted applications include the preferred role in the file name (for example `resume-backend-engineer.html`); mass applications use `resume.html`.

The rendered HTML is the canonical, self-contained file with inline CSS. The editable HTML is a non-canonical preview with `contenteditable` text slots and a toolbar; browser edits are not merged back.

Photos are optional. Every template reserves a portrait slot; it collapses completely when no photo is set. `resume photo <file>` stores the image and the renderer embeds it as a data URI. `intl_en` suppresses photos by policy; CN markets may show one. Choosing another design or resume language does not change that policy.

`--draft` adds a fixed `DRAFT — NOT FOR SUBMISSION` banner. `resume templates` lists **12 public variants: six distinct designs in both Chinese and English**, plus any learned `user-*` templates, and prints each variant's `preview.html` path (also a `preview` field in `--json`). Open that file in a browser to see the design before choosing.

All six IDs — `ats-classic`, `campus`, `modern-sidebar`, `editorial`, `executive`, `zh-professional` — exist in both `templates/cn/` (manifest `language: zh`) and `templates/en/` (`language: en`). The folders mean resume language, not market eligibility. `zh-professional` retains its historical ID and works in English too. Rendering and QA select the variant by `writing.locale`, falling back to the market profile's `language`; missing or mismatched variants fail explicitly. Direct `load_template(id, language=zh|en)` calls must specify language for multilingual IDs: omission fails instead of preferring `cn`. The CLI resolves it from the application, not from message-only `--lang`.

Default recommendations remain `campus` / `zh-professional` for Chinese-market campus / professional profiles and `ats-classic` / `executive` for international default / senior profiles. They are not exclusive choices. During creation the agent asks the user which layout to use through the interactive question tool before rendering — presenting the six designs in the resume's language, recommending the default, and pointing to each `templates/<cn|en>/<id>/preview.html` — then passes the choice with `resume new --template <id>`. The default is never accepted silently when the user has not been asked. `restyle` changes appearance only, preserving facts, market, persona, selection, and writing locale. Market/persona writing, page, photo, and fact-confirmation rules still apply, alongside each layout's capacity budgets and fixed main/sidebar regions. See the [template contract](template-contracts.md); bilingual coverage does not change review status or constitute design approval.

Build is **HTML only**. The template is sized to A4: open the HTML, choose A4 in the browser's print dialog, and save as PDF. The tool never writes PDF, DOCX, LaTeX, or image resumes.

## 9. Audit and diff

```bash
resume audit <slug>
resume diff <slug> <version> current
```

`audit` prints the HTML with headless Edge/Chrome, extracts the text, and checks:

- actual page count vs the application budget;
- section headings, selected bullets, section order, and outside-page text;
- body font floor, orphan headings, and bottom whitespace;
- clichés, bullet voice, CS fundamentals, locale markers;
- photo/sensitive fields, page size, and privacy.

It writes `qa.json`; hard failures exit `4`. `build` runs the same QA before declaring success.

Every rebuild snapshots the previous `application.yaml`, HTML, and reports under `.resume/applications/<slug>/versions/`. `diff` compares template, facts, bullets, sections, page budget, dropped reasons, and text-line counts.

## 10. Localize (EN ↔ ZH)

```bash
resume localize <slug> --to en --role "Backend Engineering Intern" --yes
resume localize <slug> --to zh --role "高级后端工程师" --yes
resume localize <slug> --to en --role "Backend Intern" --draft
```

This is transcreation, not translation:

- Re-selects facts and section order for the target market.
- CN moves education/experience per the CN profile; EN drops the photo/personal fields. No 求职意向 section is ever rendered.
- Missing target-language facts block the build (`exit 3`) with a gap list. `--draft` renders them as `[NEEDS EN]` / `[NEEDS ZH]` under a draft banner.
- Writes the target application, `resume.html`, editable HTML, and `parity.json`.
- Parity checks facts, bullet selections, normalized numbers (including 万→K), dates, entities, and links. Failures block a non-draft build (`exit 4`).

## 11. Privacy

Everything is local. `.resume/` is ignored by git. No network calls, no telemetry, no credentials.

Resume output is **HTML only**. PDF is a browser print action; the tool does not write DOCX, LaTeX, or image resumes.

## 12. Tests

```bash
python -m pytest
```

The suite covers vault validation, atomic save, merge/dedupe, evidence rules, intake branching and persistence, all gate transitions, and the CLI contract.
