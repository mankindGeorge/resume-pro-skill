# Guided Intake & Sufficiency Gate

> The resume generator must not start from a blank prompt or a single "generate my resume" request. It guides the candidate through a structured conversation, checks whether the collected facts are enough, asks targeted follow-ups, and only then generates and renders. This document defines that flow.

## 1. Principles

1. **One question at a time.** A long questionnaire gets abandoned. Ask, listen, follow up.
2. **Explain why.** Every question states what it unlocks: "This determines whether you pass the campus screen."
3. **Never fabricate.** If the user does not know a number, offer a proxy or mark it unknown. Never fill the gap with a plausible value.
4. **Show the fact summary.** Before writing, echo back every fact and every number for confirmation.
5. **Gate before generation.** If the facts are insufficient, keep asking or offer a clearly marked draft. Do not silently produce a generic resume.
6. **Data-backed by default.** Claims should have a source, a scope, or a verifiable outcome. If not, they are labeled.
7. **Sensitive fields are opt-in.** Ask only when the selected market profile requires them; mark them optional.

## 2. Intake stages

The conversation follows a fixed order, but it branches based on the persona.

```
0. Target        market, role, city, language, timeline
1. Identity      name, contact, links, photo (market-dependent)
2. Education     school, degree, major, dates, GPA/rank, courses
3. Experience    internships / full-time, newest first
4. Projects      academic, personal, open-source, competition
5. Skills        groups, proficiency, where used, CS fundamentals (CN campus tech)
6. Proof         awards, certificates, languages, publications, blog/portfolio
7. Preferences   page count, photo, framework, template, constraints
8. Confirm       fact summary + numbers + gaps
```

If the candidate is experienced, stages 3 and 4 swap emphasis: experience is primary, projects are optional. If the candidate is a student with no internship, stage 4 becomes primary and stage 3 is skipped.

## 3. Minimum viable fact set

The minimum set depends on the persona and market. The gate uses these defaults; profiles may tighten them.

### 3.1 Student, no internship

**Required**

- Name, email or phone, city, target role, target market.
- School, degree, major, start/end dates.
- At least **2 projects** (or 1 strong project + 1 competition/coursework/lab).
- At least **6 concrete skills**, with at least 3 used in a project.
- One campus/activity/volunteer item, if any.

**Preferred**

- GPA/rank if strong.
- Relevant coursework.
- Blog, GitHub, open-source, portfolio.
- Awards/competitions.

**Blocked if**

- No projects, no coursework, no competition, no campus activity, and no internship. → Switch to build mode.

### 3.2 Student with internship

**Required**

- Identity and target.
- Education.
- At least **1 internship** with company, role, dates, and **2 bullets**.
- At least **1 project** with name, role, tech, and **2 bullets**.
- At least **6 concrete skills**.

**Preferred**

- A second internship or a second project.
- Metrics for the internship.
- Blog/open-source.

### 3.3 New grad

Same as 3.2, plus:

- Graduation date.
- GPA/rank if strong.
- At least one full-time-convertible internship or a substantial project.

### 3.4 Experienced (3–9 years)

**Required**

- Identity and target.
- Education (school, degree, major, dates).
- At least **2 roles** with company, title, dates, and **3 bullets** each.
- At least **8 concrete skills**.

**Preferred**

- Scope/impact metrics for each role.
- Leadership/mentoring evidence.
- Selected projects.
- Certifications.

### 3.5 Senior / manager (10+)

**Required**

- Identity and target.
- At least **2 roles** with leadership scope.
- Team size, budget, revenue, or system scale for at least one role.
- Education.

**Preferred**

- Selected achievements, not exhaustive duties.
- Board/strategy/mentoring evidence.

### 3.6 Career switcher

**Required**

- Identity and target.
- Education.
- At least **2 transferable proof points** (project, freelance, open-source, internal transfer, course capstone).
- A clear bridge narrative.

### 3.7 Academic / creative

- Academic: publications, research, teaching, grants; multi-page.
- Creative: portfolio link, 2–3 selected projects with process and outcome.

## 4. Sufficiency model

Do not produce one opaque score. Produce a checklist with **blockers** and **warnings**.

### 4.1 Dimensions

