# Architecture and implementation boundaries

## Components

| Component | Input | Output | Responsibility |
|---|---|---|---|
| CLI (`__main__.py`) | Local JSON paths | Local JSON file | File IO and command-line errors |
| Validation (`checked_config`, `prepare`) | Aggregate metrics, source registry, quality counts | Validated adjusted cells | Fail on ambiguous duplicate cells, invalid values, or invalid configuration |
| Quality (`wilson`) | Correct/total labelled examples | Precision and 95% interval | Quantify matching precision; never infer it from the demo's invented values |
| Ranking (`rank_run`) | Adjusted cells, active sources, lens weights | Scores, source/lens ranks | Preserve missingness, apply coverage gates, normalize available weights |
| Robustness (`build_report`, `kendall_w`) | Validated cells and configuration | Source-drop and weight scenarios; agreement | Expose sensitivity and complete-case sample size |
| Release (`canonical_bytes`, `digest`) | JSON-compatible values | Stable bytes and SHA-256 | Reproducibility without wall-clock fields |

Pure functions separate calculations from the CLI. There is no import of the original backend, no sibling-directory lookup, no collector, and no connection to a data archive. The only standard-library dependencies are shipped with Python.

## Data flow and contracts

One metric row is `{entity, source, value}`. Each entity/source pair appears at most once. Inputs are already aggregated; record-level deduplication and extraction are upstream responsibilities. Null means unobserved, while numeric zero is a valid observed metric.

Configuration maps each source to one lens and provides nonnegative lens weights. Source names are arbitrary identifiers. This implementation accepts higher-is-stronger, nonnegative metrics. It does not silently mix counts and prices or claim that relative ranks have a common underlying unit.

Quality rows supply `{source, entity?, correct, total}`. Omitted entity or `"*"` means source-level fallback; entity-level assessments take precedence. Missing quality is labelled `unassessed`, not assumed precise.

The output contains version identifiers, provenance hashes, rankings, source and lens diagnostics, robustness runs, quality assessments, and explicit limitations. `release_id` hashes the full payload before the release ID is added. Floating-point results are deterministic in the supported environment; use the CI environment for byte-for-byte comparison across releases.

## Engineering tradeoffs

- A small standard-library implementation makes the demonstration portable. A production large-table pipeline could retain the original project's pandas/DuckDB/Parquet stack; this companion does not claim to implement that storage layer.
- Rank aggregation avoids mixing raw units but discards magnitude differences and does not fix selection bias or unequal source coverage.
- Source and quality configuration are explicit inputs. Provenance proves which inputs produced a release; it does not prove their truth or grant a data licence.
- Tests use invented examples and hand-calculated answers. They do not access the original report or archive.
