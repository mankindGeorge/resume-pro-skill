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

Common setups:

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

Then follow `docs/quickstart.md` or `docs/walkthrough.md`.

## 5. Print to PDF

The library templates are A4. Open `resume.html`, choose **A4** in the browser print dialog, and save as PDF. The tool itself does not write PDF, DOCX, LaTeX, or image resumes.

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
