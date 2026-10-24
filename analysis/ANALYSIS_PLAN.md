# Analysis plan (fixed before results)

**Status:** FROZEN on 2026-10-23.
**Rule:** nothing in this file changes after any lane has produced numbers, except through §12 (amendments), which needs a dated entry and a reason. §1–§11 are not edited.

Why it's fixed: the preview prototype already shows a ranking (Sasuke, Itachi, Kakashi). Changing the method after seeing results would let the analysis drift toward that answer. The plan below decides every choice in advance.

---

## §1 Question and output

**Main question:** which Naruto characters show the strongest evidence of potential to sell as a branded product in Germany, and how confident can we be?

**Output:** `release/dashboard.json`, valid against `contract/dashboard.schema.json` (contract 1.0.0), plus `reports/FINDINGS.md`.
**Out of scope:** units sold, revenue, residents vs. language, drink demand. No source measures these, and the dashboard says so.

## §2 Characters (locked)

- **14 keys** in `config/characters.yaml`.
- **Benchmark:** `naruto_uzumaki`. Shown, never ranked: his name is also the franchise name.
- **Candidates (13, ranked):** Sasuke, Itachi, Kakashi, Hinata, Gaara, Madara, Obito, Minato, Pain/Nagato, Jiraiya, Orochimaru, Tsunade, Shikamaru.
- **Excluded:** Sakura and Boruto. Never ranked, never shown.

## §3 Inputs

- **Archive:** read-only, at the path in `config/paths.toml`, pinned to commit `1dd5472`. `nga.paths.check_archive()` must pass at the start of every pipeline run.
- **Copying:** never copy archive files into this repo. Row-level intermediates (titles, snippets, comment text) live only in `work/` (gitignored).
- **Snapshot date:** 2026-10-22.
- **YouTube:** stays in the analysis and the output. The release contains only **project-computed** YouTube counts (German comments and German-channel videos mentioning each character), labelled as of `youtube_snapshot: 2026-10-22`. These are project metrics, not YouTube statistics, so they may be kept and shown after the 30-day window. **Never** use or show YouTube's own view, like or comment-count statistics anywhere in this repo's outputs. The archive's raw API payloads are purged or refreshed by 2026-11-21. This pipeline does **not** call any API.

## §4 Cleaning rules per source

General:
- Count distinct entities (ASIN, item ID, ad ID, video ID, comment ID), never raw rows.
- A record that names several characters counts once for **each** of them. Lanes also record a `solo_*` variant: records whose only candidate character is this one (the benchmark may co-occur).
- Price outliers are flagged, not deleted: excluded from medians, kept in counts.

