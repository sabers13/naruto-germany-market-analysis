# Independent spot-check

Phase 1 labelling and review were done by the same model family that wrote the matching rules. To close that independence gap (`ANALYSIS_PLAN.md` §6.3 and the §12 entry of 2026-10-23), a different model family re-labelled a subset blind: it saw the match context, not the first labeller's label. Labels only, no snippets.

## Method

- 72 items from the phase 1 sample, labelled with the same four values: `correct`, `wrong_character`, `not_naruto`, `unclear`.
- Exact agreement: identical labels. Binary agreement: `correct` against everything else.
- Cohen's κ is computed on the binary grouping.

## Agreement (n = 72)

| Metric | Value |
|---|---|
| Exact agreement | 70/72 = **0.972** |
| Binary agreement (correct vs not) | 70/72 = **0.972** |
| Cohen's κ (binary) | **0.911** |

The two disagreements were one eBay match (first labeller `wrong_character`, second `correct`) and one Amazon match (`correct` against `unclear`).

## Treatment decisions unchanged

- The eBay disagreement sits in a stratum with precision 9/10 = 0.90 (`use`); with the second label it would be 10/10, still `use`.
- The Amazon disagreement sits in a stratum with precision 23/31 ≈ 0.742 (`adjust`); with the second label it would be 22/31 ≈ 0.710, still `adjust`.
- The other 70 items agree, so no other stratum changes. Every treatment decision in `precision.csv` stands.
