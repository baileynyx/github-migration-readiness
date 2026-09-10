# Migration runbook: discovery through recovery

This is a proposed operating procedure for the [fictional six-repository assessment](sample-assessment.md). No live migration, customer outcome or recovery timing is claimed. Executable walkthroughs cover offline assessment, synthetic collector replay and ref verification using disposable local Git repositories.

## 1. Discover and define the scope

The migration lead and application owners record source product/version, Git versus TFVC, target product, repositories, desired visibility, accountable owners and evidence collection time. Agree which Git history and platform metadata must survive. Record exclusions explicitly, including archived repositories.

Choose the migration route after confirming that scope. For this scenario, GitHub Enterprise Importer supports Azure DevOps **Cloud** to GitHub Enterprise Cloud; do not assume the same route works directly for Azure DevOps Server. Git LFS objects require follow-up transfer. Check the current [supported data and limitations](https://docs.github.com/en/migrations/ado/understand-migrations-from-azure-devops-to-github) before a real rehearsal.

Capture refs, LFS objects, pull-request/work-item requirements, identity mappings, access rules, hooks, pipelines, agents, feeds and service connections. Retain the source evidence in controlled storage and normalize only the supported facts into the assessment JSON. Missing evidence remains null or omitted.

**Gate:** every in-scope repository has an accountable owner, a supported route and a defined preservation contract. Assign each unknown or blocker an owner and a closure action before scheduling cutover.

## 2. Assess and prepare the destination

Run the [README commands](../README.md#walk-through-a-complete-sample-assessment) and review every finding, including findings below the displayed highest status. Associate each disposition with the inventory revision, evidence location, reviewer and decision date.

The identity administrator and repository owner approve target visibility, teams and permission levels. Platform engineering specifies branch protections, review rules and permitted integrations. Security and integration owners implement the [sample's security acceptance requirements](sample-assessment.md#security-requirements-belong-in-the-acceptance-record).

Decide whether to retain Azure Pipelines with GitHub-hosted repositories or convert delivery separately. GitHub Actions Importer offers an Azure DevOps pipeline conversion path, but secrets, service connections, agents and approvals require additional manual work; do not infer pipeline readiness from repository import. See the [Actions Importer guidance](https://docs.github.com/en/actions/migrating-to-github-actions/automated-migrations/migrating-from-azure-devops-with-github-actions-importer).

**Gate:** owners accept the target design and scope. A security feature or scan is recorded as verified only after its actual coverage and configuration are checked.

## 3. Rehearse in an isolated destination

Start with the catalog pilot, then rehearse representative LFS and delivery-dependent repositories. Use migration credentials with the access required by the selected tool and record their revocation owner. Prevent the rehearsal destination from triggering production deployments or sending production integration events.

Capture source refs at a recorded point, execute the chosen import, retain logs and investigate warnings. For Git data, compare branch and tag names and object IDs, including annotated-tag objects and peeled refs. Verify the destination default branch explicitly. If an intentional history transformation changes IDs, agree a different reconciliation method and document the mapping before acceptance.

Use the [ref verification walkthrough](ref-verification.md) to compare captured advertisements and retain JSON/Markdown differences. Its [synthetic example](../examples/ref-verification/refs.md) demonstrates a missing branch, destination-only work, a changed branch and a changed tag annotation with the same peeled target. A ref match alone does not satisfy this stage's acceptance gate.

Compare required metadata separately: reconcile exported/imported counts and inspect representative historical and recent pull requests, comments, attachments and work-item links as applicable to the preservation contract. Document unsupported or intentionally excluded data; matching Git refs cannot establish metadata completeness.

Transfer and verify LFS objects from a fresh clone. Test builds, feed access, notifications, target-user permissions, branch-rule enforcement and release approvals in non-production. The application owner signs off the result and records unresolved issues.

**Gate:** the reconciliation has no unexplained differences and representative operational/security checks pass. Record observed duration and failure points only after execution; this exercise supplies no measured timing.

## 4. Authorize and execute cutover

Before the change window, the migration lead names the decision maker, participants, freeze window, observation window, recovery point, acceptable data-loss/recovery objectives and abort deadline. Define abort criteria: unexplained ref/object differences, missing required metadata, broken authorization, failed critical builds or missing LFS assets.

Confirm the chosen route's behavior for writes during import; establish the planned source write freeze and suspend duplicate build/webhook triggers. Capture final source evidence, verify the freeze, perform the final import or tool-supported reconciliation, and retain logs. Do not assume an importer supports incremental updates; decide and rehearse its final-run procedure first.

Repeat final data reconciliation and the security/delivery acceptance checks. The migration lead and application owner authorize changing developer remotes, documentation, integration endpoints and delivery references to the destination. Keep the former source read-only through observation.

**Gate:** required checks are evidenced, unresolved exceptions are explicitly accepted by the appropriate owner, and there is exactly one writable source of truth. A CLI exit code alone cannot authorize this transition.

## 5. Observe and hand over

Application and platform owners monitor clone/fetch/push, pull requests, CI, release approvals, LFS retrieval and hook delivery for the agreed window. Record failures, support ownership and escalation routes. Verify old integrations no longer trigger duplicate work.

Retain evidence according to the agreed access and retention rules. Revoke temporary migration access when no longer needed, then complete the source archival/retirement decision after acceptance. Do not remove recovery evidence merely because the first build passes.

**Gate:** the application owner accepts the destination, the support owner accepts operations, and retirement is separately approved.

## 6. Recover without losing post-cutover work

| When or why recovery is needed | Response | Verification before resuming writes |
| --- | --- | --- |
| Before destination writes begin; import or final checks fail | Stop promotion, preserve logs and keep the destination unavailable to normal writers. Restore source integrations only after confirming the source still matches the captured recovery point. | Source data and access checks pass; destination cannot accept competing writes; the decision maker authorizes reopening the source. |
| After destination commits, pull requests or other updates exist | Freeze both sides. Inventory changes since cutover, preserve destination data, and decide whether a controlled forward fix or fallback is safer. Reconcile Git changes and platform metadata through an agreed, rehearsed method. | Owners account for every accepted post-cutover change, recheck access/integrations and explicitly select one writable source. |
| Security or release integration fails while repository data is intact | Disable the affected integration or deployment path and contain the issue. Investigate credentials and permissions with the relevant owner before choosing a forward fix or wider fallback. | The failed control is retested, exposed credentials are handled where applicable, and release authority is restored deliberately. |

Do not blindly mirror the source over a destination that may contain new work. Reverting migration scripts or changing links does not recover repository data, pull-request discussions or delivered releases. An application release rollback is a separate operation requiring its own recovery procedure.

## Required acceptance record

Keep one controlled record per repository linking:

- Source and destination identifiers, scope, owners, collection time and exact inventory/report revisions.
- Tool/version and import logs, final ref/object reconciliation and metadata/LFS evidence.
- Permission, branch-rule, security, build and integration test results.
- Each finding's disposition, unresolved exceptions, approving role and decision time.
- Freeze/cutover times, recovery point, retained post-cutover changes, recovery decision and observation outcome.

These are record requirements, not completed sign-offs. Public portfolio examples contain synthetic data only.

[Sample assessment](sample-assessment.md) · [Project overview](../README.md)
