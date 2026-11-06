---
name: resume-pro-skill
description: "Evidence-backed, China-first market-aware resume builder with international support. Trigger when the user wants to create, optimize, review, restyle, tailor, or translate a resume, compare a resume to a JD, or get job-fit recommendations. Supports students, interns, new grads, career switchers, experienced professionals, and primarily China's job market while also covering international applications. Produces self-contained A4 HTML."
---

# Resume Pro Skill

A resume is a **per-job selection over a verified career vault**, rendered through a **strict HTML template contract**. This skill handles the conversation and judgment; the CLI handles extraction, validation, linting, rendering, and QA.

The primary audience is **China's job market**; international applications are supported through `intl_en` and the English template variants. China-first positioning does not relax market or persona rules: always apply the target market's selection, writing, page, photo, and fact-confirmation rules.

## Runtime setup

- After the skill folder is imported, run `python bootstrap.py` once. It checks Python 3.10+, the six runtime dependencies, and every library template variant.
- Prefer `python bootstrap.py --install` to get the `resume` command. If pip cannot install packages, run `python bootstrap.py --deps-only` and call `python resume.py <command>` instead of `resume <command>`.
- Keep the imported folder on disk. The CLI reads `templates/`, `schema/`, and `profiles/` from it.
- Packaging: `python scripts/package_skill.py` builds a deterministic ZIP, excludes private material, and verifies the extracted copy before reporting `PASS`.
- If the check fails, report the concrete error and the documented fix; do not pretend the CLI is ready or fall back to writing a resume by hand.

## Non-negotiable rules

1. **Never invent facts.** No new company, title, project, metric, date, certificate, or responsibility. Every bullet must trace to an evidence id in the vault.
2. **Never one-shot a resume.** Guide intake, check sufficiency, ask targeted questions, and only then generate.
3. **Ask before applying a writing framework.** STAR, XYZ, FAB, CAR, result-first, and user voice require explicit consent. Store `writing.framework` and `writing.consent: true`.
4. **Markets are not translations.** Re-derive the CN or EN resume from the verified facts.
5. **HTML deliverable.** Write `resume.html` and a non-canonical editable HTML variant, framed at A4 (210 × 297 mm). PDF comes from the browser print dialog with A4 selected.
6. **Templates are a contract.** A failed template audit cannot be kept without an explicit override; a missing slot fails the build.
7. **Evidence beats adjectives.** Prefer a real number, scope, or verifiable outcome. If none exists, ask for a smaller true detail.
8. **Chinese-market rules.** Core skills, AI-related work, internships, and projects are the four campus signals. CS fundamentals are required for campus. Reject demo-only projects. Education is always included. Order by HR priority: students lead with education → experience → projects → skills; professionals lead with summary → experience → projects → education → skills. 1–2 pages for students/under 3 years; 2–3 for 3+ years.
9. **Respect the application mode.** Ask whether the resume is mainly for mass applications. If not, classify each experience/project by job family and ask for the preferred role. Use that role for ranking and the file name.
10. **Photo slot.** Every template reserves an optional portrait slot. When no photo is set, the slot is completely invisible.
11. **Language-matched variants.** Offer all five designs (`ats-classic`, `campus`, `modern-sidebar`, `editorial`, `executive`) in both resume languages: 10 variants. `templates/cn/` means Chinese (`language: zh`), `templates/en/` English (`language: en`). Render and QA using `writing.locale`, falling back to the market profile's `language`; a mismatched or missing variant fails. When calling `load_template(id, language=zh|en)`, specify the language for IDs that exist in both variants.

Default recommendations are `campus` / `modern-sidebar` for Chinese-market campus / professional profiles and `ats-classic` / `executive` for international default / senior profiles. Market/persona still govern selection, writing, page policy, photos, and fact confirmation. Respect each design's capacity budgets; bilingual availability does not change template review status.

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

A file means `optimize`, not `create`. "Review" means diagnose without rewriting. "Translate" means `localize`, not literal translation. If intent is ambiguous, ask one question using the protocol below.

## Mandatory continuous interaction

