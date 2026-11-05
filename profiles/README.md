# Profiles

Profiles turn "write a good resume" into market- and persona-specific rules. They are data, not prose: the intake gate, selector, linter, renderer, and localizer all read them.

## 1. Markets

| File | Market | Status | Notes |
|---|---|---|---|
| `markets/intl_en.yaml` | International / English | stable | A4, no photo, 1 page default, 2 for 10+ years |
| `markets/cn_internet.yaml` | China internet / tech | stable | A4, photo optional, campus 1–2 pages, 3+ years 2–3 |
| `markets/cn_soe.yaml` | China SOE | experimental | Education, certificates, stability |
| `markets/cn_finance.yaml` | China finance | experimental | Certificates and school carry more weight |
| `markets/cn_creative.yaml` | China creative | experimental | Portfolio-first |
| `markets/hk_sg.yaml` | Hong Kong / Singapore | experimental | English-first, A4 |
| `markets/academic.yaml` | Academic CV | experimental | Multi-page, publications-first |

Fields:

| Field | Meaning |
|---|---|
| `page` | Page size and page-count limits by seniority |
| `photo_policy` | `forbidden`, `optional`, or `expected` |
| `personal_fields` | Fields the renderer may emit; everything else is suppressed |
| `section_order` | Section order per persona/seniority |
| `dates` | Date format and the word for "present" |
| `bullets` | Default framework, target/max bullets, metric policy |
| `ats` | Parseability constraints and standard headings |
| `signals` | What this market rewards and rejects |

## 2. Personas

| File | Persona | Status |
|---|---|---|
| `personas/student_with_projects.yaml` | Student, no internship, has projects | stable |
| `personas/student_with_internship.yaml` | Student with an internship | stable |
| `personas/new_grad.yaml` | New graduate | stable |
| `personas/experienced.yaml` | 3–9 years | stable |
| `personas/student_no_projects.yaml` | No internship, no projects | experimental (build mode) |
| `personas/career_switcher.yaml` | Career switcher | experimental |
| `personas/senior_manager.yaml` | 10+ years / manager | experimental |
| `personas/academic.yaml` | Academic | experimental |
| `personas/creative.yaml` | Designer / creative | experimental |

Fields:

| Field | Meaning |
|---|---|
| `minimum_facts` | What must exist before the gate can reach `minimum` |
| `required_signals` | The proof points the resume must show |
| `page_budget` | Page target per market |
| `question_ladders` | Ordered questions for each intake area |
| `prompt_rules` | Non-negotiable behavior for the intake agent |
| `build_mode` | When true, produce a proof plan instead of forcing a resume |

## 3. Stable vs experimental

- A `stable` profile has fixtures, tests, and a reviewed template pairing.
- An `experimental` profile may be used for exploration but the router must warn and must not claim optimization quality.
- Experimental profiles never silently fall back to a stable profile with different rules. The user chooses, or the route stops.

## 4. Page counts

- CN campus / under 3 years: 1–2 pages.
- CN 3+ years: 2–3 pages.
- International: 1 page under 10 years; 2 pages for senior or management.
- Academic CV: up to 4 pages; the one-page rule does not apply.

Page count is a budget, not a target to fill. A second page must earn its place.

## 5. Sensitive fields

`personal_fields.allowed` is the only source of truth for what may be emitted. A field present in the vault but absent from `allowed` is suppressed, not warned about, and never reaches HTML or logs. `id_number` is never emitted by any profile.

## 6. Adding a profile

1. Copy the closest existing profile.
2. Change `id`, `label`, and `status: experimental`.
3. Fill every field; do not leave silent defaults.
4. Add fixtures for three personas.
5. Add the template pairing.
6. Only then promote to `stable`.
