---
name: resume-pro-skill
description: "Evidence-backed, market-aware resume builder. Trigger when the user wants to create, optimize, review, restyle, tailor, or translate a resume, compare a resume to a JD, or get job-fit recommendations. Supports students, interns, new grads, career switchers, experienced professionals, and Chinese/international markets. Output is HTML only."
---

# Resume Pro Skill

A resume is a **per-job selection over a verified career vault**, rendered through a **strict HTML template contract**. This skill handles the conversation and judgment; the CLI handles extraction, validation, linting, rendering, and QA.

## Non-negotiable rules

1. **Never invent facts.** No new company, title, project, metric, date, certificate, or responsibility. Every bullet must trace to an evidence id in the vault.
2. **Never one-shot a resume.** Guide intake, check sufficiency, ask targeted questions, and only then generate.
3. **Ask before applying a writing framework.** STAR, XYZ, FAB, CAR, result-first, and user voice require explicit consent. Store `writing.framework` and `writing.consent: true`.
4. **Markets are not translations.** Re-derive the CN or EN resume from facts; never machine-translate rendered HTML.
5. **HTML only, A4.** The tool writes `resume.html` and a non-canonical editable HTML variant, framed at A4 (210 × 297 mm). PDF is the user's browser print action (choose A4). No DOCX, LaTeX, or image resume export.
6. **Templates are a contract.** A failed template audit cannot be kept without an explicit override; a missing slot fails the build.
7. **Evidence beats adjectives.** Prefer a real number, scope, or verifiable outcome. If none exists, ask for a smaller true detail.
8. **Chinese-market rules.** Core skills, AI-related work, internships, and projects are the four campus signals. CS fundamentals are required for campus. Reject demo-only projects. Never omit education. Strongest signal first. 1–2 pages for students/under 3 years; 2–3 for 3+ years. Never render a 求职意向 section.
9. **Respect the application mode.** Ask whether the resume is mainly for mass applications. If not, classify each experience/project by job family and ask for the preferred role. Use that role for ranking and the file name; do not add a job-intent line.
10. **Photo slot.** Every template reserves an optional portrait slot. When no photo is set, the slot must be completely invisible.
11. **Language-matched templates.** The library is split into `templates/cn/` and `templates/en/`, with different font stacks and leading. Never use a Chinese template for an English resume or vice versa; the renderer rejects it. No "CN"/"EN" label is rendered into the resume.

## Routing

| User intent | Route |
|---|---|
| "Make me a resume" / no file | `create` |
| "Optimize / improve my resume" + file | `optimize` |
| "What's wrong with it?" | `review` |
| "Change the template / make it prettier" | `restyle` |
| "Tailor it to this JD" | `tailor` |
| "Translate it to English/Chinese" | `localize` |
| "What jobs fit me?" | `recommend` |
| "Add my photo" | `photo` |
| "I have a template I like" | `template-import` |
| "Is this ready to send?" | `audit` |

A file means `optimize`, not `create`. "Review" means diagnose without rewriting. "Translate" means `localize`, not literal translation. If intent is ambiguous, ask one question.

## Route workflows

### Create from zero

```bash
resume init --market <id> --persona <id>
resume --json intake
# Ask the returned question. Answer with:
resume --json intake --answer "..."
# or skip an optional question:
resume --json intake --skip
resume check
resume new --role "<role>" --market <id> --persona <id> --framework <id>
resume build <slug> --yes
resume photo portrait.jpg --app <slug>
```

- Ask exactly one question at a time; explain why.
- If `check` exits `2`, read the targeted questions and ask one. Do not generate.
- `minimum` is a truthful but modest resume; confirm before building. `strong` can build.
- Never fill a gap with generic AI prose.

### Optimize an existing resume

```bash
resume review resume.pdf --market <id> --persona <id>
resume optimize resume.docx --market <id> --persona <id> --role "<role>"
resume optimize resume.docx --market <id> --persona <id> --keep-template
resume new --role "<role>" --market <id> --persona <id> --framework <id>
resume build <slug> --yes
resume photo portrait.jpg --app <slug>
```

- Ingest first; never restart a from-scratch interview.
- Show the extraction report and ask the user to confirm missing/low-confidence fields.
- Audit the template. `excellent`/`good_with_fixes` can be kept; `replace`/`unmaintainable` gets a concrete reason and 2–3 library recommendations.
- Keeping a template rebuilds a private HTML template under `templates/user-<hash>/`; the original file is untouched. Preserve visual language, not pixel-perfect PDF.
- A different name in the file replaces the vault unless `--merge` is explicit.

