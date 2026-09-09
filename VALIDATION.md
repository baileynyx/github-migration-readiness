# Validation

## Six-repository sample assessment

September 9, 2026: local validation with Python 3.12.14 passed all **15 tests** using `python -m unittest discover -s tests -v`. The original 12 assessment tests remain; three new tests check the sample's six outcomes and discovery gaps, reproduction of both committed report formats through the CLI, and blocking exit codes with reports still written.

The CLI generated [JSON](examples/migration-assessment/readiness.json) and [Markdown](examples/migration-assessment/readiness.md) directly from the [fictional inventory](examples/migration-assessment/inventory.json): **1 blocker, 1 unknown, 3 review, 1 ready**. `--fail-on never` returned 0; both `--fail-on blocker` and `--fail-on unready` returned 1 as expected. No report was hand-edited.

The workflow also generates the full sample under `reports/migration-assessment/` and includes it in the existing report artifact. Hosted results should be checked on the PR's exact commit; the local results above do not claim a hosted run.

The [scenario](docs/sample-assessment.md) and [runbook](docs/migration-runbook.md) describe proposed acceptance work. No source-provider data collection, repository migration, target security check or recovery rehearsal was performed.

## Original baseline

September 9, 2026: `python -m unittest discover -s tests -v` passed all **12 tests**. Coverage includes explicit clean inventories, unknown data, missing default refs, unresolved identities, malformed types, unsupported fields, duplicate names, empty inventories, review-only findings, deterministic sorting, safe Markdown rendering and CLI exit behavior.

The example CLI completed and generated `examples/readiness.json` and `examples/readiness.md` with one blocker, one unknown and one ready inventory. `--fail-on never` was used because the example deliberately contains findings.

The [first hosted inventory workflow](https://github.com/baileynyx/github-migration-readiness/actions/runs/34357954317) passed for source commit `03efbe8da6d4047a752cbdb9396ee286f7f6c60b`: the test suite, synthetic report generation and report artifact upload completed successfully. No provider inventories were collected and no repositories were migrated. The test suite establishes behavior for the documented normalized contract, not completeness of an external export.
