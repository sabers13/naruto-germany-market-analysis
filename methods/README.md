# Naruto Germany — reproducible analysis methods

A standalone engineering companion to the completed [Naruto Germany market analysis](https://github.com/sabers13/naruto-germany-market-analysis). It demonstrates how heterogeneous evidence can be validated, quality-adjusted, ranked, stress-tested, and exported reproducibly.

**Every bundled input and result is synthetic.** The six demonstration entities (`candidate_a` through `candidate_f`) and five source names are invented. The example does not reproduce the study's character ranking or establish any market finding.

## What a reviewer can inspect

| Capability | Implementation |
|---|---|
| Input validation | Unique entity/source cells; finite nonnegative metrics; validated lens coverage and weights |
| Quality assessment | Observed match precision, Wilson 95% intervals, explicit adjustment/exclusion thresholds |
| Evidence synthesis | Average ranks within sources, lens aggregation, weighted index; missing stays null |
| Sensitivity analysis | Drop each source; change lens weights; report top-set changes and boundary ties |
| Agreement | Tie-corrected Kendall's W on re-ranked complete cases, with sample size |
| Reproducibility | Canonical JSON, input/config/quality SHA-256 hashes, content-addressed releases |
| Verification | Hand-calculated statistical cases, failure cases, CLI and deterministic output tests |

## Run in under a minute

Python 3.12 or newer; no runtime dependencies, credentials, archive, or network access required.

```bash
cd methods
make demo
make test
```

Without Make, from the `methods/` directory:

```bash
PYTHONPATH=src python3 -m market_methods \
  --metrics examples/metrics.json \
  --config examples/config.json \
  --quality examples/quality.json \
  --out /tmp/market-methods-demo.json
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The CLI can also be installed locally with `python3 -m pip install .`, then called as `market-methods`. Installation may download build tooling; the commands above run directly from source.

## Architecture

```text
Local aggregate metrics + source/lens configuration + optional quality counts
                              |
                validate identities, values and coverage
                              |
            assess precision -> adjust / exclude / stop
                              |
              source ranks -> lens ranks -> evidence index
                              |
          leave-one-source-out + alternative weights + agreement
                              |
             canonical JSON report + provenance + release hash
```

The package starts at the **aggregate input boundary**. Collectors, platform access, raw records, and the original dashboard deployment are outside this implementation. See [architecture](docs/ARCHITECTURE.md), [method](docs/METHOD.md), and [publication scope](docs/PUBLICATION_SCOPE.md).

## Relationship to the original study

This is a new, source-configurable implementation of selected ideas from the private analysis backend: rank aggregation, quality controls, robustness checks, and reproducible releases. It is not a byte-for-byte extraction or an exact reproduction of the frozen study protocol. Its API, entity count, source configuration, tie handling, and agreement reporting are deliberately independent of the study release.

The companion can run entirely on invented inputs. It makes no claim that source restrictions disappear through aggregation, that a research label grants permission, or that a metric index predicts purchases.

## Resume wording

> Built a reproducible Python analysis pipeline for a Germany-focused market study, with quality-aware rank aggregation, missing-data handling, sensitivity analysis, and content-addressed JSON exports; published a tested methods companion using synthetic data.

The statistical approach and implementation can be discussed independently of the original datasets.

## Licence

MIT for this implementation and documentation, see [LICENSE](LICENSE). Synthetic examples were authored for this companion. No Naruto artwork, platform content, or third-party datasets are included. The project name identifies the associated study and does not imply endorsement.
