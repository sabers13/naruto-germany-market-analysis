# Findings: which Naruto characters show the strongest evidence of potential in Germany

Snapshot 2026-10-22 · public edition (`data/dashboard.json`, release_id `v1.2.0-20261022-8187b745`, sha256 `399c29c786a649c043d62f6ede4062410826aafb05fa6691edcbd7660587b0c1`, `status validated`, contract 1.2.0) · 13 candidates ranked, 7 sources in score, 1 source fairly comparable with Naruto.

Kleinanzeigen counts feed the evidence index, but its figures (ad counts, prices, state totals) are not published, so this edition leaves them out.

## 1. Answer: top 3 show the strongest evidence of potential

All figures below are from `characters[]` of the public release and match it exactly.

**1. Sasuke Uchiha — evidence index 93, rank 1, confidence `robust`, top-3 in 6 of 7 sources.**
Drivers: 623 eBay items (most of any candidate), 1,405 German YouTube comments (most). Supporting: 129 Amazon products, search interest 4.06 (highest candidate mean), 34,797 Europe fan votes.

**2. Itachi Uchiha — index 89, rank 2, `robust`, top-3 in 6 of 7 sources.**
Drivers: 129,376 Europe fan votes (2nd), 1,104 German YouTube comments (2nd), 562 eBay items (2nd). Supporting: 95 Amazon products, search interest 3.10.

**3. Kakashi Hatake — index 83, rank 3, `robust`, top-3 in 5 of 7 sources, flagged `low_precision`.**
Drivers: 475 eBay items (3rd), 692 German YouTube comments. Supporting: 89 Amazon products, 50,773 Europe votes, search interest 2.40. The `low_precision` flag means his counts were multiplied by measured keyword precision before ranking; treat shop counts as approximate, not exact.

We say "evidence of potential", never "will sell best": these are second-hand listings, search and fan signals, not sales.

The top 5 read as two tiers. **Shortlist** — Sasuke, Itachi, Kakashi: all
`robust` (top 3 in the main run, in all 7 leave-one-out runs, and in all 3
alternative weightings). **Contenders** — Madara (rank 4, index 68) and
Minato (rank 5, index 64): each leads in only one source (Madara 3rd on
German YouTube comments, Minato 1st on the Europe vote) and their evidence
rests on fewer sources, so they are follow-ups, not launch picks.

## 2. How sure are we

