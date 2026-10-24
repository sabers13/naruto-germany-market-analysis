# Publication scope

This companion publishes an original implementation of analysis methods, documentation, synthetic inputs, and synthetic outputs. It does not distribute the finished study's dataset or results.

## Included

- Configurable offline rank aggregation and explicit missing-data handling.
- Match-quality calculations, sensitivity checks, and agreement calculations.
- Deterministic releases, provenance, local CLI, and automated verification.
- Invented entities, generic invented sources, and invented quality counts.

## Outside this companion

- Raw or normalized platform data, scraped pages, comments, listings, usernames, media, or API payloads.
- The existing dashboard JSON, ranks, aggregate counts, or report screenshots.
- Collection scripts, session material, credentials, and archive history.
- Character illustrations, logos, copied fonts, or other platform/rights-holder assets.

## Adding another input

The caller must establish permission to access, process, retain, and redistribute it for the intended use. Those are distinct questions. A publicly accessible page, a robots allowance, aggregation, an API key, or keeping data private is not a blanket grant of those rights. The engine has no built-in legal clearance mechanism. Unverified caller data is labelled `user_supplied_unverified`.

This repository intentionally needs no live platform requests. Its local demonstration can be reviewed and reproduced independently of source terms.

## Placement in the GitHub project

This companion lives under `methods/` with its own README, source tree, examples, tests, and licence. The outer README links to `methods/README.md`; the root GitHub Actions workflow runs `make check` in `methods/`.

Adding the companion does not retroactively establish permissions for files already published elsewhere in the repository. The methods contribution and any existing report/data release must be described separately.
