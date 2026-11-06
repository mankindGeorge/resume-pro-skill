# Evaluation

This is an internal evaluation on fictional fixtures. It is not a user study and it is not an ATS guarantee.

## 1. Automated surface

- Templates are organized under `templates/cn/` and `templates/en/`; the folders identify resume language (`zh`/`en`). Each of the six layouts exists in both languages (twelve variants).
- 271 tests cover vault validation, evidence rules, intake branching, continuous-interaction instructions and CLI state transitions, sufficiency, ingestion, template audit, template learning, selection, writing consent, lint, JD match, recommendation, HTML rendering, six A4 layouts in both languages, language-aware template resolution, education-first ordering, optional portrait slots, mass/targeted role classification, transcreation/parity that preserves the source layout, QA, version diffs, standard template typography, README preview assets, workspace publishing, and private-safe skill packaging/bootstrap.
- Run: `python -m pytest`.
- Browser QA: headless Edge/Chrome prints the rendered HTML to a temporary PDF, then checks actual pages, extracted text, selected bullets, headings, font floor, and section order.
- Reproducibility: the same vault + application + template produce byte-identical HTML. Template manifests are signed with SHA-256 over HTML + CSS.
- Golden preview hashes are stored under `tests/golden/` as `cn-<id>.sha256` / `en-<id>.sha256` (twelve files).

## 2. Fixtures

| Fixture | Purpose |
|---|---|
| `vault-student.yaml` | One internship + one project; bilingual; CN campus |
| `vault-student-projects.yaml` | Two projects, no internship; bilingual |
| `vault-experienced.yaml` | Two roles, six years; bilingual |
| `vault-incomplete.yaml` | Deliberately blocked; targeted questions |
| `vault-student-cn.yaml`, `vault-experienced-cn.yaml` | Chinese-language previews; `campus` and `modern-sidebar` |
| `vault-academic.yaml` | Academic-market data for localization tests |
| Strong/weak DOCX, HTML, PDF, scanned PDF | Ingestion and template audit |
| Six signed layouts × two languages (twelve previews) | Rendering, language parity, and A4 print |

## 3. Blind review rubric

A reviewer sees only the rendered resume, not the vault, and scores 1–5:

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Truth | Unsupported claims | Mostly supported | Every claim traceable |
| Targeting | Generic | Some JD language | Clear must-have coverage and gaps |
| Structure | Hard to scan | Standard sections | Strong primacy and hierarchy |
| Legibility | Cluttered | Readable | 10-second skim finds the signals |
| Market fit | Wrong conventions | Mostly right | CN/EN fields, order, page count correct |

A resume is shippable only when no dimension is 1 and Truth is at least 4.

## 4. ATS honesty

- The templates are text-based, single-column (except `modern-sidebar`), and use standard headings.
- `modern-sidebar` is a two-column layout; older ATS parsers may struggle. Use `ats-classic` when parseability is the priority.
- No tool can guarantee an ATS result. Always test against the target company's system when possible, and keep the HTML/PDF text selectable.
- The tool never claims a specific ATS score. `match` is a transparent rubric, not an employer's actual filter.

## 5. Known limitations

- PDF ingestion and template learning are approximate; scanned PDFs are detected, not OCR'd.
- Bullet rewriting is agent work guided by the framework; the CLI does not call an LLM.
- Continuous questioning is a mandatory host-agent instruction, not a CLI-controlled dialog. Regression tests check the instruction contract and scripted CLI answer/summary/resume transitions; they do not execute `AskUserQuestion`, verify a real host UI, or prove shell quoting. A host without a suitable interactive tool cannot run this workflow as specified.
- Intake `complete: true` and a passing sufficiency gate do not establish user consent. The agent must show the facts and independently verify `summary.confirmed: true`; a legacy skipped confirmation must be revisited. Re-answering collection fields may append, so the agent must verify requested replacements rather than assuming every `--id` edit is a replacement.
- Name order, phone formatting, and address granularity are not automatically transformed.
- Experimental markets (`cn_soe`, `cn_finance`, `cn_creative`, `hk_sg`, `academic`) are not validated in v1.
- Output is self-contained A4 HTML; PDF comes from the browser print dialog.
- No golden image snapshots; QA is text/geometry based.
- Portrait images are embedded as-is; there is no cropping or face detection.
- The target role is a targeting and filename device.
- No user study yet; measure with real candidates before making quality claims.

## 6. License and prior art

MIT. No AGPL, CC BY-NC, or unlicensed code/templates/assets are included. See `ATTRIBUTIONS.md` and `docs/open-source-policy.md`.
