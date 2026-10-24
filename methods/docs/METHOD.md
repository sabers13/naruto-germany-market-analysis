# Method and interpretation

This companion demonstrates selected analysis techniques. It is not the frozen protocol of the completed market study.

1. **Validate aggregate inputs.** Reject duplicate entity/source cells, unknown sources, negative or non-finite values, invalid weights, and invalid coverage. Keep null distinct from zero.
2. **Assess match quality where provided.** Precision is `correct / total`. Report its Wilson 95% interval. Use the point estimate unchanged at precision >= 0.90; multiply the metric by precision at 0.70 <= precision < 0.90; exclude the cell below 0.70. A supplied source-wide assessment below 0.50 stops the build. These are explicit heuristic policies, not confidence-bound decisions. No quality assessment means `unassessed`.
3. **Rank within each active source.** Higher values receive better ranks. Tied values receive average ranks. Missing and excluded cells are not ranked.
4. **Aggregate within lenses.** Take the mean of observed source ranks when an entity covers at least `ceil(minimum_lens_coverage * active_sources_in_lens)` sources. Otherwise the lens is null. Coverage denominators use active sources in each scenario, so source removal can change eligibility; inspect the per-run results accordingly.
5. **Combine lenses.** Compute a weighted mean over available positive-weight lenses, renormalizing their weights. Smaller scores indicate stronger relative evidence. Average-tied scores retain tied overall ranks; entity identifiers order tied display rows alphabetically.
6. **Form an index.** For N entities, `100 * (N - score) / (N - 1)`. For a single entity the index is undefined and exported as null. It is an index, not a percentage chance of sales. Different source coverage can distort comparisons even when the result is in [0, 100].
7. **Stress-test.** Drop each configured source once and rerun. Repeat with caller-supplied alternative weights. Compare top-k membership as sets; report alphabetical tie-breaking at the top-k boundary. These are descriptive checks, not inferential confidence estimates.
8. **Measure agreement.** Compute tie-corrected Kendall's W across sources on complete cases. Re-rank that subset before calculation. Report the numbers of entities and sources. Fewer than two sources or entities, or a zero tie-corrected denominator, gives null rather than false certainty.
9. **Export deterministically.** Sort metric/quality rows for provenance, canonicalize JSON, and hash inputs, configuration, quality assessments, and the resulting payload. There is no runtime timestamp in the release.

Known limitations include non-random inputs, source selection, matching bias, uncertain quality estimates, differing source coverage, and the loss of raw magnitude in ranking. Wilson intervals describe precision sampling uncertainty under their usual assumptions; that uncertainty is not propagated through the index. No significance or causal claim is made.
