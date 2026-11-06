# CLI Contract

The CLI is the deterministic half of the product. The agent handles conversation and judgment; the CLI handles extraction, validation, linting, rendering, and QA. Every command must be runnable without an LLM.

## 1. Global conventions

```
resume <command> [options]
```

| Convention | Rule |
|---|---|
| Working directory | The nearest ancestor containing `.resume/`; override with `--cwd`. |
| Vault | `.resume/vault.yaml` by default. |
| Applications | `.resume/applications/<slug>/`. |
| Config | `.resume/config.yaml`. |
| Locale | `--lang en|zh` affects messages only, never content. |
| JSON | `--json` writes machine output to stdout and nothing else. Logs go to stderr. |
| Colors | `--no-color` forces plain text. Auto-disabled when not a TTY. |
| Network | No command performs network access in v1. |
| Secrets | No credentials, tokens, or cookies are read or stored. |
| Determinism | Same vault + same application + same template → identical HTML bytes. |
| Output format | Resume output is self-contained HTML; PDF comes from the browser print dialog. |
| Overwrite | Commands never overwrite an existing artifact without `--force`; versions are moved to `versions/`. |

## 2. Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. |
| `2` | Sufficiency `blocked`. Nothing was generated. |
| `3` | Invalid input or schema validation failure. |
| `4` | Audit or QA hard failure. Artifact exists but is not deliverable. |
| `5` | Unsupported file format, or a scanned/image-only file that cannot be read. |
| `6` | Missing external dependency (for example LibreOffice for `.doc`). |
| `7` | Internal error. A report path is printed. |

## 3. Commands

### 3.1 Create

```
resume init [--market <id>] [--persona <id>] [--json]
resume intake [--json] [--answer TEXT] [--id QUESTION_ID] [--skip]
               [--summary] [--reset]
resume check [--draft] [--json]
resume profile [--json]
resume photo <image> [--app <slug>] [--clear] [--json]
```

| Command | Behavior |
|---|---|
| `init` | Creates `.resume/` and an empty vault with `status: collecting`. Idempotent. `--market`/`--persona` pre-answer the first two questions. |
| `intake` | Runs the guided state machine. One question at a time. With no flags, interactive. With `--json`, prints the current question; `--answer`/`--skip` records an answer and prints the next. `--id` corrects a specific question. `--summary` prints collected facts and the gate. `--reset` clears the session, not the vault. |
| `check` | Runs the sufficiency gate. Exit `2` when blocked; writes `.resume/sufficiency.json` and prints the report path. `--draft` marks the report non-deliverable. |
| `profile` | Prints the current vault summary and missing dimensions. Never invents. |
| `photo` | Copies a JPEG/PNG/WebP portrait into `.resume/assets/` and stores `identity.photo`. Every template reserves the slot; it is invisible when empty. `intl_en` suppresses photos by policy. `--clear` removes it. |

`intake` state lives in `.resume/intake-session.json`: answers, skips, branch flags, generated artifact ids, and the confirmation note. Re-answering any non-confirm question reopens the vault. The intake asks whether the resume is mainly for mass applications; if not, it asks for target roles per experience/project and a preferred role.

### 3.2 Optimize an existing resume

```
resume optimize <file> [--market <id>] [--persona <id>] [--role <role>]
                       [--keep-template] [--template <id>] [--override <reason>]
                       [--merge] [--force] [--json]
resume review <file> [--market <id>] [--persona <id>] [--json]
resume restyle <file> --template <id> [--market <id>] [--persona <id>] [--json]
resume template-import <file> [--market <id>] [--persona <id>] [--force] [--json]
```

| Command | Behavior |
|---|---|
| `optimize` | Ingest → extraction report → template audit → merge facts → keep/replace decision. Writes `.resume/imports/<timestamp>-<slug>/`. If the existing vault belongs to a different name, it is replaced unless `--merge` is explicit. The vault is not written when a requested keep is refused. |
| `review` | Diagnostic report only. Writes `.resume/reviews/<timestamp>-<slug>/review.json`; never writes the vault or the source file. Exit `4` when the verdict is `replace` or `unmaintainable`. |
| `restyle` | Appearance only: preserve facts, market, persona, selection, and writing locale. `--app` updates the template and rebuilds HTML with its matching language variant; a file produces `.resume/restyles/<timestamp>-<slug>/preview.html` for a learned template. Never switch markets or reselect facts to make a design fit. |
| `template-import` | Audit a user template; learn it only when the verdict is `excellent` or `good_with_fixes`. Writes `.resume/template-imports/<timestamp>-<slug>/` and `templates/user-<hash>/`. |

Market and persona are required; they come from the flags or `.resume/intake-session.json`. A missing target exits `3` with `ingest.target_missing`.

`--keep-template` without an `excellent` / `good_with_fixes` verdict fails with exit `4` and prints the failing dimensions. `--override <reason>` records an explicit exception in `template-decision.json` and allows the private rebuild.

Supported inputs: DOCX, text-based PDF, HTML, MD, TXT. DOC/RTF require LibreOffice (exit `6` when missing). Scanned/image-only PDFs are detected and refused.

### 3.3 Target

