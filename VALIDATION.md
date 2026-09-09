# Validation

September 9, 2026: `python -m unittest discover -s tests -v` passed all **12 tests**. Coverage includes explicit clean inventories, unknown data, missing default refs, unresolved identities, malformed types, unsupported fields, duplicate names, empty inventories, review-only findings, deterministic sorting, safe Markdown rendering and CLI exit behavior.

The example CLI completed and generated `examples/readiness.json` and `examples/readiness.md` with one blocker, one unknown and one ready inventory. `--fail-on never` was used because the example deliberately contains findings.

GitHub Actions has not run yet. No provider inventories were collected and no repositories were migrated. The test suite establishes behavior for the documented normalized contract, not completeness of an external export.
