# Template Library

This folder holds the six A4 templates, split by language.

```
templates/
├── cn/
│   ├── campus/           # single-column campus sheet
│   └── zh-professional/  # left sidebar + experience-first main column
├── en/
│   ├── ats-classic/      # bare single-column ATS sheet
│   ├── modern-sidebar/   # main column + right sidebar
│   ├── editorial/        # magazine-style one page
│   └── executive/        # centered letterhead, two pages
└── user-<hash>/          # private learned templates, never part of the public library
```

Every template:

- is A4 with declared margins and page budgets;
- reserves an optional `identity.photo` slot that collapses when empty;
- renders no 求职意向 section and no CN/EN badge;
- uses strict `data-slot` markers and a signed manifest.

See [`docs/template-contracts.md`](../docs/template-contracts.md) for the full contract.
