# Schema

Three files define the data model. Everything else — intake, selection, rendering, linting, localization — reads and writes these shapes.

| File | Owns | Never does |
|---|---|---|
| `vault.schema.json` | Durable facts, per-locale phrasing, evidence registry | Select or order facts for a job |
| `application.schema.json` | Per-job selection, template choice, writing consent, output pointers | Store new facts |
| `template.schema.json` | Renderer ↔ template contract, slots, budgets, print rules | Hold content |

Worked examples live in [`examples/`](examples/):

- [`vault-student.yaml`](examples/vault-student.yaml) — student with one internship and one project.
- [`vault-experienced.yaml`](examples/vault-experienced.yaml) — 6 years, two roles, mixed evidence.
- [`vault-incomplete.yaml`](examples/vault-incomplete.yaml) — collecting state with a blocker.
- [`application.yaml`](examples/application.yaml) — CN internet campus application.
- [`template-ats-classic.yaml`](examples/template-ats-classic.yaml) — a valid manifest.

Validate them:

```bash
python - <<'PY'
import json, yaml
from jsonschema import Draft202012Validator
pairs = [
    ("vault", "schema/examples/vault-student.yaml"),
    ("application", "schema/examples/application.yaml"),
    ("template", "schema/examples/template-ats-classic.yaml"),
]
for kind, path in pairs:
    schema = json.load(open(f"schema/{kind}.schema.json"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(yaml.safe_load(open(path)))
    print("ok", path)
PY
```

## 1. Core rules

### 1.1 One fact, two locales

`localizedText` and `localizedList` hold `en` and `zh` separately. They are authored or approved per locale, never machine-translated at render time.

```yaml
text:
  zh: "将 P95 延迟从 480ms 降至 190ms"
  en: "Cut P95 latency from 480ms to 190ms"
```

If a locale is missing, the renderer asks for it. It does not translate.

### 1.2 Every bullet has evidence

A bullet requires at least one `ev_*` id:

```yaml
bullets:
  - id: bul_exp_001
    text: { zh: "...", en: "..." }
    evidence: [ev_intern_perf]
```

The evidence entry carries the strength:

| Status | May render as a hard fact? | May render a number? |
|---|---|---|
| `verified` | Yes | Yes |
| `user_asserted` | Yes, as the candidate's claim | Yes, if the number came from the user |
| `estimated` | Never as fact | Never |
| `unknown` | Never | Never |

`source: inference` is for internal reasoning only. It must never reach a rendered bullet.

### 1.3 IDs are stable and typed

| Prefix | Object |
|---|---|
| `edu_` | education |
| `exp_` | experience |
| `proj_` | project |
| `skl_` | skill group |
| `awd_` | award |
| `cert_` | certificate |
| `lang_` | language |
| `pub_` | publication |
| `bul_` | bullet |
| `ev_` | evidence |

IDs survive edits. A new role gets a new id; an edited title keeps its id.

### 1.4 Sensitive fields are data, not output

`identity.personal` may contain date of birth, gender, marital status, nationality, political status, and ID number. These are stored locally and never rendered unless the market profile explicitly allows the field. `id_number` must never be rendered or logged.

### 1.5 Dates

`YYYY-MM` or `present`. No free-text dates. This is what makes date-consistency checks possible.

### 1.6 Template language

Every template manifest declares `language: zh | en`. Rendering and QA resolve the variant from the application's `writing.locale`, falling back to the target market profile's `language` only when it is absent; a missing or mismatched variant fails explicitly (`render.template_missing` / `render.language_mismatch`). The `templates/cn/` and `templates/en/` folders denote resume language, not market eligibility. Chinese templates use CJK-first font stacks; English templates use Latin-only stacks. This keeps font metrics and line spacing coherent.

## 2. Application invariants

JSON Schema checks shape. These invariants are checked at runtime:

1. `vault_fingerprint` matches the vault file used for the build.
2. Every `fact_ids`, `bullet_ids`, `summary_evidence`, and bullet `evidence` reference exists.
3. A `summary` has at least one `summary_evidence` entry.
4. `writing.consent` is `true`; the framework is one of the six registered values.
5. `page_budget.target <= page_budget.max`.
6. A `user_learned` template exists under `templates/user-<hash>/` and is never published.
7. A failing template audit cannot be kept without a matching `overrides[]` entry.
8. `output.draft: true` forces a visible "DRAFT — NOT FOR SUBMISSION" label.

## 3. Slot naming

Template slots use dotted names:

```
identity.name
identity.contact
identity.links
identity.photo   # optional; slot collapses when empty
section.summary
section.education
section.experience
section.projects
section.skills
section.awards
section.certificates
section.languages
section.publications
section.open_source
experience.item
experience.item.company
experience.item.title
experience.item.dates
experience.item.bullet
project.item
project.item.name
project.item.bullet
education.item
education.item.school
education.item.degree
```

Rules:

- A section slot is `section.<id>` and must match a section id in `application.selection.sections`.
- A repeated entry is `<section>.item`; its fields are `<section>.item.<field>`.
- A bullet slot is `<section>.item.bullet` and is repeatable.
- Missing required slot = render error. Missing optional slot = the slot collapses, with no empty border or label left behind.
- A template must never contain business logic or content. It contains slots, structure, and CSS.

## 4. Template budgets

Defaults, overridable per template within the schema limits:

| Item | EN | ZH |
|---|---|---|
| Summary | 240 chars | 120 chars |
| Bullets per role | 3–5 | 3–5 |
| Bullets per project | 2–4 | 2–4 |
| Skills shown | 8–16 | 6–12 |
| Roles | 1–5 | 1–5 |

A template cannot raise `max_*` above the schema limit. Page count is enforced by the renderer and QA, not by the template author.

## 5. Validation layers

1. **Syntax** — JSON/YAML parses.
2. **Schema** — `jsonschema` Draft 2020-12.
3. **Referential integrity** — ids exist, bullets have evidence, fingerprints match.
4. **Sufficiency** — the gate decides `blocked | minimum | strong`.
5. **Lint** — content rules, including CN rules.
6. **Render** — required slots present, budgets respected.
7. **QA** — parseability, page count, overflow, privacy.

A later layer never compensates for an earlier failure. If the vault does not validate, intake does not proceed to sufficiency.

## 6. Versioning

`schema_version` is a string major.minor. A major change requires a migration in `vault.py`; a minor change is additive. Unknown versions fail with a clear message and never load silently.
