# Install

## 1. Requirements

- Python 3.10 or newer.
- Optional: Microsoft Edge, Google Chrome, or Chromium for browser-backed QA (`resume audit`). Without one, QA falls back to estimates and warns.
- Optional: LibreOffice for legacy `.doc`/`.rtf` ingestion.
- No network access is required at runtime.

## 2. CLI

From the repository root:

```bash
python -m pip install -e ".[dev]"
resume --version
resume --help
resume templates
```

For a normal install:

```bash
python -m pip install .
```

## 3. Agent skill

The repository root is the skill: `SKILL.md` is the entry point. Point your agent's skill directory at this folder.

### 3.1 Packaged ZIP

Build a private-safe archive from a verified checkout:

```bash
python scripts/package_skill.py
# dist/resume-pro-skill-<version>.zip
```

The archive contains a single `resume-pro-skill/` folder. By default, before reporting `PASS`, the script unzips it and runs the bootstrap check, so a damaged or incomplete package is not reported as importable. It always excludes `.git`, `docs/local/` (including the private design review lab), learned `templates/user-*`, local workspaces, caches, and secret-like files. `--include-tests` adds the public suite; `--json` reports the SHA-256, file count, and archive size.

Unzip it into your agent's skill directory. Keep the folder on disk: the CLI reads `templates/`, `schema/`, and `profiles/` from it.

```bash
cd resume-pro-skill
python bootstrap.py              # Python version, dependencies, 12 template variants
python bootstrap.py --install    # editable install; adds the `resume` command
# If pip cannot install packages:
python bootstrap.py --deps-only  # dependencies only
python resume.py templates       # launcher for environments without `resume`
```

`--install` uses an editable install on purpose, so the imported folder remains the source of templates, schema, and profiles. Do not copy only the Python package elsewhere. If pip is unavailable entirely, install the packages in `requirements.txt` by hand and use `python resume.py`.

The bootstrap check verifies the package, not the host agent: it does not test an agent's question UI or tool permissions.

### 3.2 Common setups

- **Claude Code:** place or symlink the folder under `~/.claude/skills/resume-pro-skill`.
- **Codex / Cursor / Qoder:** add the folder as a skill/prompt directory in the agent's settings. The exact path depends on the client version; the agent only needs to read `SKILL.md`.
- **Manual:** open `SKILL.md` in the agent and ask it to follow the routing table.

Do not copy the repository into a public template library. The public library is split into `templates/cn/` and `templates/en/`; learned templates in `templates/user-*` are private and ignored by git.

## 4. First run

```bash
mkdir my-resume && cd my-resume
resume init --market cn_internet --persona student_with_internship
resume intake
resume check
```

Optional portrait: `resume photo portrait.jpg --app <slug>`. Every template reserves the slot; it is invisible when empty. Rebuild to embed the photo.

User-facing files are published to `workspace/<project-slug>/` in the project root. `resume build` copies the resume, editable copy, and reports there; `resume review` publishes its report to a review subfolder. Keep diagnoses and other user-facing reports in that project folder.

Then follow `docs/quickstart.md` or `docs/walkthrough.md`.

## 5. Print to PDF

The library templates are A4. Open `resume.html`, choose **A4** in the browser print dialog, and save as PDF.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `No .resume directory found` | Run `resume init` in the project root. |
| `vault.not_found` | Run `resume init` or `resume optimize` first. |
| `writing.framework_missing` | Choose `star`, `xyz`, `fab`, `car`, `result_first`, or `user_voice`. |
| `localize.locale_gaps` | Write the target-language facts in the vault, or use `--draft` to inspect markers. |
| `render.page_size_mismatch` | Use an A4 library template; the application must be A4. |
| `qa.layout.font_size` fails | Keep body text at 10pt or larger; 9pt is the floor. |
| QA says no browser | Install Edge/Chrome or set `RESUME_PRO_BROWSER`. |
| `.doc`/`.rtf` fails | Install LibreOffice or export to DOCX/PDF. |
