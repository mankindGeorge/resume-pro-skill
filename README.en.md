<!-- SPDX-License-Identifier: MIT -->

# Resume Pro Skill

[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![中文](https://img.shields.io/badge/%F0%9F%87%A8%F0%9F%87%B3_%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-Available-green)](README.md)
[![English](https://img.shields.io/badge/%F0%9F%87%BA%F0%9F%87%B8_English-Current-blue)](README.en.md)
[![Docs](https://img.shields.io/badge/%F0%9F%93%96_Docs-Read-FF7A00)](#documentation)

**Get the facts right. Then make the resume work.**

A resume skill for Chinese and international job applications, combining an agent's guided intake and writing with a Python CLI's validation and rendering. Create, improve, tailor, and localize resumes from a shared record of career facts.

No invented experience, no one-shot generic prose, and no treating Chinese and English resumes as sentence-by-sentence translations. Resume deliverables are **HTML only**, with an **A4** print layout.

## What it does

| Your goal | Workflow |
|---|---|
| Create a resume from scratch | Collect information in stages, check sufficiency, and ask for missing details |
| Improve an existing resume | Extract facts, ask for confirmation, and assess whether to keep or replace the template |
| Understand what needs fixing | Diagnose without silently rewriting |
| Tailor to a role | Select experience against a job description (JD) and report matches, gaps, and risks |
| Explore suitable roles | Recommend role families from existing experience and identify evidence to add |
| Switch between Chinese and English | Reorganize facts and wording for the target market |
| Change the layout or add a photo | Preserve facts; optional photo slots disappear when unused |

Supports students, interns, new graduates, career switchers, experienced professionals, and other personas. Primary market profiles include `cn_internet` and `intl_en`; see the [market matrix](docs/market-matrix.md) for the scope of other profiles.

Cover letters, interview coaching, salary negotiation, job scraping, and auto-apply are out of scope.

## Core principles

- **Facts and evidence first.** Resume bullets link to sources, distinguishing verified, user-asserted, estimated, and unknown information. Numeric claims supported only by estimated or unknown sources are blocked by checks; a user assertion is not external verification.
- **Guide before generating.** Ask targeted questions when information is missing instead of filling gaps with fiction. Ask about mass versus targeted applications before selecting experience.
- **Writing frameworks require consent.** Ask before applying STAR, XYZ, FAB, CAR, result-first, or user-voice guidance.
- **Different markets, different priorities.** Adjust sections, order, page budgets, and photo policies by market and career stage. Chinese campus profiles emphasize education, fundamentals, real internships, and individual project contributions.
- **No job-intent section.** Use the target role for selection and file naming, not as a separate resume section.
- **HTML-only, A4.** Deliver self-contained HTML. Users can print to PDF in their browser with A4 selected; there is no DOCX, LaTeX, or image resume export.
- **Separate automated checks from judgment.** The CLI checks structure, evidence rules, templates, and output. The agent and user handle wording, fact confirmation, and final review.

## Quickstart

### 1. Prepare the environment

Requires **Python 3.10+**. Run from the repository root:

```bash
python -m pip install -e .
resume --version
resume --help
```

Editable installation lets the CLI read templates, profiles, and schemas directly from the source directory. Keep that directory after installation; downloading dependencies may require network access on first install.

- Install Edge, Chrome, or Chromium for browser-backed layout QA. When unavailable, some checks fall back to estimates and emit a warning.
- Legacy DOC / RTF ingestion requires LibreOffice.
- To use an agent, load this project as a skill with [SKILL.md](SKILL.md) as its entry point. The agent must be able to run local commands; importing a skill does not establish that Python dependencies are ready. See [installation](docs/install.md).

### 2. Collect career information

This example targets Chinese internet-sector campus / internship applications. Run in a separate job-application working directory:

```bash
resume init --market cn_internet --persona student_with_internship
resume intake
resume check
resume profile
```

Answer the guided questions. If checks report missing information, fill the gaps before generating; do not bypass a blocked gate. Data is stored under `.resume/` in the current working directory.

### 3. Choose a writing approach and build

Use `--framework result_first` below only after the user agrees to that framework, or replace it with their chosen alternative.

```bash
resume new --role "Backend Engineer" --market cn_internet --persona student_with_internship --framework result_first
```

Replace `<slug>` below with the application identifier returned by the previous command. Confirm the content, then check and build:

```bash
resume lint --app <slug>
resume build <slug> --yes
resume audit <slug>
```

`--yes` confirms acceptance of a minimally sufficient profile; it cannot bypass a blocked gate or other hard failures. Open the generated HTML to review content and layout. For PDF, use the browser's print function with A4 selected.

### 4. Work with an existing resume or target role

These are independent examples. Replace file paths and `<slug>` with your own inputs:

```bash
# Diagnose an existing resume
resume review resume.pdf --market cn_internet --persona experienced

# Extract information and assess the original template; confirm extracted facts
resume optimize resume.docx --market cn_internet --persona experienced

# Compare against a JD and explore suitable role families
resume match --app <slug> --jd jd.md
resume recommend --app <slug>

# List templates or add an optional photo to an application
resume templates
resume photo portrait.jpg --app <slug>

# Create an English application from the recorded facts
resume localize <slug> --to en --role "Backend Engineer" --yes
```

Localization requires the agent and user to supply target-language wording. When it is missing, the CLI reports gaps rather than translating or inventing content. Failed fact-parity checks block final delivery.

For complete workflows, see the [walkthrough](docs/walkthrough.md) and [CLI contract](docs/cli-contract.md).

## Inputs, templates, and outputs

**Inputs:** DOCX, text-based PDF, HTML, Markdown, and TXT. DOC / RTF require LibreOffice. OCR for scanned PDFs is not currently supported.

**Templates:** Chinese and English templates are organized separately, without CN / EN badges on the rendered resume. Chinese resumes use Chinese templates, English resumes use English templates, and cross-language combinations are rejected.

| Language | Directory | Templates included in the source tree |
|---|---|---|
| 中文 | [`templates/cn/`](templates/cn/) | `campus`, `zh-professional` |
| English | [`templates/en/`](templates/en/) | `ats-classic`, `modern-sidebar`, `editorial`, `executive` |

Photo slots collapse completely when unused; `intl_en` suppresses photos by market policy. Review each layout with actual content. Automated checks are not design approval or a guarantee of compatibility with every ATS.

**Outputs:** Final HTML, a non-canonical editable HTML copy, and check reports. Targeted applications normally include the role in the file name. Browser edits to the editable copy are not automatically merged back into the career vault.

## How it works

```text
Guided intake → sufficiency gate → market/persona profile → fact selection
              → application model → writing + lint → optional localization → HTML → QA
```

- **Career vault:** Durable experience, evidence records, and per-language wording.
- **Application model:** Fact selections, target market, writing settings, and template for one application.
- **Template contract:** Slots and content requirements declared with `data-slot`, filled by a deterministic renderer.

The CLI processes data locally, with no telemetry or automatic upload feature. Whether the agent's model provider receives conversation or file content depends on your client and model configuration; this does not make the entire workflow offline.

## Documentation

Detailed technical documentation is currently primarily in English. The language links above switch only the project README.

| Document | Contents |
|---|---|
| [Installation](docs/install.md) | Environment requirements and Skill / CLI setup |
| [Quickstart](docs/quickstart.md) | Guided intake, checks, and common commands |
| [Walkthrough](docs/walkthrough.md) | Complete an application by scenario |
| [Agent entry](SKILL.md) | Triggers, workflows, and non-negotiable rules |
| [Market matrix](docs/market-matrix.md) | Market and persona coverage |
| [Chinese resume rules](docs/cn-resume-rules.md) | Content and structure for Chinese-market resumes |
| [Intake and sufficiency](docs/intake-and-sufficiency.md) | Follow-up questions and generation gates |
| [Writing engine](references/writing-engine.md) | Frameworks, wording, and evidence constraints |
| [Triggers and routes](docs/triggers-and-routes.md) | Handling different user intents |
| [CLI contract](docs/cli-contract.md) | Commands, inputs, outputs, and exit codes |
| [Template contracts](docs/template-contracts.md) | Slots, budgets, and template rules |
| [Evaluation and limitations](docs/evaluation.md) | Tests, QA, and ATS-check boundaries |
| [Open-source policy](docs/open-source-policy.md) | Rules for code, templates, and assets |

## Development and verification

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The public suite covers the vault, evidence rules, intake, ingestion, selection, templates, rendering, localization, and QA. Passing tests do not certify hiring outcomes, universal ATS compatibility, or upstream code provenance.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before contributing.

## License

This project uses the [MIT License](LICENSE). See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for prior art and license notes. Third-party content remains subject to its own licenses.
