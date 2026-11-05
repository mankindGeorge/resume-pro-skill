# Open-Source Policy

> The project must be open-source by default and must respect the licenses of every project it learns from. We reuse **ideas and methods**, not files, unless the license explicitly permits it and the attribution is preserved.

## 1. Our license

- **Code:** MIT.
- **Templates:** MIT (original work).
- **Documentation:** MIT.
- **Examples:** MIT, with fictional candidates only.

MIT is chosen for maximum reuse and contribution. Every source file carries an SPDX header:

```text
SPDX-License-Identifier: MIT
```

## 2. Inbound reuse matrix

| Upstream license | Can we copy code/assets? | What we must do | Examples |
|---|---|---|---|
| MIT | Yes | Keep copyright + license notice; add to `ATTRIBUTIONS.md` | dabydat, yanliudesign, RenderCV, JSON Resume, HackMyResume, Reactive-Resume, offer-toolkit |
| Apache-2.0 | Yes | Keep NOTICE, license, and patent grant; state changes | Resume-Matcher |
| BSD-3-Clause | Yes | Keep copyright + license; no endorsement claims | Jinja2, etc. |
| AGPL-3.0 | **No** | Learn ideas only; do not copy code into an MIT project | OpenResume |
| CC BY-NC 4.0 | **No** (for commercial use) | Learn ideas only; do not copy templates, scripts, or text | vibe-resume-skill |
| No license | **No** | Treat as all rights reserved; learn conventions only | geekcompany/ResumeSample |

**Rule of thumb:** if the license is not clearly permissive, do not copy the file. Read it, extract the principle, and write our own implementation.

## 3. What we borrow from each project

| Project | Borrow (idea) | Do not copy |
|---|---|---|
| dabydat | XYZ/STAR doctrine, domain-context interview, ATS honesty, delivery verification | Reference text verbatim |
| yanliudesign | Router + schema-first flow, template catalog metadata, editable HTML, consent-based rewriting | Templates, prompts, text |
| KevinYoung | raw/resume split, template fingerprint, measured QA, preservation ledger | Templates, scripts, text (CC BY-NC) |
| Resume-Matcher | Master resume → per-job tailoring, deterministic component audit, parse round-trip | Code (Apache-2.0 is reusable, but we write our own) |
| Reactive-Resume | ATS-safe filter, extracted-text view, import formats, local-first privacy | Templates/code unless attributed |
| OpenResume | U.S. conventions, local-first, parser round-trip | Code (AGPL) |
| RenderCV | YAML → deterministic typography, version control | Code/typography themes unless attributed |
| JSON Resume | Interoperable schema discipline | Schema verbatim (we extend it) |
| JadeAI | JD match, writing lint | Templates, literal translation approach |
| geekcompany/ResumeSample | Chinese conventions, FAB, "write growth when no achievements" | Text/templates (no license) |
| offer-toolkit | Fit tiers, gap classification, three resume versions, CN/EN ≠ translation | Text/prompts verbatim |

## 4. Originality requirements

- Every template is original HTML/CSS, designed for this project.
- Every script is original; no copied implementation, even from permissive projects, unless explicitly attributed.
- Every reference document is written from scratch; short quotations are allowed with attribution.
- No scraped resume templates, stock resume text, or proprietary job-board content.
- No copied personal data or real candidate resumes in examples.

## 5. Data, privacy, and platform terms

- **Local-first:** the CLI reads local files; no upload, no telemetry, no analytics by default.
- **No credential handling:** do not ask for or store LinkedIn/job-board passwords.
- **No unauthorized scraping:** do not bypass login walls, rate limits, CAPTCHAs, or terms of service.
- **User-supplied JDs only** in v1; optional URL fetch only where the site permits it.
- **PII:** keep a PII inventory; support a public-share redaction mode; warn before sharing.

## 6. Attribution and notices

- `ATTRIBUTIONS.md` lists every project whose ideas informed the design, with links and license names.
- Source files that reuse permissively licensed code include the original copyright and license header.
- The README includes a "Prior art" section; it does not imply endorsement.

## 7. Contribution rules

- Contributors sign off commits (DCO) and confirm they wrote the code or have the right to submit it.
- No contribution may add a dependency with a non-permissive license without review.
- No contribution may add a template or asset of unclear origin.
- CI checks license headers and dependency licenses.

## 8. Release checklist

- [ ] All source files have SPDX headers.
- [ ] `LICENSE`, `ATTRIBUTIONS.md`, and `NOTICE` (if Apache-2.0 code is reused) are present.
- [ ] Dependency license scan passes.
- [ ] No AGPL/CC BY-NC/no-license code or assets copied.
- [ ] All templates and scripts are original.
- [ ] Examples use fictional candidates only.
- [ ] No telemetry or network calls by default.
