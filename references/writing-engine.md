# Writing Engine: Frameworks and Content Packaging

How the agent collects, packages, and rewrites bullets, and what the linter will reject. The CLI stores the framework and runs the linter; the agent writes the sentence. Frameworks and packaging live together in this document: **every framework has its own packaging recipe** — packaging is never tied to one framework.

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

## 2. Packaging under each framework

Packaging is the same job in every shape: rewrite raw facts into 「问题—决策—影响」, answering background, the user's role, action, and result — never a paraphrase of what the user said. The framework decides the order, the labels, and which slots to collect. Apply the recipe of the chosen framework; do not default to one framework's shape.

### STAR — `star`

- Collect: situation, task, action, result.
- Labeled points: `项目背景：`（S）, `核心框架：`（T）, `解决方案：`（A，或 `难点：`）, `核心成果：`（R）.
- Package: background states the problem and constraint; the framework point states the technical route and why it was chosen; the solution explains the pain point and why the approach fits it; the result states what problem was solved and what changed.

### XYZ — `xyz`

- Collect: the accomplished X, the measure Y, the doing Z.
- Labeled points: `核心成果：`（X）, `衡量口径：`（Y）, `实现做法：`（Z）.
- Package: lead with the concrete outcome, attach the number or scope that proves it, then the personal action that caused it. When the measure is missing, follow the data fallback in the content-sufficiency rules: ask the user first.

### FAB — `fab`

- Collect: the feature built, its advantage over the obvious alternative, the benefit created.
- Labeled points: `核心能力：`（F）, `技术优势：`（A）, `实际收益：`（B）.
- Package: name what was built, explain why it beats the alternative, and end with what changed for the user or the business.

### CAR — `car`

- Collect: challenge, action, result.
- Labeled points: `难点：`（C）, `解决方案：`（A）, `核心成果：`（R）.
- Package: lead with the hardest constraint, describe the decision that answered it, and close with the measurable change.

### Result first — `result_first`

- Collect: the result first, then the action detail and context needed to believe it.
- Labeled points: `核心成果：` first, then `解决方案：`（关键做法）, `项目背景：` last and brief.
- Package: put the result in the first clause; keep only the action detail that makes it credible; cut background that the result already proves.

### User voice — `user_voice`

- Collect: the user's own wording and what it proves.
- Labeled points: keep the user's own labels and order.
- Package: tighten the wording without replacing the voice; data and evidence rules still apply.

Shared rules for every recipe:

- Each point is a complete, substantial sentence with real detail; never a one-line fragment.
- Every rendered line of a project or experience intro must fill at least 2/5 of the printable width. When a wrap would leave only a few characters alone on a line, expand the sentence with real detail (preferred) or tighten the wording so the line fills or merges; never deliver a one- or two-character line.
- A result point must say what problem was solved and what changed, not just list an award or repeat the technology. A solution point must explain the pain point and why the approach fits it. Remove filler such as launch dates unless they prove impact.
- Data fallback order: ask for the real value → ask permission to estimate → propose candidate values → the user confirms → write.
- All points render as labeled paragraphs or plain lines — never `<ul>`, `<ol>`, or `<li>`, and no dot before the text. The leading label (for example `项目背景：` or `Background:`) renders bold so the point structure is visible at a glance.

## 3. Before / after

Weak:
> Responsible for improving the onboarding flow and working with the team.

STAR:
> Onboarding dropped 60% of users at step 3; I redesigned it to a single screen after testing three variants, cutting drop-off to 22%.

XYZ:
> Cut onboarding drop-off from 60% to 22% by replacing the three-step flow with a single screen, validated on 3 variants.

FAB:
> Single-screen onboarding (feature) removes two decision points (advantage), so new users reach first value in under a minute (benefit).

CAR:
> A three-step onboarding lost 60% of users at step 3; I rebuilt it as a single screen after testing three variants, cutting drop-off to 22%.

Result first:
> Cut onboarding drop-off from 60% to 22% by rebuilding the flow as one screen and testing three variants.

The facts are identical. Only the order and emphasis change. Never add a number that is not in the vault.

## 4. Lint rules

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

## 5. Evidence prompts

When a bullet has no support, ask one question, not a lecture:

- "What changed because of this — a number, a before/after, or a user outcome?"
- "What did you personally decide or build, as opposed to the team?"
- "Where can this be checked: a document, repo, dashboard, certificate, or link?"
- "If you don't have the number, what is the smallest true outcome you can state?"

If the answer is "just make something up", refuse and offer a smaller true detail. A gap is better than a fabrication.

## 6. Output format

The resume output is **HTML only**.

- The tool writes `resume.html` and a non-canonical editable HTML variant.
- PDF is produced by the user's browser print dialog.
- Output is self-contained HTML; PDF comes from the browser print dialog.
- The vault remains the source of truth; browser edits are not merged back.
