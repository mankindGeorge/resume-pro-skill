# Chinese Resume Rules (CN Market)

> Encodes the user's Chinese-market principles. These are hard rules for `cn_internet`, `cn_soe`, `cn_finance`, and `cn_creative` unless the user explicitly overrides them. They are **not** translations of international rules — they describe a different screening logic.

## 1. Core competitiveness

A Chinese resume is screened for four signals, in this order of importance:

1. **Core skills** — the concrete stack, tools, and domain knowledge the role needs.
2. **AI-related ability** — applied AI experience where relevant, not a pile of AI buzzwords.
3. **Internship experience** — real internships, especially at recognized companies.
4. **Projects** — real projects with the candidate's own changes, optimization, and thinking.

Education is not optional. It is a required structural field and a primary filter for campus recruiting.

### 1.1 Order by strength, not by template

Put the strongest signal first. If the candidate's internship is stronger than their projects, internship comes first; if projects are stronger, projects come first; if the skill stack is the strongest signal, a compact core-skills block goes near the top.

This is the **primacy effect**: the first screen decides whether the rest is read. Put key information early and put weaker or less relevant information later.

## 2. Self-presentation

- Treat the candidate as an ordinary person with real strengths. Do not wait for the interviewer to discover them.
- Show highlights explicitly: a concrete result, a named system, a measurable improvement, a real ownership boundary.
- Do not write a hero narrative. Write evidence.

## 3. Absolute don'ts

### 3.1 Never generate a whole resume in one shot

- No one-click, full-document generation with generic prose.
- Interviewers recognize AI boilerplate immediately; it makes every candidate look the same.
- The workflow must be interactive: collect facts, show the selection, ask before rewriting, show before/after.

### 3.2 Never fill skills with AI buzzwords while omitting CS fundamentals

- A campus tech resume that lists only AI tool names and frameworks, without operating systems, computer networks, data structures and algorithms, or databases, fails written tests and looks shallow.
- For campus/tech roles, the skills section must show at least three of: operating systems, computer networks, data structures and algorithms, databases, programming languages.
- AI-related skills are a plus, not a substitute for fundamentals.

### 3.3 Never write demo-only projects

- "Reproduced a tutorial", "cloned a demo", "followed a course" is not a project.
- Every project must show at least one of: the candidate's own changes, an optimization, a re-architecture, a performance improvement, a new feature, a real user/deployment, a bug they diagnosed, or a design trade-off they made.
- The interviewer will ask "what did you change?" — the resume must already answer it.

## 4. Page count

| Candidate | Pages |
|---|---|
| Student / fresh grad / < 3 years | 1–2 pages |
| 3+ years | 2–3 pages |

Do not compress a strong 2-page campus resume into an unreadable one-pager. Do not let a 3-year candidate sprawl to 4 pages. Page count is a guideline tied to evidence volume, not a hard aesthetic.

## 5. Common pitfalls

- **Beautify moderately; never fabricate.** Honesty first. Every metric must be verified or marked unknown.
- **No flow accounts.** Do not list duties. Write what the candidate owned and what they shipped.
- **No weird structure.** Use standard section headings and a conventional order. HR systems parse resumes automatically; a strange layout causes manual re-checking.
- **Never omit school or education.** Missing school/degree/major/dates is a common and costly mistake. It breaks automated intake and forces back-and-forth.
- **Put key information early; put weaker information later.** See primacy effect above.
- **Include dates for every entry.** Mixed or missing dates cause parser errors.
- **Do not hide core text in images, tables, or text boxes.**

## 6. How campus interviewers read a resume

1. **Skim in seconds** (roughly 10 seconds) looking for a highlight.
2. If a highlight is found, read in detail.
3. Look for: core skills, AI-related ability, real enterprise projects, real internships.
4. If there is a blog or open-source link, open it and judge whether the content has value.

Implication: the first screen must contain at least two of the four signals, and blog/open-source links must be real, current, and relevant. A dead link is worse than no link.

## 7. Implementation mapping

### 7.1 Profile fields (`cn_internet`)

```yaml
market: cn_internet
language: zh
page:
  student_or_under_3y: [1, 2]
  over_3y: [2, 3]
section_order:
  default: [header, intent, education, core_skills, internships, projects, campus, honors, self_evaluation]
  order_by_strength: true
required_fields: [name, phone, email, city, target_role, school, degree, major, education_dates]
signal_priority: [core_skills, ai_related, internships, projects, blog_or_open_source]
skills_require_cs_fundamentals_for_campus_tech: true
project_depth_required: true
```

### 7.2 Lint rules

| Rule id | Check | Severity |
|---|---|---|
| `cn.cliche` | Generic phrases such as "具备良好的沟通能力", "学习能力强", "熟练掌握", "有较强的团队合作精神", "对…有浓厚兴趣" without evidence | error if ≥ 2 |
| `cn.ai_buzzword_density` | AI terms dominate the skills section while CS fundamentals are absent | error |
| `cn.cs_fundamentals_missing` | Campus tech role missing ≥ 3 of OS / networks / data structures / algorithms / databases | error |
| `cn.demo_only_project` | Project bullets contain only reproduction/tutorial language and no change/optimization/decision | error |
| `cn.flow_account` | Bullets are duty lists without ownership or result | warning |
| `cn.structure_missing_education` | School, degree, major, or dates missing | error |
| `cn.page_count` | Outside 1–2 pages (<3 years) or 2–3 pages (3+) | error |
| `cn.primacy` | Top third of the page lacks at least two of the four core signals | warning |
| `cn.weird_structure` | Non-standard headings or unconventional order | warning |
| `cn.dead_link` | Blog/open-source link is unreachable or empty | warning |
| `cn.cliche_opening` | "本人…", "作为一名…", "我是一名…" openings | warning |

### 7.3 Interview additions

Ask these during intake, one at a time:

1. "你希望我用哪种写法？STAR / XYZ / 结果前置（FAB）/ 保留你的原话只做轻修？" — explain the trade-offs, never choose silently.
2. For campus tech: "除了 AI 工具，操作系统、计算机网络、数据结构、数据库这几门你哪些能写？"
3. For every project: "除了复现，你自己改了什么、优化了什么、踩了什么坑、最后怎么解决的？"
4. "有没有技术博客、GitHub、开源贡献？链接给我，我会检查是否可访问。"

### 7.4 QA: 10-second skim

Extract the top screen of the rendered resume and verify:

- name and contact are visible;
- school/degree/major are visible;
- at least two of: core skills, AI-related, internship, project;
- at least one concrete proof point (number, named system, or shipped result);
- no cliché opening.

If the skim fails, the resume is not deliverable even if every other check passes.

## 8. Writing framework consent

Before any optimization, ask which framework the user wants:

| Framework | Best for | Risk |
|---|---|---|
| **STAR** | Behavioral, consulting, PM, campus interviews | Easily becomes 4 long sentences |
| **XYZ** | International tech, quantified impact | Needs verified metrics |
| **FAB** | Chinese internet, product/marketing | Can sound like a sales pitch |
| **Result-first** | Chinese tech, experienced hires | Can omit context |
| **Keep the user's voice** | Users who dislike formulaic writing | Less consistent |

Default suggestions: `intl_en` tech → XYZ; `cn_internet` campus → result-first + FAB; `cn_internet` experienced → result-first; consulting/PM → STAR or CAR. The choice is stored as `writing.framework` with `writing.consent: true`. The linter must not apply a framework the user did not approve.
