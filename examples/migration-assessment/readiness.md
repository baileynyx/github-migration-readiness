# Migration readiness assessment

Readiness describes the supplied inventory; it does not certify migration completeness.

| Repository | Status | Field | Finding | Resolution |
| --- | --- | --- | --- | --- |
| synthetic-audit-archive | review | archived | Repository is archived. | Confirm inclusion and preserve read-only intent at cutover. |
| synthetic-catalog-api | ready | — | No findings in supplied inventory. | Proceed to rehearsal and provider-specific checks. |
| synthetic-legacy-orders | blocker | owner | Required value is empty. | Assign a valid owner. |
| synthetic-legacy-orders | blocker | branches | Default branch is absent from the ref inventory. | Reconcile the default branch and exported refs. |
| synthetic-legacy-orders | blocker | hooks | Service hooks require target reconfiguration. | Recreate and test hooks with target credentials. |
| synthetic-legacy-orders | blocker | pipeline_dependencies | External pipeline dependencies exist. | Map pipelines, agents, service connections, secrets and artifact feeds. |
| synthetic-legacy-orders | blocker | unmapped_identities | Identity mappings are unresolved. | Resolve target identities and verify permissions with owners. |
| synthetic-media-assets | review | uses_lfs | Git LFS objects require separate verification. | Transfer LFS objects and verify availability from a fresh clone. |
| synthetic-release-tools | review | hooks | Service hooks require target reconfiguration. | Recreate and test hooks with target credentials. |
| synthetic-release-tools | review | pipeline_dependencies | External pipeline dependencies exist. | Map pipelines, agents, service connections, secrets and artifact feeds. |
| synthetic-undiscovered-worker | unknown | branches | Evidence was not supplied. | Collect and verify branches. |
| synthetic-undiscovered-worker | unknown | uses_lfs | Evidence was not supplied. | Collect and verify uses_lfs. |
| synthetic-undiscovered-worker | unknown | hooks | Evidence was not supplied. | Collect and verify hooks. |
| synthetic-undiscovered-worker | unknown | pipeline_dependencies | Evidence was not supplied. | Collect and verify pipeline_dependencies. |
| synthetic-undiscovered-worker | unknown | unmapped_identities | Evidence was not supplied. | Collect and verify unmapped_identities. |