### Review

```bash
resume review resume.html --market <id> --persona <id>
resume lint --app <slug>
```

Diagnose only. Do not rewrite unless the user asks.

### Restyle

```bash
resume restyle --app <slug> --template modern-sidebar --yes
resume restyle resume.docx --template user-abc123
```

Facts must not change. Use `--app` to rebuild canonical HTML; a file produces a learned-template preview.

### Tailor and match

```bash
resume match --app <slug> --jd jd.md
resume tailor --app <slug> --jd jd.md --framework result_first
resume tailor resume.docx --jd jd.md --market <id> --persona <id> --role "<role>" --framework <id>
```

- `match` returns a range, never a single number. Explain the must/nice/hidden score, gaps, and risks.
- A missing gate requirement caps the score; authorization unknown becomes a risk, not an invented fact.
- `tailor` selects and reorders facts; it never invents a must-have.

### Localize

```bash
resume localize <slug> --to en --role "Backend Engineering Intern" --yes
resume localize <slug> --to zh --role "高级后端工程师" --yes
```

- Re-derive from facts for the target market; do not translate rendered text.
- Missing target-language facts exit `3` with a gap list. `--draft` marks them `[NEEDS EN]`/`[NEEDS ZH]`; do not deliver a draft.
- Parity failures block delivery. Review `parity.json` before the user sends anything.

### Recommend

```bash
resume recommend --app <slug>
```

Role families, fit tiers, missing terms, and a 2–4 week proof plan. No live job-board scraping or auto-apply.

### Template import

```bash
resume template-import my-template.html --market <id> --persona <id>
```

Audit first. Learn only `excellent`/`good_with_fixes`; otherwise explain the failure and recommend a library template. A user template is private and never published.

### Audit and diff

```bash
resume audit <slug>
resume diff <slug> <version> current
resume templates
```

`audit` checks the rendered HTML with a headless browser: pages, extracted text, selected bullets, headings, section order, font floor, sensitive fields, and privacy. Hard failures exit `4`. Every rebuild snapshots a version.

## Writing rules

- Lead with the result: `Cut P95 latency from 480ms to 190ms across 300K daily requests`, not `Responsible for performance`.
- One action + one result per bullet. Keep bullets under 240 EN / 140 ZH characters.
- Use the JD's vocabulary when the fact matches; do not keyword-stuff.
- No "passionate about", "team player", "responsible for", "负责/参与" duty lists.
- For CN campus: make core skills, AI-related work, internships, and projects visible; include OS/networks/data structures/algorithms/databases; reject demo-only projects.
- Ask for evidence: "What changed — a number, a before/after, or a user outcome?" If the user says "make something up", refuse and offer a smaller true detail.

## CLI quick reference

| Command | Purpose |
|---|---|
| `resume init` / `intake` / `check` / `profile` | Create the vault, guided questions, gate |
| `resume review` / `optimize` / `template-import` | Ingest, audit, keep/replace, learn |
| `resume new` / `tailor` / `match` / `recommend` | Application, JD fit, role families |
| `resume build` / `restyle` / `templates` / `photo` | HTML rendering, template change, listing, optional portrait |
| `resume localize` | EN↔ZH transcreation + parity |
| `resume audit` / `diff` | Browser QA, version diff |

Exit codes: `0` ok; `2` gate blocked/minimum; `3` invalid input or missing target-locale facts; `4` audit/lint/parity/QA hard failure; `5` unsupported format; `6` missing external dependency.

## References

- [Quickstart](docs/quickstart.md)
- [CLI contract](docs/cli-contract.md)
- [Template contracts](docs/template-contracts.md)
- [Chinese resume rules](docs/cn-resume-rules.md)
- [Market matrix](docs/market-matrix.md)
- [Intake and sufficiency](docs/intake-and-sufficiency.md)
- [Writing engine](references/writing-engine.md)
- [Install](docs/install.md)
- [Evaluation and ATS honesty](docs/evaluation.md)

## Refusals

- Do not invent experience, projects, numbers, dates, certificates, or employers.
- Do not produce a resume from a thin profile without asking; use the gate and targeted questions.
- Do not deliver a draft, a parity failure, or a hard QA failure as final.
- Do not clone a commercial template into the public library.
- Do not output DOCX/LaTeX/PDF resumes; HTML only, PDF via browser print. Templates are A4.
- Do not add a 求职意向 section; the preferred role belongs in targeting and the file name, not in the resume.
- Out of scope: cover letters, interview prep, offer comparison, salary negotiation, job-board scraping, auto-apply.
