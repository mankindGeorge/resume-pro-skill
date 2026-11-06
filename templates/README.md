# Template Library

This folder holds **six distinct A4 designs in both Chinese and English: 12 variants**. `cn/` and `en/` indicate resume language; their manifests use `language: zh` and `language: en` respectively.

| Design ID | Structure | Chinese (`zh`) | English (`en`) |
|---|---|---|---|
| `ats-classic` | Minimal single column | [cn](cn/ats-classic/) | [en](en/ats-classic/) |
| `campus` | Education-first single column | [cn](cn/campus/) | [en](en/campus/) |
| `compact` | Compact one-page campus layout | [cn](cn/compact/) | [en](en/compact/) |
| `modern-sidebar` | Main column + right sidebar | [cn](cn/modern-sidebar/) | [en](en/modern-sidebar/) |
| `editorial` | One-page editorial | [cn](cn/editorial/) | [en](en/editorial/) |
| `executive` | Centered letterhead, two pages | [cn](cn/executive/) | [en](en/executive/) |

`resume templates` lists 12 public variants plus private learned templates. Rendering and QA select by `writing.locale`, defaulting to the market profile's `language`. Direct `load_template(id, language=zh|en)` calls must specify language for multilingual IDs; omission is an error, not a preference for `cn`.

Every variant:

- is A4 with declared margins and layout capacity budgets, which remain binding alongside market/persona page policy;
- reserves an optional `identity.photo` slot that collapses when empty; photo visibility follows market policy, not the design or language folder;
- orders sections by HR priority: students lead with education, then experience and projects; professionals lead with summary and experience, with education before skills;
- uses strict `data-slot` markers and a signed manifest;
- uses one standard system sans-serif family with no italic, oblique, serif/display, or variant glyph styling; ligatures/contextual alternates are disabled and numerals use lining figures;
- reorders sections within their assigned main/sidebar column. Language variants do not move sections between columns; modern-sidebar keeps education in the main column.

Default recommendations are `campus` / `modern-sidebar` for Chinese-market campus / professional profiles and `ats-classic` / `executive` for international default / senior profiles. Market/persona selection, writing, page, photo, and fact-confirmation rules remain binding, as does template review status; a signature is not design approval.

`restyle` changes appearance, not market or selection. `localize` still reselects and rewrites from facts for the target market, retaining the source design ID unless `--template` explicitly overrides it. Private learned templates under `templates/user-<hash>/` are never part of the public library. Missing target-language variants fail explicitly without a silent design fallback.

See [`docs/template-contracts.md`](../docs/template-contracts.md) for the full contract. The repository READMEs show preview thumbnails; regenerate them with `python scripts/build_readme_previews.py`.