Apply this protocol to **every route** whenever missing facts, an unresolved preference, or user consent is needed: intake, extraction confirmation, evidence follow-ups, application mode, role, framework, template, photo, localization, and minimum-gate acceptance.

### Host tool requirement

- You **MUST call the host's interactive question tool** (`AskUserQuestion` or an available equivalent), wait for its answer, then resume the **same conversation and task**. This is mandatory, not a preferred presentation style. Use only tools actually exposed by the host and follow their schema and permission rules.
- You **MUST NOT end the task with a final-answer question**, a questionnaire, or "reply with your answers / say continue" as the normal handoff. Do not start a new chat, launch a separate task for each answer, or ask the user to restart the skill.
- Ask exactly one unresolved question per tool call, in the user's language; explain why it matters. Use facts and choices already supplied instead of asking again. Do not manufacture consent or add redundant approval steps.
- Preserve **free-text** input for names, dates, experience, projects, and explanations. With `AskUserQuestion`, use its built-in Other/custom-text input; if options are required, offer honest controls such as "Leave unanswered" and "Pause", not invented candidate facts. Map a deliberate leave-unanswered choice to a recorded gap, never to a successful answer. For consent, offer approve, edit/decline, or pause; never skip confirmation. For choices, map labels to valid CLI values; retain access to all values through custom input when the tool's option limit is smaller than the list.
- Treat empty/cancelled tool results as no answer, not consent or a skip. On explicit pause/stop, or dismissal without an answer, preserve saved state and stop questioning; do not repeatedly reopen the dialog. On a requested resume, read the saved question instead of resetting. A user's "I don't know" is an unknown, not permission to invent.
- If no suitable interactive tool is available or its use is denied, preserve state and report `interaction.tool_unavailable` as a **host capability limitation**, not a CLI error code. Do not silently substitute a final-message questionnaire, pretend to have shown a dialog, or bypass the restriction. Final responses are allowed for completion, explicit pause/cancellation, or a genuine blocker; never claim a paused or blocked resume is complete.

### Agent-driven loop

1. Load the existing vault and session in the same working directory. For creation, initialize only if needed and pass only known market/persona values. For optimization, ingest first and ask only about unresolved extracted facts; do not start the full new-resume interview.
2. Use `resume --json --lang <en|zh> intake` to obtain `question.id`, `kind`, `prompt`, `why`, `required`, `choices`, and `example`. Do not use a blocking terminal prompt (`resume intake` without `--json`) to collect answers inside an agent session. Standalone human CLI use remains supported.
3. When a question needs user input, call the interactive tool and wait. After the tool returns, submit the actual answer with `resume --json --lang <en|zh> intake --id <question-id> --answer <answer>`. Preserve free-text wording and safely quote it as a single argument; never interpolate raw user input as shell code. Use `--skip --id <question-id>` only for a deliberate leave-unanswered fact, or `--answer "不知道"` / `--answer "don't know"` for an explicit unknown. Neither is a supplied fact or consent; optional gaps may remain, but required gaps still need assessment. Never submit either for `confirm.summary`.
4. After a successful write, inspect the returned next `question` and continue the tool loop immediately. A CLI process exiting successfully is **not** the end of the agent task. On invalid input, explain the validation error and ask again for that field with the tool; do not reset the session or silently change the answer. CLI `quit` is a terminal-only control: intercept pause/stop in the agent, never save it as a fact.
5. Before `confirm.summary`, call `resume --json --lang <en|zh> intake --summary`, present the facts and evidence to review, and obtain confirmation through the tool. Apply scalar corrections with their original IDs, then reread saved facts. Collection handlers can append rather than replace: do not assume `--id` removes old skills, awards, or links. For a replacement, update only the identified canonical field with the user's correction, validate, and show the corrected facts before fresh confirmation. The summary call does not advance intake and may also report progress before pausing; accepted answers are already saved after each write.
6. When the payload says `complete: true`, read `intake --summary` and require `summary.confirmed: true` from actual user approval, then run `resume --json --lang <en|zh> check`. A passing gate or exhausted question list is not proof of consent; a previously skipped confirmation must be asked through the tool using `--id confirm.summary`. For fixable gaps, ask one targeted question through the same tool loop, persist the supplied facts, and recheck. Do not repeat already answered or deliberately unknown questions; if no answer can resolve the blocker now, explain it and pause without fabricating or delivering a final resume.
7. Continue in the same task through any still-needed framework/template decisions, writing, rendering, and QA. Ask for `minimum`-gate acceptance interactively before using `--yes`. End with the verified result, or an honest pause/blocker report; do not stop merely because intake ended. A review-only request still ends with diagnosis, not an unsolicited build.

