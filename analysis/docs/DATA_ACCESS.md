# Data access and scope

This directory holds the **analysis code**. It does not contain collection code, raw data, scraped pages, listings, comments, usernames, API payloads or the data archive the pipeline reads. The published numbers are aggregates (totals, medians, ranks, shares) in [`../data/dashboard.json`](../data/dashboard.json).

## What the pipeline reads

A local, read-only archive with one folder per source. `config/paths.toml` names its location (override with `NGA_ARCHIVE`) and the archive commit the analysis is pinned to; the run stops if the archive is at another commit. The exact tables and columns per source are in [`ANALYSIS_PLAN.md`](../ANALYSIS_PLAN.md) §4.

## Where each source came from

| Source | Role | Access route | Notes |
|---|---|---|---|
| YouTube | watching | Official YouTube Data API v3, own API key | Only project-computed counts are published, never YouTube's own view, like or comment statistics. Raw API payloads are purged after the 30-day retention window. |
| Wikimedia | context | Official Wikimedia REST API | CC0 data, not scored. |
| Anime2You | watching | The publisher's public WordPress REST API | robots.txt allows it; paced requests; the site has no terms page. |
| NARUTOP99 | votes | The official published results | A 2023 snapshot, read from archived copies. |
| Google Trends | watching | Google's public Trends service, Germany | There is no official API; Google offers a CSV export in the web interface. Figures are indices, not volumes. |
| Event calendar | timeline | Curated by hand from public announcements | Franchise events only. |
| Amazon.de, eBay.de, Kleinanzeigen | shoppers | Public pages of the platforms, small paced runs | These platforms restrict automated access in their terms or robots.txt unless permission is given, so **the collection code and raw data are not published**, and Kleinanzeigen figures are not published at all (the source only feeds the index). |

## If you want to reproduce this with your own data

Use an official route and check the terms yourself. A robots.txt allowance, a public page, aggregation or an API key is not by itself permission to collect, keep or redistribute data.

- eBay: the Browse API.
- Amazon: the Creators API (needs an eligible Associates account).
- Kleinanzeigen: ask the platform for written consent.

Everything in the pipeline works from any table that follows the same shape. The synthetic inputs under `tests/` run the whole release step without any archive: `make demo`.