| Source | Table(s) | Rules |
|---|---|---|
| **Amazon.de** | `amazon/out/amazon_search_cards.parquet` | Dedupe by ASIN. Character = keys in `character_matches` (split on `"; "`). **Primary metric:** distinct ASINs. Secondary: median `review_count` per ASIN (ASINs with no review count excluded), and median `price_value`. Sponsored cards count the same as organic. |
| **eBay.de** | `ebay/data/ebay_de_observations.parquet` | `naruto_relevant = true` only. Dedupe by `item_id`, keeping the newest observation. Character = `character_matches` list. **Primary metric:** distinct items, all strata. Secondary: live items (observed 2026-10-22) and historical items reported separately; median `price_value` by stratum (exclude > €5,000); merch mix by `merch_category`, mapped to the 6 contract categories (figure+funko → figures; apparel+cosplay → clothing; trading_cards → cards; manga+media+print → manga_media; accessories+plush → accessories; other → other). |
| **Kleinanzeigen.de** | `kleinanzeigen/raw/final/listings.parquet` | Dedupe by `ad_id`. Character = `character_tags`. **Primary metric:** distinct offer ads (`is_wanted = false`); wanted ads reported separately. Median `price_eur` excluding `price_suspect` and price types other than fixed or negotiable. Regions: count per `state` (16 Bundesländer) per character; any cell with n < 10 is suppressed in the release. |
| **YouTube** | `youtube/raw/parquet/naruto-de-youtube-v1__videos.parquet`, `…__comments.parquet` | Videos: `is_naruto_relevant = true` and `channel_country = 'DE'`. Character = keys of `d_mentions.entities` (`kakashi_mask` → Kakashi). **Primary metric:** German comments: dedupe `comment_id`, `d_lang_guess = 'de'`, character from `d_mentions.entities`. Secondary: DE-channel videos, likes on German comments. |
| **Google Trends DE** | `google_trends/raw/20261022T1000Z__full/out/parquet/timeseries_bridged.parquet` (+ `geo.parquet`) | Follow `google_trends/docs/limits_and_comparability.md`: rescale everything to one reference batch (no chained rescaling); exclude censored series. **Primary metric:** mean weekly index over the last 52 complete weeks. Use the **topic series** (`trends_topic` in characters.yaml) for every character that has one (12 of 14), all brought onto one shared reference scale. Madara has no topic but his plain term is unambiguous: use it, rescaled onto the same reference, and flag it `term_series`. Pain has no topic and an ambiguous term, so Pain is **missing** in this source, not zero. If a character's topic series is censored, fall back to its plain term only when that term isn't flagged ambiguous; otherwise missing. Momentum: quarterly mean of the weekly values, 2021-Q4 → last complete quarter. `change_12m` = last 4 complete quarters vs. the 4 before. Regions (context only): within-batch share from `geo.parquet`, never averaged across metric types. |
| **Anime2You** | `anime2you/data/full/posts.parquet`, `comments.parquet` | **Primary metric:** comment mentions. Match `text_aliases` on `content_text`, whole word, case-sensitive. Ambiguous bare aliases (Hinata, Pain) count only when a `naruto_context_words` term appears in the same comment. Dedupe comment `id`. Secondary: articles via `characters_mentioned`. |
| **NARUTOP99** | `anime2you/data/external/narutop99/narutop99_rankings.parquet` | `region = 'europe'`. **Primary metric:** votes (exact name map from characters.yaml). One 2023 snapshot. |
| **Wikimedia** (context) | `wikimedia/collector/exports/full_2026-10-22/pageviews.parquet` | `granularity = 'monthly'`, `agent = 'user'`, last 12 complete months, all languages. `primary = false`, lens `context`. |
| **Instagram** (context) | `instagram/raw/parquet/insta_records.parquet` | Media count per character from `mentions_detail`. `primary = false`, lens `context`. |
| **Event calendar** | `event_calendar/data/events.parquet` | Dashboard timeline: ≤ 6 events from franchise event types only, chosen in this order: (1) `confirmed` German-relevant events (`region_scope` de/dach) in the core window, newest first, leaving one slot; (2) the newest `confirmed` franchise announcement. Each needs `source_url`. Titles/notes in EN and DE, written by the lane (facts only). |

## §5 Metric registry and lenses

Every lane writes the long table in `src/nga/metrics.py`. Exactly one `primary` metric per in-score source:

| Source | Primary metric (`metric`) | Lens | Class | In score |
|---|---|---|---|---|
| amazon | `asins` | shoppers | A/D | yes |
| ebay | `items` | shoppers | A/D | yes |
| kleinanzeigen | `offer_ads` | shoppers | A/D | yes |
| youtube | `comments_de` | watching | B | yes |
| google_trends | `interest_52w` | watching | A | yes |
| anime2you | `comment_mentions` | watching | B | yes |
| narutop99 | `votes_eu` | votes | C | yes |
| youtube (2nd) | `videos_de` | watching | B | **no** (secondary; shown, not ranked, because it overlaps with comments) |
| wikimedia | `pageviews_12m` | context | C | no |
| instagram | `media` | context | C | no |

That gives **7 in-score sources:** 3 shoppers, 3 watching, 1 votes. The dashboard's `kpis.sources_in_score` = 7. The preview's 8 counted YouTube twice; that was a preview artefact.

## §6 Accuracy check (keyword precision)