| Dimension | What it checks | Example failure |
|---|---|---|
| Structural completeness | Required fields exist | Missing school or dates |
| Evidence density | Share of bullets with a source or verifiable outcome | All bullets are duties |
| Specificity | Named tools, scope, domain, ownership | "Developed a system" |
| Depth | Projects show own changes/optimization | "Reproduced a demo" |
| Differentiation | At least one proof point per section | Every bullet is generic |
| Market fit | CN CS fundamentals, EN no photo, page count | AI-only skills, photo in EN |
| Recency/relevance | Recent 3–5 years carry the strongest evidence | Only 10-year-old work |

### 4.2 Statuses

| Status | Meaning | Action |
|---|---|---|
| `blocked` | A required field or minimum set is missing | Ask targeted questions; do not render |
| `minimum` | Enough for a truthful but modest resume | Show warnings; ask "continue or add more?" |
| `strong` | All core dimensions pass | Proceed to optimization and render |

### 4.3 Output

`intake/report.json` + a short chat summary:

```json
{
  "status": "minimum",
  "persona": "student_with_internship",
  "market": "cn_internet",
  "blockers": [],
  "warnings": [
    {"field": "experience[0].metrics", "message": "No quantified result for the internship", "ask": "What changed after your work? Users, time, errors, revenue?"},
    {"field": "skills.fundamentals", "message": "Missing OS/networks/data structures", "ask": "Which of these courses can you defend in an interview?"}
  ],
  "evidence_coverage": 0.55,
  "specificity": 0.6
}
```

## 5. Evidence requirements

Some claims need data support. The intake engine must ask for it and record its status.

### 5.1 Evidence levels

| Level | Meaning | Can it be printed? |
|---|---|---|
| `verified` | A source exists: dashboard, report, public link, manager quote, deployment record | Yes |
| `user_asserted` | The user states it confidently; no artifact | Yes, flagged for interview prep |
| `estimated` | Order-of-magnitude or approximate | Only with explicit approval; label as approximate or avoid |
| `unknown` | Not known | No; ask for a proxy or omit |

### 5.2 What needs support

| Claim | Required support | Acceptable substitute |
|---|---|---|
| Percentage / money / time saved | Source or timeframe; baseline | Before/after, order of magnitude, "from X to Y" |
| Users / requests / scale | Count or range; timeframe | "thousands", "millions", team estimate |
| Team size / leadership | Number of people, duration | "led a 4-person squad for 6 months" |
| Project outcome | Shipped/deployed/adopted/reviewed | Public link, demo, release note |
| Skill proficiency | Where used, for how long | Project bullet or role context |
| Award / certificate | Name, issuer, date, level | Certificate ID or link |
| Education | School, degree, major, dates | Transcript or student status |
| Blog / open-source | Reachable URL, content | Repository stars/commits, article date |

### 5.3 Rules

- A metric without a source is allowed only as `user_asserted`, and the interviewer may ask about it. Flag it.
- Never convert `unknown` into a plausible number.
- Prefer exact numbers; if unavailable, use a verifiable qualitative outcome ("shipped to production", "adopted by 3 teams").
- Do not use competitor numbers, industry averages, or "约 30%" as the candidate's result.
- Unit conversions (万/亿, USD/CNY) must be exact and flagged.

## 6. Re-prompt logic

When the gate is `blocked` or `minimum`, ask targeted questions.

### 6.1 Rules

- One question per turn.
- Name the gap and why it matters.
- Offer 2–3 concrete examples or ranges.
- Accept "I don't know" and offer a proxy.
- Do not repeat a question the user already answered.
- If the user is fatigued, summarize the remaining gaps and offer `--draft`.

### 6.2 Question ladders

**Project**

1. What problem did it solve, and for whom?
2. What did you personally build or change?
3. What was the hardest part, and how did you solve it?
4. What was the result — shipped, used, faster, cheaper, more accurate?
5. Is there a number or before/after you can defend?

**Internship**

1. Which team, and what was the product?
2. What did you own end-to-end?
3. What did you ship or change?
4. What happened after it shipped?
5. Any number, scale, or recognition?

**Skills**

1. Which languages/frameworks/databases did you actually use?
2. In which project or role?
3. For campus tech: which CS fundamentals can you defend — OS, networks, data structures, algorithms, databases?
4. Any AI-related work you can show, not just name?

**Education**

1. School, degree, major, dates?
2. GPA/rank, if strong?
3. Relevant coursework for this role?

