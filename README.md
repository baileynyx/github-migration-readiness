# GitHub migration readiness

An offline Python assessment tool for source-control migration planning. It highlights missing ownership, ref mismatches, identity gaps, and dependencies that need deliberate cutover work.

**Scope:** normalized inventory assessment, using synthetic examples. It does not collect provider data or migrate repositories.

## Try it in two minutes

Requires Python 3.11 or later; no packages, credentials, or cloud resources.

```shell
python readiness.py examples/inventory.json --output-dir reports --fail-on never
python -m unittest discover -s tests -v
```

Read `reports/readiness.md` or the committed [sample report](examples/readiness.md). The sample has one blocker, one unknown repository, and one repository with no findings.

For a CI inventory gate, use `--fail-on unready`: exit 0 means all inventories have no findings, 1 means findings need attention, and 2 means input or output failed. `--fail-on blocker` is the default and permits review/unknown outcomes; use the stricter gate before cutover.

## Input contract

The root contains integer `schema_version: 1` and a nonempty `repositories` array. Repository names must be unique, ignoring case. Unsupported repository fields fail validation so typos cannot silently change an assessment.

| Field | Type | Meaning |
| --- | --- | --- |
| name | Nonempty string, required | Stable repository identifier |
| owner | String | Accountable target owner; empty blocks |
| default_branch | String | Intended default branch; empty blocks |
| branches | String list | Observed branch names; absent default ref blocks |
| archived | Boolean | True requires scope review |
| uses_lfs | Boolean | True requires separate object transfer verification |
| hooks | String list | Hooks to recreate and test |
| pipeline_dependencies | String list | Agents, feeds, service connections or dependent jobs |
| unmapped_identities | String list | Unresolved identities; nonempty blocks |

Except for `name`, missing/null values are unknown, never a pass. Explicit empty lists mean observed absence. Each repository takes the highest finding category: blocker, unknown, review, then ready. A ready result covers only this inventory contract, not every migration risk.

## Why this design

Normalization separates provider collection from assessment. Deterministic reports are easy to diff in review. No network client or credentials are needed. Field-level resolutions explain the next action rather than reduce a migration to a misleading percentage score.

## Rehearsal and cutover

1. Confirm scope, owner, destination, and the meaning of every unknown field.
2. Capture source refs and LFS inventory. Rehearse import into an isolated destination.
3. Compare `git ls-remote --heads --tags` output, including annotated-tag object and peeled refs. Check LFS objects from a fresh clone.
4. Validate issues, identities, permissions, branch rules, hooks, pipelines, agents and feeds independently; matching Git refs does not prove those moved.
5. Agree a write freeze and fallback criteria. Reconcile final refs, run pipeline smoke tests, then change source-of-truth links.
6. Keep the source read-only during the agreed observation window. If fallback is needed, reconcile post-cutover writes before reopening it; do not create two writable sources of truth.

## Evidence and limits

See `VALIDATION.md` for executed checks. There are no live provider collectors, migrations, employer assets, or invented operational metrics. Next useful extension: a read-only Azure DevOps collector with pagination, retry handling, and explicit unknowns for unavailable fields.