1. **Matches file:** each lane writes `work/matches/<source>.parquet` with one row per (record, character) match: `record_hash` (sha1 of the source ID), `source`, `character_key`, `matched_on` (alias or tag), `snippet` (≤ 200 chars around the match, or the title). This file stays local.
2. **Sample** (seed `20261023`): per in-score keyword source (amazon, ebay, kleinanzeigen, youtube, anime2you), 40 random matches overall, plus 15 per ambiguous character (Hinata, Pain/Nagato), plus 10 per top-5 candidate by preliminary count. About 400 items in total.
3. **Labeller:** a model from a **different family** than the lane author (the matching rules were written by one model, the labels by another). Labels: `correct` / `wrong_character` / `not_naruto` / `unclear`. `unclear` counts as wrong.
4. **Precision** per (source, character) where n ≥ 10, else per source; Wilson 95% interval.
5. **Rules:**

   | Precision | Treatment |
   |---|---|
   | ≥ 0.90 | Use as is |
   | 0.70 – 0.90 | Multiply counts by precision before ranking; flag `low_precision` |
   | < 0.70 | Drop that (source, character) from scoring; flag `excluded_source`; dashboard shows it hatched |

   If a source's overall precision is < 0.50, **stop** (§10).
6. Labels are kept as `reports/accuracy/labels.csv` (no snippets; notes describe the error type without quoting). The public repository holds only the aggregate `precision.csv` and the spot-check summary. The sample is rebuilt deterministically from the seed and joined on `sample_id` + `record_hash`. Snippets stay in `work/`.

Google Trends, NARUTOP99 and Wikimedia are not keyword-matched and skip this step.

## §7 Scoring