```
resume new [--role <role>] --market <id> --persona <id> --framework <id>
            [--company] [--template <id>] [--slug] [--jd <file>]
            [--no-role-in-filename] [--json]
resume lint [--app <slug>] [--market <id>] [--persona <id>] [--json]
resume match --jd <jd.md> [--app <slug>] [--market <id>] [--persona <id>] [--json]
resume tailor <file|--app <slug>> --jd <jd.md> [--framework <id>]
              [--market <id>] [--persona <id>] [--role <role>]
              [--template <id>] [--slug] [--no-role-in-filename]
              [--merge] [--json]
resume recommend [--app <slug>] [--market <id>] [--persona <id>] [--json]
```

| Command | Behavior |
|---|---|
| `new` | Selects facts and creates `.resume/applications/<slug>/application.yaml`. `--role` falls back to the vault's preferred role. `--framework` is required and stored as `writing.consent: true`; no render. Targeted applications name the HTML after the role (for example `resume-backend-engineer.html`); mass applications use `resume.html`; `--no-role-in-filename` forces the plain name. |
| `lint` | Runs global + CN rules and the 10-second skim. Writes `lint.json`; exit `4` on lint errors. |
| `match` | Fit report only: must-have, nice-to-have, gate requirements, hidden signals, range, tier, gaps, risks. Writes `match.json`. |
| `tailor` | Ingests a file (or loads `--app`), scores the JD, selects facts, and creates/updates the application. Missing must-haves are reported, never invented; no render. |
| `recommend` | Role families, matched/missing terms, and a proof-building plan. No job-board access. |

Templates are language-classified by resume locale, not by market. `new`/`tailor`/`restyle` resolve the variant from `writing.locale` (falling back to the market profile's `language`); a missing variant fails with `render.template_missing` and a wrong-language learned template with `render.language_mismatch`. Build and QA repeat the resolution. `resume templates` lists both languages and each variant's preview path.

`tailor` and `new` require an explicit writing framework. `tailor` without an existing application and without `--framework` exits `3` with `writing.framework_missing`. A file ingested by `tailor` replaces an existing vault with a different name unless `--merge` is explicit.

### 3.4 Build and localize

```
resume build <application> [--draft] [--template <id>] [--yes] [--json]
resume localize <application> --to <en|zh> [--market <id>] [--role <role>]
                 [--template <id>] [--framework <id>] [--draft] [--yes] [--json]
resume templates [--json]
```

| Command | Behavior |
|---|---|
| `build` | Runs the gate and lint, then writes `resume.html`, `resume-editable.html`, `render.json`, and `lint.json`. `blocked` exits `2`; `minimum` requires `--yes`; lint errors exit `4`. |
| `templates` | Lists the 12 public variants (six signed layouts × `templates/cn` and `templates/en`), plus learned `user-*` templates: id, language, markets, personas, pages, columns, fingerprint, directory `path`, and `preview` (the `preview.html` path, also printed in human output). The CLI groups by language folder. |
| `localize` | Re-derives from the vault for the target market; writes a parity report and the target HTML. Retains the source layout ID and resolves its target-language variant unless `--template` overrides it. Missing target-locale facts exit `3`; `--draft` marks them. Parity failures exit `4`. Literal translation is not a mode. |

### 3.5 Verify

```
resume audit <application> [--json]
resume diff <application> <version-a> <version-b> [--json]
resume doctor [--json]
```

| Command | Behavior |
|---|---|
| `audit` | Runs content, market, layout, parseability, and privacy checks. Exit `4` on hard failure. |
| `diff` | Compares two versions: facts, bullets, template, page count. |
| `doctor` | Planned: checks Python, optional extractors, fonts, and write permissions. |

## 4. Application directory

```
.resume/applications/<slug>/
├── application.yaml
├── resume.html
├── resume-editable.html
├── sufficiency.json
├── extraction.json
├── template-audit.json
├── lint.json
├── match.json
├── parity.json
├── qa.json
└── versions/
    └── <timestamp>/
        ├── application.yaml
        ├── resume.html
        └── qa.json
```

`versions/` is append-only. `build` snapshots the previous output before writing.

## 5. Error format

```
<code>: <path>: <message>
  fix: <one concrete action>
```

Example:

```
3: application.yaml selection.bullet_ids[2]: unknown bullet id "bul_exp_009"
  fix: run `resume profile --json` and pick an existing bullet, or add the fact to the vault first.
```

Errors never say "something went wrong". Every error names a path and a fix.

## 6. Stdout / stderr

- Human mode: result summary to stdout, progress and warnings to stderr.
- `--json`: exactly one JSON object to stdout; no prose. Warnings go to stderr as NDJSON.
- Reports are written to files and their paths printed. They are not dumped into the terminal.

## 7. Security and privacy

- All processing is local.
- No telemetry.
- `--json` output and logs redact phone, email, ID number, and home address by default; `--include-pii` is explicit and never used by reports.
- User files are never uploaded.
- A learned template stays under `templates/user-<hash>/` and is excluded from git by default.

## 8. Non-goals

No `apply`, no `scrape`, no `login`, no `upload`, no `email`. The CLI produces files; it does not contact employers.