For tool-input mappings, pause/resume behavior, and acceptance scenarios, see [Guided intake](docs/intake-and-sufficiency.md#13-continuous-agent-interaction).

## Route workflows

### Create from zero

```bash
resume init --market <id> --persona <id>
resume --json --lang <en|zh> intake
# Call the host's interactive question tool, wait, then submit its answer:
resume --json --lang <en|zh> intake --id <question-id> --answer <answer>
# Only if the user explicitly leaves this field unanswered:
resume --json --lang <en|zh> intake --skip --id <question-id>
# Repeat the tool loop until intake completes, then check:
resume --json --lang <en|zh> check
# List layouts in the resume language and where to preview them:
resume templates
resume new --role "<role>" --market <id> --persona <id> --framework <id> --template <id>
resume build <slug> --yes
resume photo portrait.jpg --app <slug>
```

- Ask exactly one question at a time; explain why.
- **Choose the template with the user before rendering.** After the gate passes, call the interactive tool to ask which layout to use. Present the five designs available in the resume's language (`resume templates`; each ID exists in both `cn`/`en`), recommend the market/persona default, and let the user pick another or keep the default. Tell the user where to view each design: open `templates/<cn|en>/<id>/preview.html` in a browser (the `preview` path is also in `resume templates --json`). Pass the chosen ID with `--template`; the default is used only after the user confirms it.
- If `check` exits `2`, read the targeted questions and ask one. Do not generate.
- `minimum` is a truthful but modest resume; confirm before building. `strong` can build.
- Never fill a gap with generic AI prose.

### Optimize an existing resume

```bash
resume review resume.pdf --market <id> --persona <id>
resume optimize resume.docx --market <id> --persona <id> --role "<role>"
resume optimize resume.docx --market <id> --persona <id> --keep-template
resume new --role "<role>" --market <id> --persona <id> --framework <id> --template <id>
resume build <slug> --yes
resume photo portrait.jpg --app <slug>
```

- Ingest first; never restart a from-scratch interview.
- Show the extraction report and ask the user to confirm missing/low-confidence fields.
- Audit the template. `excellent`/`good_with_fixes` can be kept; `replace`/`unmaintainable` gets a concrete reason and 2–3 library recommendations.
- When not keeping the original, ask the user to choose a library layout with the interactive tool before rendering, and show where to preview it (`templates/<cn|en>/<id>/preview.html`; `resume templates`), exactly as in Create from zero.
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

Change appearance only: preserve facts, market, persona, selection, and writing locale. Use `--app` to rebuild canonical HTML with the matching language variant; a file produces a learned-template preview. Do not use restyling to switch markets or reselect content.

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

- Re-derive from facts for the target market; keep the existing cross-market selection and writing workflow.
- Retain the source design ID by default and resolve its target-language variant; change the design only with an explicit `--template <id>`. A learned template without that language fails clearly.
- Missing target-language facts exit `3` with a gap list. `--draft` marks them `[NEEDS EN]`/`[NEEDS ZH]`; deliver only after the gaps are resolved.
- Parity failures block delivery. Review `parity.json` before the user sends anything.

### Recommend

```bash
resume recommend --app <slug>
```

Role families, fit tiers, missing terms, and a 2–4 week proof plan.

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

## Guardrails

- Every bullet traces to an evidence id; ask for missing facts instead of filling gaps.
- A thin profile goes through the gate and targeted questions before writing.
- Draft markers, parity failures, and hard QA failures stay internal until resolved.
- The public library contains original layouts informed by public guidance; learned user templates remain private.
- Deliver HTML; PDF comes from the browser print dialog with A4 selected.
