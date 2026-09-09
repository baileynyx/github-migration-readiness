# Validation

September 9, 2026: `python -m unittest discover -s tests -v` passed all **12 tests**. Coverage includes explicit clean inventories, unknown data, missing default refs, unresolved identities, malformed types, unsupported fields, duplicate names, empty inventories, review-only findings, deterministic sorting, safe Markdown rendering and CLI exit behavior.

The example CLI completed and generated `examples/readiness.json` and `examples/readiness.md` with one blocker, one unknown and one ready inventory. `--fail-on never` was used because the example deliberately contains findings.

The [first hosted inventory workflow](https://github.com/baileynyx/github-migration-readiness/actions/runs/34357954317) passed for source commit `03efbe8da6d4047a752cbdb9396ee286f7f6c60b`: the test suite, synthetic report generation and report artifact upload completed successfully. No provider inventories were collected and no repositories were migrated. The test suite establishes behavior for the documented normalized contract, not completeness of an external export.
