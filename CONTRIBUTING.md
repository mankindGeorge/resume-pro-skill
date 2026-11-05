# Contributing

## License

By contributing, you agree that your contribution is licensed under the MIT License in `LICENSE`.

## Developer Certificate of Origin

Sign off every commit:

```bash
git commit -s -m "feat: add sufficiency gate"
```

The sign-off certifies that you wrote the contribution or have the right to submit it.

## SPDX headers

Every source file starts with:

```
SPDX-License-Identifier: MIT
```

Use the comment syntax of the file type:

- Python / JS / CSS: `#` or `/* */`
- HTML / Markdown: `<!-- -->`

## No incompatible code or assets

Do not copy code, templates, fonts, images, or text from:

- AGPL projects;
- CC BY-NC projects;
- projects without a license;
- commercial template libraries.

If a technique is useful, reimplement it and cite the idea in `ATTRIBUTIONS.md`.

## Tests and fixtures

- Every rule needs a failing fixture and a passing fixture.
- Every template needs a snapshot test.
- Every schema change needs a migration note and updated examples.

## Examples and privacy

- Example resumes must use fictional people, schools, and companies.
- Never commit a real resume, phone number, email address, ID number, or employer-confidential material.
- `applications/` and `templates/user-*` are ignored by git. Keep them that way.

## Local working material

Keep internal plans, research notes, unapproved designs, and their private scripts/tests under `docs/local/`. The whole directory is ignored by Git and excluded from source distributions; new local files do not need individual exclusion rules. Keep published user documentation directly under `docs/`, and do not make public code or documentation depend on local-only files. Ignoring files does not remove previously tracked files or replace license compliance.

## Scope

This project covers resume creation, optimization, templates, and job-fit recommendation. Cover letters, interview prep, offer comparison, salary negotiation, job-board scraping, and auto-apply are out of scope.