### 6.3 Handling "just make something up"

Refuse clearly and explain the interview risk: the interviewer will ask follow-up questions, and a fabricated metric is worse than no metric. Offer a qualitative substitute or a build plan.

## 7. Generation gate

```
resume build <application>
  → intake check
    → blocked: list missing fields, ask; exit 2
    → minimum: show warnings, ask "continue or add more?"; require confirmation
    → strong: proceed
  → optimization (framework consent, market rules, CN rules)
  → template selection
  → render HTML + editable
  → QA
```

### 7.1 Draft mode

`resume build --draft` may render a clearly marked draft when facts are incomplete:

- Placeholders use `[TO CONFIRM: ...]`, never plausible invented text.
- The page carries a visible "DRAFT — NOT FOR SUBMISSION" banner in the HTML (hidden in print only if the user explicitly asks).
- QA marks it `non-deliverable`.
- The draft is a conversation aid, not a resume.

### 7.2 No bypass

There is no "just generate it" path. The only exception is an explicit user request for a draft, and the draft is labeled.

## 8. Confirmation

Before writing, show:

- the structured fact summary;
- every number, separately, with its evidence level;
- the sections that will be included and their order;
- the gaps and what will happen to them;
- the chosen writing framework and template.

The user confirms or edits. Only then does the optimizer run.

## 9. Integration with optimization and templates

After the gate:

1. Apply the writing framework the user chose (`star | xyz | fab | result_first | car | user_voice`).
2. Apply the market rules (`intl_en`, `cn_internet`, `cn_soe`, etc.).
3. Apply the CN rules (four signals, CS fundamentals, project depth, page count, primacy).
4. Ask the user which layout to use (interactive tool), recommending the market/persona default and showing where to preview each design (`templates/<cn|en>/<id>/preview.html`; `resume templates`). Pass the chosen ID with `--template`; do not accept the default silently.
5. Render deterministically.
6. Run QA, including the 10-second skim.

## 10. Examples

### 10.1 Student, no internship, one project

The gate is `minimum` if the project is strong, plus coursework and skills. It asks for a second proof point; if none, it offers build mode with a 2–4 week plan. It does not invent a second project.

### 10.2 Student with an internship but no numbers

The gate is `minimum`. It asks: "What changed after your work — time saved, errors reduced, users reached, or something shipped?" If the user has no number, it uses "shipped to production and used by the team" as a verifiable qualitative result.

### 10.3 Experienced candidate with dates missing

The gate is `blocked` on dates. It asks for month/year for each role. It will not render a resume with guessed dates.

### 10.4 CN campus tech candidate with AI-only skills

The gate is `blocked` on CS fundamentals. It asks which of OS / networks / data structures / databases the candidate can defend. It will not accept "familiar with AI" as a substitute.

## 11. Anti-patterns

- Asking for everything in one message.
- Generating before the gate passes.
- Accepting vague claims because the user is in a hurry.
- Filling missing fields with generic AI text.
- Asking for sensitive fields by default.
- Treating a `user_asserted` metric as `verified`.
- Letting a draft look deliverable.

## 12. Application mode and role classification

Before asking for a target role, ask:

> "Is this resume mainly for mass applications? (海投)"

- **Yes — mass:** one broad version. No preferred role is required. The output file stays `resume.html`.
- **No — targeted:** for each experience and project, ask which job families it supports (`target_roles`), then ask which role the user prefers. Store:
  - `preferences.application_mode: targeted`
  - `preferences.preferred_role`
  - `experience[].target_roles` / `projects[].target_roles`

The preferred role is used for fact ranking, the application target, and the output file name (for example `resume-backend-engineer.html`). Use `--no-role-in-filename` if the user wants a plain `resume.html`.

The target role is a selection and naming device.

## 13. Continuous agent interaction

