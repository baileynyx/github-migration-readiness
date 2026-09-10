# Validation

## Visual rehearsal evidence

September 10, 2026: `python tools/render_ref_demo.py --output-dir docs/assets/ref-demo` completed a fresh real-Git rehearsal and rendered its observed results into a four-frame, 30-second GIF and static summary. The intact copy matched 5 records; the changed copy reported 2 matched, 1 missing, 1 unexpected and 2 mismatched records. The source refs remained unchanged. Full captures, reports, execution evidence and source/asset hashes are retained under [docs/assets/ref-demo](docs/assets/ref-demo/transcript.md).

All four rendered frames were visually inspected for readable text, correct counts and unclipped IDs. GIF inspection confirmed four frames, 30,000 ms total presentation duration and no repeat extension. This is a presentation of captured synthetic evidence; its timing is not measured execution duration. The existing 50-test suite passed after this presentation-only change. No additional unit tests or live provider operations were introduced. See the [reproduction guide](docs/ref-demo.md).

## Git ref verification

September 10, 2026: local validation passed **50 tests**, comprising the previous 32 and 18 ref-verification tests. Coverage includes missing/unexpected/mismatched refs, annotated-tag objects and peeled targets, case-sensitive names, SHA-1/SHA-256 handling, malformed/duplicate/out-of-scope records, size limits, Markdown escaping, input/output gates and reproduction of the committed synthetic reports.

The standalone `rehearse_refs.py` run used actual local Git commands against two disposable bare repositories. The intact copy returned comparator exit **0** with **5 matched records**. After deliberate destination changes, comparison returned **1** with **2 matched, 1 missing, 1 unexpected and 2 mismatched records**. A changed annotated-tag message was detected while its peeled target still matched. The source advertisement remained unchanged; temporary repositories were removed. The rehearsal returned 0 because both expected outcomes were verified.

CI runs the same rehearsal, publishes its difference report in the job summary and includes captures, JSON/Markdown reports and timestamped evidence in the existing synthetic-report artifact. Hosted status must be checked for the PR's actual commit. These local results do not claim a hosted run or a real provider migration. Matching supplied refs does not prove object availability, capture provenance or operational acceptance. See the [walkthrough and limits](docs/ref-verification.md).

## Read-only Azure DevOps collector

The local suite passed **32 tests**: 15 existing assessment/sample tests and 17 collector tests using synthetic HTTP responses. New coverage includes complete refs pagination, later-page 403/404 handling, missing facts, malformed/duplicate evidence, authentication failure, repeated tokens/page limits, bounded retries, HTTP 200 pacing, Retry-After dates/budgets, fixed-host GET requests, redirect refusal, diagnostic redaction and output-directory protection.

The public fixture CLI collected two fictional repositories and generated schema-version-1 inventory. Passing that inventory into `readiness.py` produced **1 blocker, 1 unknown, 0 review, 0 ready**. Tests regenerate the committed inventory plus JSON/Markdown reports and compare content. The workflow now generates this evidence alongside the earlier examples and uploads it in the existing report artifact.

No live Azure DevOps organization, PAT, project or repository was accessed. Authentication and network behavior were exercised with mocked transports; hosted CI should be verified for the exact PR commit. The collector cannot establish full project visibility, accountable owners, archive intent, LFS, hooks, pipeline dependencies or target identity mappings from its two endpoint families.

## Six-repository sample assessment

September 9, 2026: local validation with Python 3.12.14 passed all **15 tests** using `python -m unittest discover -s tests -v`. The original 12 assessment tests remain; three new tests check the sample's six outcomes and discovery gaps, reproduction of both committed report formats through the CLI, and blocking exit codes with reports still written.

The CLI generated [JSON](examples/migration-assessment/readiness.json) and [Markdown](examples/migration-assessment/readiness.md) directly from the [fictional inventory](examples/migration-assessment/inventory.json): **1 blocker, 1 unknown, 3 review, 1 ready**. `--fail-on never` returned 0; both `--fail-on blocker` and `--fail-on unready` returned 1 as expected. No report was hand-edited.

The workflow also generates the full sample under `reports/migration-assessment/` and includes it in the existing report artifact. Hosted results should be checked on the PR's exact commit; the local results above do not claim a hosted run.

The [scenario](docs/sample-assessment.md) and [runbook](docs/migration-runbook.md) describe proposed acceptance work. No source-provider data collection, repository migration, target security check or recovery rehearsal was performed.

## Original baseline

September 9, 2026: `python -m unittest discover -s tests -v` passed all **12 tests**. Coverage includes explicit clean inventories, unknown data, missing default refs, unresolved identities, malformed types, unsupported fields, duplicate names, empty inventories, review-only findings, deterministic sorting, safe Markdown rendering and CLI exit behavior.

The example CLI completed and generated `examples/readiness.json` and `examples/readiness.md` with one blocker, one unknown and one ready inventory. `--fail-on never` was used because the example deliberately contains findings.

The [first hosted inventory workflow](https://github.com/baileynyx/github-migration-readiness/actions/runs/34357954317) passed for source commit `03efbe8da6d4047a752cbdb9396ee286f7f6c60b`: the test suite, synthetic report generation and report artifact upload completed successfully. No provider inventories were collected and no repositories were migrated. The test suite establishes behavior for the documented normalized contract, not completeness of an external export.