1. **Within each in-score source:** rank the 13 candidates by the (precision-adjusted) primary metric, highest = 1. Ties get the average rank. A missing value (source doesn't cover the character, or it was excluded in §6) is **not** ranked, never filled with 0.
2. **Lens rank:** the mean of that character's source ranks within the lens. If fewer than half of the lens's sources rank the character, the lens rank is null.
3. **Score:** the weighted mean of the non-null lens ranks with weights **shoppers 0.50 / watching 0.30 / votes 0.20**, renormalised over the non-null lenses. Lower is better.
4. **Evidence index:** `round((13 − score) / 12 × 100)`, giving 0–100.
5. **Rank:** ordered by score; ties broken by shoppers lens rank, then alphabetically.
6. **`top3_sources`:** the number of in-score sources where the character ranks ≤ 3.
7. **Robustness:**
   - Leave-one-source-out: 7 runs, each dropping one in-score source. Report each run's top 3 and `same_top3` (the count of runs whose top-3 *set* equals the main top 3).
   - Alternative weights, fixed here: equal (⅓ each); shoppers_only (1/0/0); german_only (0.625/0.375/0, which drops the Europe vote). Report the top 3 and `same_top3` for each.
   - Kendall's W across the 7 sources on the candidates that every source ranks. Label: W < 0.3 weak, 0.3–0.6 moderate, > 0.6 strong.
8. **Confidence per character:**
   - `robust`: in the top 3 in the main run and in ≥ 6 of 7 leave-one-out runs and in all 3 alternative weightings.
   - `one_source`: ranked ≤ 3 in exactly one source and > 6 in the main run.
   - `mixed`: everyone else.

## §8 Other outputs

| Contract field | Rule |
|---|---|
| `momentum` | The 6 series in the dashboard: the top 3 by score plus the 3 next-highest candidates that have a topic or unambiguous term series. Values rounded to 2 dp. `flags` mark ambiguous or censored series. |
| `regions` | Kleinanzeigen counts for the top 3 by score, per state; `suppress_below: 10`; `full_edition_only: true`. |
| `merch` | eBay merch mix for every candidate with ≥ 100 items; `min_items: 100`. |
| `prices_eur` | Median asking prices per platform; null if fewer than 10 priced records. |
| `kpis` | `shop_listings_checked` = distinct Amazon cards + eBay items + Kleinanzeigen ads before character filtering; `youtube_comments_de`; `youtube_comments_total`; `anime2you_articles`; `records_counted` = sum of all in-score source records; `characters_ranked` = 13; `sources_in_score` = 7. |
| `sources` | Records per source as used (after dedupe). |

## §9 Release

`release/dashboard.json`:
- `meta.status = "validated"`;
- `contract_version` 1.0.0;
- `archive_commit` from `check_archive()`;
- `input_sha256` = sha256 over the sorted list of (path, sha256) for every archive file read.

It must validate against the schema, and a reconciliation report must show every number traced to its metric row.

## §10 Stop rules (the run stops and reports instead of working around)

The pipeline halts and reports when any of these happens:
1. Any test fails, or the schema is invalid.
2. The archive commit doesn't match the pin.
3. A source's overall keyword precision is < 0.50.
4. Distinct-entity totals differ by > 1% from the archive's documented counts (DATA_CATALOG.md) without a written explanation in the lane report.
5. Fewer than 10 of 13 candidates have a score.
6. Any task would need to change §1–§11 of this plan.

## §11 Publication

- Aggregates only.
- `regions.full_edition_only = true`.
- No titles, comment text, usernames, IDs or listing URLs in `release/`, `reports/` or git history.
- `work/` is never committed.

## §12 Amendments

Format: `YYYY-MM-DD — section — change — reason`. Leave empty unless a change is approved.

- 2026-10-23 — §3 — YouTube rule changed from "no YouTube figures after 2026-11-21 unless refreshed" to "only project-computed counts in outputs, kept as a dated snapshot; never YouTube's own statistics; raw payloads are purged by 2026-11-21" — follows the archive's retention note (III.E.4.b for raw data, III.E.4.h for project metrics); made before any lane ran
- 2026-10-23 — §6.3 — Phase 1 labelling and review ran on the same model family as the builders. Mitigation: a blind independent spot-check was commissioned by a different family (Claude Opus 5.5): 72 items, 70 agree (97.2%), Cohen's κ 0.91 (binary correct/not), all treatment decisions unchanged. Recorded in reports/accuracy/independent_spotcheck.md.
- 2026-10-23 — §7.2 / contract — Lens ranks are means of source ranks and therefore fractional; contract `lens_ranks` typed number 1–13 (was integer). Introduced by the release step; formalised in contract 1.1.0.
- 2026-10-23 — new §13 — Fair benchmark comparison with Naruto added (rules below); contract 1.1.0 adds `benchmark_comparison`. Ranking (§7) is unchanged: Naruto stays unranked.
- 2026-10-23 — §13 — `ahead_in` counts comparable sources whose UNROUNDED ratio is ≥ 1.00 (rounding to 2 dp is for display only). Reports describe ratios between 0.95 and 1.05 as "about the same as Naruto", never as ahead or behind. Rule 4 reading recorded: Naruto's character topic /m/02sp46 is censored in the archive, so the franchise-dominance test uses his plain term "Naruto" (the series actually used); the release's `detail` text says so. Reason: review finding on rule 4.
- 2026-10-23 — §4 Google Trends / §8 momentum — Censoring is tested on the exact weekly series used (same batch and view), with the archive's definition (google_trends/docs/limits_and_comparability.md): censored if its peak in the used window is < 10 or > 30% of weekly buckets are zero. Censored series get the momentum flag `censored` (flag precedence: ambiguous_name > censored > term_series > topic_series), and reports must not describe their change_12m as a rise or fall. If a censored series feeds `interest_52w` in scoring, §4 requires it to be missing: this is a conformance check, and any resulting ranking change needs explicit approval before release. Reason: phase-2 review should-fix 4.
- 2026-10-23 — §4 Google Trends / §8 momentum — Correction to the censoring test: use the archive's own definition exactly as term_inventory.csv applies it. A series is censored if its peak over the full window of the request it comes from (the trends batch/view) is < 10, OR if more than 30% of its weekly values are zero within the window being used (the 52 weeks for interest_52w; the full momentum window for momentum flags). Peaks are not tested on the 52-week sub-window, because every request contains the dominant anchor "Naruto", which makes every candidate's recent peak small by construction. Censored series are missing in interest_52w scoring (§4) and flagged `censored` in momentum. Ranks 6–13 may change as a result; any change to the membership or order of the top 5 requires explicit approval.
- 2026-10-23 — §7.7 — Kendall's W is reported twice: (a) headline: W across the in-score sources excluding google_trends, on the candidates every one of those sources ranks; (b) secondary: W across all 7 in-score sources on their complete cases, labelled with its n. The agreement label uses (a). Reason: after the censoring correction, google_trends ranks only 4 candidates, and W on n = 4 (three of them the top 3) is unstable and understates agreement. Ranking, LOO and alternative weights are unaffected.
- 2026-10-23 — §13 rules 1, 3 and 5 — Kleinanzeigen moves from rule 1 (explicit_tags, comparable) to rule 3 (alias_restricted, NOT comparable): the archive tagger treats plain "Naruto" as the franchise and tags Naruto only on "Uzumaki"/"Naruto Uzumaki" (datasets/kleinanzeigen/docs/FINAL_DATASET.md §3.3), so his count is narrowed relative to the candidates. Rule 5 now also needs the lower 95% bound of Naruto's precision to be ≥ 0.90; otherwise NOT comparable with reason `precision_uncertain` (YouTube comments: 0.93 from n = 14, lower bound 0.69). The benchmark minimum drops from 2 comparable sources to 1, and the UI states how many sources the comparison rests on. Result: only NARUTOP99 votes are comparable. Contract 1.2.0 adds `precision_uncertain`. Reason: owner review of the comparison before publication.
- 2026-10-23 — §8 / §11 — New contract field `regions_trends` (contract 1.2.0): Google Trends DE by state from the archive's regional batches, context only, never scored. `naruto_index` = single-term "Naruto" request (strongest state = 100); `shares` = each candidate's plain-term share of the one multi-term request it appears in, whole percent, Google's 0 kept as null (too few searches, not zero); `readings` = `ambiguous` for ambiguous_name characters, else `flat` when highest minus lowest state ≤ 2 points, else `hint`; candidates without a regional series are listed in `missing`. The release step also writes `release/dashboard.public.json` (`meta.edition = "public"`): no Kleinanzeigen figures (counts, prices, accuracy, records, Naruto's benchmark value; KPIs leave the ads out), no `regions` block. Kleinanzeigen still feeds the evidence index and `meta.notes` says so. Reason: the platform's terms (§5(1) Nutzungsbedingungen) require written consent for automated access, so its figures are not redistributed.

