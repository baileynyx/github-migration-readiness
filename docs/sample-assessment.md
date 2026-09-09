# Sample assessment: a six-repository migration wave

**Independent portfolio exercise by Bailey Fitchett. All repositories, teams and dependencies below are fictional.**

The scenario is an Azure DevOps Cloud Git estate being assessed for a move to GitHub Enterprise Cloud. Source product and target selection are human planning context, not fields the CLI verifies. Nothing was exported from an organization or migrated.

## Read the evidence

1. Inspect the normalized [inventory](../examples/migration-assessment/inventory.json).
2. Open the generated [Markdown assessment](../examples/migration-assessment/readiness.md) or [JSON assessment](../examples/migration-assessment/readiness.json).
3. Use the decisions below to plan discovery and rehearsal, then follow the [migration runbook](migration-runbook.md).

The inventory produces **1 blocker, 1 unknown, 3 review, and 1 ready** repository. These are repository counts, not finding counts. Each finding carries a resolution, and the most severe finding determines the repository's displayed status. A blocker can therefore coexist with review findings.

## Turn findings into work

| Repository | Result | Accountable role and next action | Evidence required before advancing |
| --- | --- | --- | --- |
| `synthetic-catalog-api` | ready | Catalog team: nominate this small, dependency-free inventory as the initial pilot candidate. | Rehearsal export/import reconciliation, target permissions and branch-rule checks, and an application build result. A clean inventory is not cutover approval. |
| `synthetic-legacy-orders` | blocker | Migration lead: establish an accountable application owner; that owner reconciles `master` against observed `main`/release branches and resolves the former contributor. Build engineering maps the hook, Windows agent and feed. | Approved owner, corrected default-ref evidence, identity decisions with permission checks, and successful target hook/build/feed exercises. Fixing identity alone leaves other findings. |
| `synthetic-media-assets` | review | Content team: inventory LFS object IDs and sizes and rehearse object transfer separately. | Source/destination LFS inventory reconciliation and a fresh clone that materializes the required assets. Matching Git pointers alone is insufficient. |
| `synthetic-release-tools` | review | Release engineering: map the service connection, production approval, shared template and notification hook to the chosen target delivery model. | A non-production release rehearsal, scoped target credentials, an approval enforcement check and exactly one expected hook notification. |
| `synthetic-audit-archive` | review | Records team: decide whether the archive belongs in this wave and retain its read-only intent. | Documented scope/retention decision, reconciled history, and a target access check preventing ordinary contributors from writing. |
| `synthetic-undiscovered-worker` | unknown | Integration team: collect branches, LFS usage, hooks, pipeline dependencies and unresolved identities. | Source evidence for all five unknown fields; use an empty list only after confirming absence. Rerun the assessment after collection. |

The first pilot should establish the basic procedure with the catalog repository. Later rehearsals must also exercise LFS and delivery dependencies; one uncomplicated pilot cannot validate the entire estate. Keep the orders repository out of cutover until its blockers are resolved, and keep the worker in discovery until its unknowns are resolved.

## Security requirements belong in the acceptance record

The current schema does not inspect repository contents, GitHub settings, permissions or credentials. The following are **required checks in the fictional plan, not findings produced by the CLI**.

| Requirement | Responsible role | Acceptance evidence |
| --- | --- | --- |
| Intended visibility and least-privilege team access | Repository owner and identity administrator | Approved access mapping plus positive and negative tests with representative target users; ownership tags/names alone grant nothing. |
| Protected changes and release approvals | Platform and release engineering | Review and status-check enforcement on the intended branches; an attempted unapproved non-production deployment is denied. |
| Credentials and service connections | Security and integration owners | Scoped target credentials or approved federation, tested service access, and a recorded revocation plan for obsolete migration credentials. No secret values in the assessment. |
| History and dependency scanning | Security and application owners | Verify applicable security features are available and enabled, review scan coverage and unresolved alerts, and assign remediation or explicit risk acceptance. A scan without alerts is not proof that history contains no secrets. |
| External integrations | Hook and pipeline owners | Correct target endpoint, authentication, event delivery and duplicate-trigger behavior verified in rehearsal. |

Secret scanning is a separate GitHub capability, not part of this offline program. Its coverage and availability must be checked for the target. See [GitHub's secret scanning documentation](https://docs.github.com/en/code-security/concepts/secret-security/secret-scanning).

## Interpret the gate honestly

`--fail-on never` permits report generation for this deliberately mixed sample and exits 0. Both `--fail-on blocker` and `--fail-on unready` exit 1 for this inventory.

An LFS-using or archived repository can remain `review` even after humans complete its acceptance work: the schema stores observed facts, not signed-off exceptions. Do not change `uses_lfs` to false or erase real dependencies to make a gate green. Record the disposition and evidence separately. A strict gate remains conservative; a human release decision is an additional control.

A `ready` result means only that this contract found no issue in the supplied inventory. The CLI cannot approve a migration or verify that source evidence is current.

[Back to README](../README.md) · [Runbook](migration-runbook.md)

