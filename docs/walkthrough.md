# Walkthrough

Fictional data only. Do not put real contact details in a public example.

## 1. Create from zero (CN campus)

```bash
mkdir demo && cd demo
resume init --market cn_internet --persona student_with_internship
resume --json intake
# answer one question at a time; first tell it whether this is a mass application
resume --json intake --answer "后端开发工程师（校招）"
resume --json intake --answer "Example University"
# ...
resume check
resume new --role "后端开发工程师（校招）" --market cn_internet \
  --persona student_with_internship --framework result_first
resume build <slug> --yes
resume audit <slug>
resume photo portrait.jpg --app <slug>   # optional; invisible when empty
```

What good looks like:

- `check` is `STRONG` or a confirmed `MINIMUM`; a `BLOCKED` gate asks one targeted question.
- The `campus` template is A4, 1–2 pages, education early; no 求职意向 section.
- `audit` passes with no hard failures; warnings are readable.
- `resume.html` is canonical; `resume-editable.html` is a non-canonical preview.

## 2. Optimize an existing resume

```bash
mkdir demo && cd demo
resume init --market intl_en --persona experienced
resume review my-resume.pdf --market intl_en --persona experienced
resume optimize my-resume.docx --market intl_en --persona experienced --role "Senior Backend Engineer"
```

- `review` never writes the vault.
- `optimize` extracts, audits the template, and reports missing fields.
- If the audit says `replace` or `unmaintainable`, use a library template:
  `--template ats-classic` or `--template modern-sidebar`.
- If the audit says `excellent`/`good_with_fixes`, keep it:
  `resume optimize my-resume.docx ... --keep-template`.
  The original file is unchanged; a private HTML template appears under `templates/user-<hash>/`.

Then:

```bash
resume new --role "Senior Backend Engineer" --market intl_en \
  --persona experienced --framework result_first --template ats-classic
resume lint --app <slug>
resume build <slug> --yes
resume audit <slug>
resume photo portrait.jpg --app <slug>   # optional; invisible when empty
```

## 3. Tailor to one JD

```bash
resume match --app <slug> --jd jd.md
resume tailor --app <slug> --jd jd.md --framework result_first
resume build <slug> --yes
resume audit <slug>
resume photo portrait.jpg --app <slug>   # optional; invisible when empty
```

- The match report is a range. A missing gate requirement caps it.
- Gaps are classified `fixable` / `hard` / `not_important`; risks are separate.
- `tailor` selects and reorders facts; it never invents a must-have.

## 4. Localize

```bash
resume localize <slug> --to en --role "Backend Engineering Intern" --yes
resume localize <slug> --to zh --role "高级后端工程师" --yes
```

- The target market gets its own section order, page budget, and template.
- Missing target-language facts block with a gap list; `--draft` marks them.
- `parity.json` compares facts, numbers (万→K normalized), dates, entities, and links.
- A parity failure or QA hard failure is not deliverable.

## 5. A deliberately failing example

```bash
mkdir blocked && cd blocked
resume init --market cn_internet --persona student_with_internship
cp path/to/schema/examples/vault-incomplete.yaml .resume/vault.yaml
resume check
# exit 2: education fields, projects, skills, and CS fundamentals are missing
resume build <slug> --yes
# still exit 2: the gate blocks before rendering
```

The gate should ask one targeted question at a time; it must not generate a resume from a thin profile.

## 6. Using the example vaults

The `schema/examples/` vaults are fictional and safe:

- `vault-student.yaml` — one internship, one project, bilingual.
- `vault-student-projects.yaml` — two projects, no internship, bilingual.
- `vault-experienced.yaml` — two roles, six years, bilingual.
- `vault-incomplete.yaml` — deliberately blocked.

To use one:

```bash
resume init --market cn_internet --persona student_with_internship
cp schema/examples/vault-student.yaml .resume/vault.yaml
resume check
```

The example application and template manifest are in the same folder for schema reference.
