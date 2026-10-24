# Analysis pipeline

The reproducible analysis behind the [Naruto × Germany dashboard](../README.md): which Naruto characters show the strongest evidence of potential to sell in Germany, and how sure the answer is.

**Plan first, results second.** [`ANALYSIS_PLAN.md`](ANALYSIS_PLAN.md) fixed every cleaning rule, metric, weight and stop rule before any result existed. Later changes are listed in its amendments section, each with a date and a reason. The results are in [`reports/FINDINGS.md`](reports/FINDINGS.md).

## Pipeline

```text
local source archive (read-only, pinned commit)
        |
  four lanes: shops | fans (text) | trends | votes
        |   one long metrics table; distinct entities, never raw rows
        |
  accuracy check: sample matches, hand labels, Wilson intervals
        |   adjust or drop low-precision (source, character) cells
        |
  scoring: ranks within source -> lens ranks -> weighted evidence index
        |
  robustness: leave-one-source-out, alternative weights, Kendall's W
        |
  benchmark comparison with Naruto, on fair sources only
        |
  release: schema-validated JSON, content-addressed id, input hash,
           privacy check (no URLs, titles or long snippets)
        |
  public edition: Kleinanzeigen figures removed
```

| Package | Purpose |
|---|---|
| `nga.shops`, `nga.fans`, `nga.trends`, `nga.votes` | One lane per kind of evidence. Each writes rows to the shared metrics table |
| `nga.accuracy` | Keyword-precision sample, scoring and treatment rules |
| `nga.scoring` | Ranking, evidence index, robustness runs, confidence labels |
| `nga.benchmark` | Fair "compared with Naruto" ratios |
| `nga.release` | Release build, provenance, privacy check, public edition |
| `contract/` | JSON Schema the release must satisfy |
| `config/` | Locked character dictionary and German state map |

## Run it

Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
make test    # unit tests on synthetic inputs; archive tests skip without the archive
make demo    # builds a full and a public release from synthetic inputs
```

The full pipeline (`make all`) needs the private source archive, which is not part of this repository. See [`docs/DATA_ACCESS.md`](docs/DATA_ACCESS.md).

## Scope

This directory publishes code, the written plan, aggregate accuracy results and the findings report. It does not publish collection code, raw or row-level data, or the archive. The [`methods/`](../methods/README.md) companion is a separate, generalised implementation with invented inputs; this pipeline is the study's own.