Leave-one-out: all 7 runs (each dropping one in-score source) keep the same top-3 set {Sasuke, Itachi, Kakashi}, 7/7.
Alternative weights: the equal (1/3 each), shoppers-only (1/0/0) and german-only (0.625/0.375/0, Europe vote dropped) weightings all keep the same top-3 in the same order.
Agreement is strong across the sources that rank (headline Kendall's W 0.713, labelled `strong`, over the 11 candidates every in-score source except google_trends ranks); across all 7 sources it is 0.429 (`moderate`, n=3 complete cases) — google_trends cells are missing for most candidates after censoring, so the 7-source W covers almost nobody.

## 3. Surprises and disagreements between sources

Biggest disagreement is the fan vote vs. the shops. Minato Namikaze won the Europe vote outright (223,694 votes, rank 1 on votes) but is only rank 5 overall (index 64, shoppers lens 6.0, watching 7.25; just 85 eBay items and 41 Amazon products). Sasuke is the mirror image: rank 1 overall and rank 1 on shoppers and watching, but only 5th on votes (34,797). Madara (rank 4, index 68) is the balanced outsider: 4th on votes (50,237), 982 German YouTube comments (3rd), but only 31 Amazon products. Hinata (rank 6, index 51) carries two warnings — `ambiguous_name` plus `excluded_source` (her Amazon matches were dropped for low precision) — so her shop footprint (317 eBay items) should be read with caution.

## 4. Momentum (Google Trends DE, 20 quarters 2021-Q4 → 2026-Q3, `partial_last: false`)

Google search data is low-resolution for individual characters, because every request is dominated by the term 'Naruto'; it is used only where it passes the archive's censoring test (Sasuke, Itachi, Kakashi, Hinata). Momentum rule: a `change_12m` percentage is only described as a rise or fall
when its 12-month point move clearly exceeds Google's integer rounding;
smaller moves read "flat within Google's resolution" (the weekly values
behind the quarterly means are integers, so small `change_12m` percentages
are rounding noise, not signal). Sasuke (−3.6%) and Itachi (−4.2%) move only
−0.15/−0.14 index points over the last 12 months — flat within the
resolution. Kakashi (−16.8%, −0.48 pts) and Hinata (−18.7%, −0.69 pts,
flagged `ambiguous_name`, so her trend is the least trustworthy) move
several times the noise floor and show real declines. Madara and Minato are
flagged `censored`: their search trends sit at Google's integer floor and
are too low to read — no rise or fall may be claimed for them (Minato's
+8.6% `change_12m` is a floor artefact, not a riser). Scale note: values are on the shared reference scale where the search term 'Naruto' = 37.73.

## 5. Google searches by state (`regions_trends`, context only)

Searches for "Naruto" (single-term request, strongest state = 100): Bremen 100,
Sachsen-Anhalt 96, Niedersachsen 90 … Baden-Württemberg 73, Bayern 65; every
state lies between 65 and 100. Candidate shares of their own Google requests
are whole percent and barely move between states: Sasuke 5–7%, Kakashi 3–5%
(flat, within 2 points); Itachi 5–8% with its high in Nordrhein-Westfalen is a
hint, not a finding; Hinata is ambiguous; Pain/Nagato has no regional series.

## 6. What this cannot tell you

No sales or revenue: no source measures units sold. Language is not residence: "German" signals mean German-language activity, not proven residence in Germany. Merchandise mix is not drink demand: eBay mix for the top sellers is figures/clothing/cards-heavy (e.g. Sasuke: 199 figures, 120 clothing, 89 cards of 623 items), which does not predict energy-drink flavours. Do not use YouTube's own view/like statistics — the release carries only project-computed German comment/video counts as of `youtube_snapshot: 2026-10-22`.

## 7. Recommended next step

Run a post-launch scorecard on first-party sales data: for whichever of the top 3 is launched first, track sell-through, repeat purchase and product-line performance per character against these pre-launch indices, then decide whether to extend to Madara or Minato. The archive cannot answer that; only sales data can.

## 8. Compared with Naruto (fair sources only)

Only 1 of 9 sources allows a fair candidate-vs-Naruto comparison
(ANALYSIS_PLAN.md §13 with the §12 entry of 2026-10-23): the NARUTOP99 Europe
vote (direct vote counts; Europe, not Germany only). Kleinanzeigen is not
comparable because the archive tagger counts Naruto only on "Uzumaki"/"Naruto
Uzumaki" (his count is narrowed); German YouTube comments are not comparable
because Naruto's precision 0.93 rests on 14 labels (95% CI from 0.69).
Amazon and eBay fail on Naruto precision (0.74/0.66); Google Trends tracks
the franchise, not the character (r = 0.94 with the franchise topic);
Anime2You narrowed Naruto's matching; YouTube videos and Anime2You articles
have no measured Naruto baseline.

Wording rule (§13): "reaches X% of Naruto's …", never "more popular than Naruto".
Band rule (§12): ratios between 0.95 and 1.05 read "about the same as Naruto"
— Sasuke 0.9954 and Obito 0.9754 (unrounded).

- **Minato** reaches 640% of Naruto's Europe vote (223,694 vs 34,959),
  **Itachi** 370% (129,376), **Kakashi** 145% (50,773), **Madara** 144% (50,237).
- **Sasuke** (34,797) and **Obito** (34,098) are about the same as Naruto.
- Everyone else trails: Jiraiya 87%, Hinata 79%, Shikamaru 55%, Gaara 39%,
  Orochimaru 29%, Pain/Nagato 19%, Tsunade 17%.
- One source cannot rank candidates against Naruto overall; it shows that the
  fan favourites in Europe (Minato, Itachi) are not the shop leaders.

## 9. Deutsche Zusammenfassung

Sasuke Uchiha (Index 93), Itachi Uchiha (89) und Kakashi Hatake (83) zeigen die stärkste Evidenz für Potenzial in Deutschland — alle mit der Konfidenzstufe „robust". Sasuke führt bei eBay (623 Artikel) und deutschen YouTube-Kommentaren (1.405). Itachi überzeugt über alle Quellen (129.376 Europavotes, 1.104 Kommentare, 562 eBay-Artikel), Kakashi über eBay (475), allerdings mit eingeschränkter Keyword-Präzision. Das Ergebnis ist stabil: Alle sieben Leave-one-out-Läufe und alle drei Alternativgewichtungen behalten dieselben Top 3, die Übereinstimmung der Quellen ist stark. Minato gewinnt nur die europäische Fan-Abstimmung (223.694 Stimmen, 6,4× Narutos Wert), nicht die Shops, und sein Suchtrend ist zensiert (zu niedrig zum Ablesen). Fair mit Naruto vergleichbar ist nur die Europa-Abstimmung (NARUTOP99): Minato erreicht 640 % von Narutos Stimmen, Itachi 370 %, Kakashi 145 %, Madara 144 %; Sasuke und Obito liegen etwa gleichauf. Kleinanzeigen (Naruto nur als „Uzumaki“ getaggt) und deutsche YouTube-Kommentare (Präzision aus nur 14 Labels) sind nicht vergleichbar. Google-Suchen nach Bundesland: Bremen 100, Bayern 65; die Kandidaten-Anteile sind zwischen den Ländern praktisch gleich.
