# Writing Engine Reference

How the agent rewrites bullets, and what the linter will reject. The CLI stores the framework and runs the linter; the agent writes the sentence.

## 1. Framework consent

The user chooses one framework before any rewrite:

| ID | Shape | Best for |
|---|---|---|
| `star` | Situation → Task → Action → Result | Behavioral interviews, early career |
| `xyz` | Accomplished X, measured by Y, by doing Z | Engineering, data |
| `fab` | Feature → Advantage → Benefit | Product, design, customer-facing |
| `car` | Challenge → Action → Result | Cross-functional, problem-solving |
| `result_first` | Result → action detail | Experienced, dense resumes |
| `user_voice` | Keep the candidate's wording | Distinctive voice, creative |

The application stores `writing.framework` and `writing.consent: true`. A build without consent fails. Never apply a framework silently.

## 2. Before / after

Weak:
> Responsible for improving the onboarding flow and working with the team.

STAR:
> Onboarding dropped 60% of users at step 3; I redesigned it to a single screen after testing three variants, cutting drop-off to 22%.

XYZ:
> Cut onboarding drop-off from 60% to 22% by replacing the three-step flow with a single screen, validated on 3 variants.

FAB:
> Single-screen onboarding (feature) removes two decision points (advantage), so new users reach first value in under a minute (benefit).

Result first:
> Cut onboarding drop-off from 60% to 22% by rebuilding the flow as one screen and testing three variants.

The facts are identical. Only the order and emphasis change. Never add a number that is not in the vault.

## 3. Lint rules

### Global

| Code | Severity | Catches | Fix |
|---|---|---|---|
| `lint.weak_verb` | warn | worked on, responsible for, helped, 负责, 参与 | Lead with drove, cut, shipped, built |
| `lint.no_metric` | info | no number | Add a real number or keep a verifiable outcome |
| `lint.bullet_too_long` | warn | over 240 EN / 140 ZH chars | One action, one result |
| `lint.first_person` | warn | "I", "my", 我的, 本人 | Drop the pronoun |
| `lint.unsupported_superlative` | warn | best, world-class, 第一, 顶尖 | Replace with a result |
| `lint.placeholder_link` | warn | example.com, xxx, todo | Real link or remove |
| `lint.missing_education` | error | no education | Add it; never omit school |
| `lint.date_order` | error | end before start | Fix the dates |
| `lint.date_future` | warn | implausible future date | Confirm |
| `lint.page_count` | error/warn | estimate over max/target | Cut weak content; do not shrink below 9pt |
| `lint.skim_failed` | warn | 10-second skim misses signals | Move proof into the first screen |
| `lint.demo_only_project` | warn/error | project with no own change | Describe your change and outcome |

### Chinese market

| Code | Severity | Catches | Fix |
|---|---|---|---|
| `cn.cliche` | warn | 套话, 团队合作精神, 精通, passionate about | Replace with behavior and evidence |
| `cn.cliche_opening` | warn | 本人 / 作为一名 / 我是一名 at the start | Open with the strongest fact |
| `cn.ai_buzzword_density` | warn | AI terms overwhelm the fundamentals signal | Keep real AI skills; show CS fundamentals |
| `cn.cs_fundamentals_missing` | error | campus resume without OS/networks/data structures | Add and be ready to defend them |
| `cn.demo_only_project` | error | a reproduced demo with no own work | Rewrite or remove |
| `cn.flow_account` | warn | 负责/参与 duty lists with no result | What you owned, changed, achieved |
| `cn.structure_missing_education` | error | no education | Add school, degree, major, dates |
| `cn.page_count` | error/warn | 1–2 pages for students, 2–3 for 3+ years | Cut or rebalance |
| `cn.primacy` | warn | education not in the first screen | Move it up |
| `cn.weird_structure` | warn | duplicate sections | One section per purpose |
| `cn.dead_link` | warn | placeholder link | Real link or remove |
| `cn.self_evaluation` | warn | 自我评价 filler in the summary | Replace with evidence |

## 4. Evidence prompts

When a bullet has no support, ask one question, not a lecture:

- "What changed because of this — a number, a before/after, or a user outcome?"
- "What did you personally decide or build, as opposed to the team?"
- "Where can this be checked: a document, repo, dashboard, certificate, or link?"
- "If you don't have the number, what is the smallest true outcome you can state?"

If the answer is "just make something up", refuse and offer a smaller true detail. A gap is better than a fabrication.

## 5. Output format

The resume output is **HTML only**.

- The tool writes `resume.html` and a non-canonical editable HTML variant.
- PDF is produced by the user's browser print dialog; the tool never writes a PDF resume.
- No DOCX, LaTeX, or image export in v1.
- The vault remains the source of truth; browser edits are not merged back.
