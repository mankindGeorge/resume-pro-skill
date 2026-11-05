# Attributions and Prior Art

This project studies existing resume tools and borrows **ideas and evaluation methods**, not code, templates, or text. All schemas, templates, and source code in this repository are original unless a file says otherwise.

## 1. Projects studied

| Project | License | What informed this project | What was reused |
|---|---|---|---|
| [dabydat/resume-builder-skill](https://github.com/dabydat/resume-builder-skill) | MIT | Editorial method: Harvard-style bullets, XYZ/STAR, domain context, ATS myths | Ideas only |
| [yanliudesign/resume-builder-skill](https://github.com/yanliudesign/resume-builder-skill) | MIT | Router → schema → entry flows → editable HTML; template library approach | Ideas only |
| [KevinYoung-Kw/vibe-resume-skill](https://github.com/KevinYoung-Kw/vibe-resume-skill) | CC BY-NC 4.0 | Raw/resume split, template allowlist, fingerprints, measured QA, CN focus | Ideas only; **no code or assets** due to the non-commercial license |
| [srbhr/Resume-Matcher](https://github.com/srbhr/Resume-Matcher) | Apache-2.0 | Deterministic ATS scoring dimensions and PDF round-trip checking | Ideas and weights, reimplemented |
| [AmruthPillai/Reactive-Resume](https://github.com/AmruthPillai/Reactive-Resume) | MIT | Template breadth, ATS filters, i18n, local-first UX | Ideas only |
| [xitanggg/open-resume](https://github.com/xitanggg/open-resume) | AGPL-3.0 | Parser checklist and U.S. resume best practices | Ideas only; **no code** |
| [rendercv/rendercv](https://github.com/rendercv/rendercv) | MIT | YAML → deterministic document pipeline | Ideas only |
| [jsonresume/jsonresume.org](https://github.com/jsonresume/jsonresume.org) | MIT | JSON Resume schema concepts | Ideas only |
| [hacksalot/HackMyResume](https://github.com/hacksalot/HackMyResume) | MIT | Theme/model separation and multi-format output | Ideas only |
| [geekcompany/ResumeSample](https://github.com/geekcompany/ResumeSample) | No license | Chinese resume conventions, FAB framing, writing growth when achievements are thin | Ideas only; **no text copied** |
| JadeAI (resume builder) | Not verified | Template breadth, JD matching, grammar checks, translation features | Observed features only; no code or assets |
| offer-toolkit-skill (Dreameryanyan) | MIT | Match rubric, gap tiers, ATS/recruiter/HM versions, EN↔ZH transcreation stance | Ideas only |
| Harvard Career Services guidance | Public guidance | Action verbs, bullet structure, resume length | Public best practices |

## 2. License compatibility

- MIT / Apache-2.0 / BSD: reusable with attribution. This project still prefers original implementations.
- AGPL-3.0: no code reused; ideas only.
- CC BY-NC 4.0: no code or assets reused; ideas only.
- No license: ideas only; no text or assets reused.

No AGPL, CC BY-NC, or unlicensed code, templates, or assets are included in this repository.

## 3. Originality statement

- The three JSON schemas are original.
- The six template layouts are original and are not traced from any commercial or open-source template.
- The lint rule set, sufficiency model, and route design are original syntheses.
- Example resumes use fictional people, schools, and companies. They are not real candidate data.

## 4. Trademarks

Company and product names mentioned in documentation belong to their owners and are used for identification only. No affiliation or endorsement is implied.