The [mandatory interaction protocol](../SKILL.md#mandatory-continuous-interaction) applies to every route, not only initial intake. The agent must use the host's interactive question tool (such as `AskUserQuestion`), wait for the response, and continue the same task. A final chat message asking the user to reply or say "continue" is not an acceptable substitute. Ask only for missing facts, unresolved preferences, or required consent; retain previous answers and do not add unnecessary confirmations.

The CLI remains a deterministic, short-lived state operation. Each successful answer/skip saves the vault and intake session and returns the next question. It cannot force a host to expose a dialog or keep an agent running; the skill instructions define that host-side requirement. If the required tool is unavailable or denied, report the capability limitation and preserve state rather than silently degrading to a questionnaire.

### 13.1 Map the actual tool result

| User interaction | Agent action |
|---|---|
| Selects a valid option | Map the display label to the CLI's allowed value and submit it with the original question ID |
| Enters free text | Preserve the text, including Chinese, punctuation, and multiple lines; pass it as one safely quoted argument |
| Tool only exposes choice buttons plus custom input | Use custom input for facts; neutral buttons may mean leave unanswered or pause, never sample names or invented achievements |
| Selects leave unanswered for a fact | Use `--skip --id <question-id>`; required fields retain blocker notes, which alone do not guarantee the gate fails |
| Says they do not know a fact | Submit an accepted unknown value such as `不知道`; do not invent a value or mark it verified |
| Needs to approve facts or a writing framework | Offer approve, edit/decline, or pause; do not offer skip as a way past consent |
| Requests pause/stop, or dismisses without answering | Do not submit any answer, skip, or confirmation; preserve state and stop asking |
| Provides an invalid answer | Explain the CLI error, retain saved answers, and use the interactive tool to correct that field |
| Corrects an earlier answer | Use its original `--id` for scalar fields and reread saved facts. Collection handlers may append; explicitly replace the identified field when requested, validate it, and obtain fresh confirmation |

For `AskUserQuestion`, custom input is supplied through the built-in Other path; do not add a duplicate Other option. Respect the actual tool's question and option limits. Do not turn free-form experience collection into a forced multiple-choice test. If no available input can represent the required answer, report the limitation instead of inventing one.

### 13.2 Save, resume, and finish

- Read the next question with `resume --json --lang <en|zh> intake` in the same working directory. Submit answers with `--id` so they apply to the question actually shown, not an assumed cursor.
- Do not run bare interactive `resume intake` through the agent's shell tool; that is the standalone human terminal workflow, not a chat question UI.
- Read `intake --summary` before fact confirmation. Display facts for review, then ask for confirmation using the interactive tool, not a final message. Treat corrections as real edits, not automatic consent.
- On pause, accepted answers already exist in `.resume/vault.yaml` and `.resume/intake-session.json`. A read-only summary can report progress; do not send `quit` as `--answer`, since JSON mode treats that as content rather than a terminal control. Do not use `--reset` to resume.
- `complete: true` only ends the intake question list. Independently require `summary.confirmed: true` from actual user approval before proceeding; neither question-list completion nor the gate result is a substitute for checking consent. If needed, show the summary and obtain approval through the tool with `--id confirm.summary`. Then run the sufficiency check and continue any remaining consent, writing, rendering, and QA steps within the same task. Do not ask "shall I continue?" merely because a command exited.
- A blocked gate cannot be bypassed by keeping the conversation alive. Resolve actionable gaps interactively; if the user cannot supply them, explain the blocker and pause. Explicit pause, cancellation, a real blocker, or the requested deliverable are valid stopping points.

### 13.3 Acceptance scenarios

| Scenario | Expected behavior |
|---|---|
| Three consecutive intake answers | Three sequential host-tool exchanges; each answer is saved, the next tool question opens without a user "continue" message |
| Known market/persona or previously answered identity | Reuse saved information; do not ask it again |
| A multiline Chinese project description | Custom text reaches the vault without replacement by option labels or shell execution |
| Invalid choice, then valid correction | The same field is corrected; other saved answers and the session survive |
| Pause, then resume | No fake answer is saved; intake resumes at the pending question |
| Final fact confirmation | The summary is shown before consent; completion proceeds to the sufficiency check rather than ending the agent task |
| Template/framework/localization clarification | The same interactive protocol is used outside intake |
| Choosing a layout before rendering | The agent asks which design to use through the tool, shows the six layouts in the resume language and each `templates/<cn\|en>/<id>/preview.html` path, recommends the default but lets the user change it, then passes `--template <id>` |
| Missing or denied host tool | Honest capability-blocker report, no simulated dialog or silent fallback |

Automated tests guard the instruction contract and exercise CLI state transitions with scripted answers. They do not prove a particular agent client displays dialogs or follows instructions; validate those behaviors in a host that exposes the tool.