## §13 Benchmark comparison (Naruto), fixed on 2026-10-23

Purpose: show each candidate "compared with Naruto" only where the comparison is fair. Naruto stays unranked (§2).

Comparable sources, decided by these rules in this order (first match wins):
1. explicit_tags: the source tags characters explicitly → comparable. (kleinanzeigen `offer_ads`)
2. vote: a direct vote count → comparable. (narutop99 `votes_eu`)
3. alias_restricted: Naruto's matching was deliberately narrowed relative to other characters → NOT comparable. (anime2you `comment_mentions`; anime2you `articles` uses the archive's own extraction with unknown Naruto handling → NOT comparable, reason not_measured)
4. franchise_dominated (google_trends `interest_52w`): compute the Pearson correlation between Naruto's character-topic weekly series and the franchise topic `/m/01hryy` over the same 52 weeks, both on the shared reference. r ≥ 0.90 → NOT comparable; r < 0.90 → comparable. Report r.
5. precision: keyword/entity sources (amazon `asins`, ebay `items`, youtube `comments_de`) are comparable only if Naruto's own precision row in reports/accuracy/precision.csv is ≥ 0.90 (precision_ok), else NOT comparable (precision_low). youtube `videos_de` has no Naruto precision measurement → NOT comparable (not_measured).

Values: use the same values scoring uses (after §6 treatments; an excluded candidate cell is null). Ratio = candidate value ÷ Naruto value, rounded to 2 dp; null when not comparable or either value is missing. `ahead_in` = number of comparable sources with ratio ≥ 1.00; `comparable_sources` = number of comparable sources with a non-null ratio for that candidate.

Wording rule for reports: "Minato reaches 640% of Naruto's Europe vote", never "Sasuke is more popular than Naruto".
- 2026-10-23 — §8 kpis/sources — Record counts cover only records actually used: google_trends `records` and kpis.records_counted exclude the rows of censored series.
- 2026-10-23 — §8 momentum — change_12m stays in the release for every shown series (contract unchanged), but values flagged `censored` must not be displayed or described as a trend. counts.google_interest = null means "not measurable (censored or ambiguous)", never zero. Both rules are stated in meta.notes and the release notes.
