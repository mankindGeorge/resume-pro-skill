# Template Library

This folder holds **six distinct A4 designs in both Chinese and English: 12 variants**. `cn/` and `en/` indicate resume language only, not market eligibility; their manifests use `language: zh` and `language: en` respectively.

| Design ID | Structure | Chinese (`zh`) | English (`en`) |
|---|---|---|---|
| `ats-classic` | Minimal single column | [cn](cn/ats-classic/) | [en](en/ats-classic/) |
| `campus` | Education-first single column | [cn](cn/campus/) | [en](en/campus/) |
| `modern-sidebar` | Main column + right sidebar | [cn](cn/modern-sidebar/) | [en](en/modern-sidebar/) |
| `editorial` | One-page editorial | [cn](cn/editorial/) | [en](en/editorial/) |
| `executive` | Centered letterhead, two pages | [cn](cn/executive/) | [en](en/executive/) |
| `zh-professional` | Left sidebar + experience-first main column | [cn](cn/zh-professional/) | [en](en/zh-professional/) |

Keep `zh-professional` as the compatible historical ID, including for English. `resume templates` lists 12 public variants plus private learned templates. Rendering and QA select by `writing.locale`, defaulting to the market profile's `language`. Direct `load_template(id, language=zh|en)` calls must specify language for multilingual IDs; omission is an error, not a preference for `cn`.

Every variant:

- is A4 with declared margins and layout capacity budgets, which remain binding alongside market/persona page policy;
- reserves an optional `identity.photo` slot that collapses when empty; photo visibility follows market policy, not the design or language folder;
- renders no 求职意向 section and no CN/EN badge;
- uses strict `data-slot` markers and a signed manifest;
- preserves its design's fixed main/sidebar regions. Language variants do not move sections between columns.

Default recommendations remain `campus` / `zh-professional` for Chinese-market campus / professional profiles and `ats-classic` / `executive` for international default / senior profiles. Recommendations do not exclude other designs. Market/persona selection, writing, page, photo, and fact-confirmation rules remain unchanged, as does template review status; a signature is not design approval.

`restyle` changes appearance, not market or selection. `localize` still reselects and rewrites from facts for the target market, retaining the source design ID unless `--template` explicitly overrides it. Private learned templates under `templates/user-<hash>/` are never part of the public library. Missing target-language variants fail explicitly without a silent design fallback; legacy flat learned templates remain supported with manifest-language validation.

See [`docs/template-contracts.md`](../docs/template-contracts.md) for the full contract.
