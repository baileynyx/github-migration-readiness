# Migration readiness assessment

Readiness describes the supplied inventory; it does not certify migration completeness.

| Repository | Status | Field | Finding | Resolution |
| --- | --- | --- | --- | --- |
| synthetic-legacy | blocker | owner | Required value is empty. | Assign a valid owner. |
| synthetic-legacy | blocker | uses_lfs | Git LFS objects require separate verification. | Transfer LFS objects and verify availability from a fresh clone. |
| synthetic-legacy | blocker | hooks | Service hooks require target reconfiguration. | Recreate and test hooks with target credentials. |
| synthetic-legacy | blocker | pipeline_dependencies | External pipeline dependencies exist. | Map pipelines, agents, service connections, secrets and artifact feeds. |
| synthetic-legacy | blocker | unmapped_identities | Identity mappings are unresolved. | Resolve target identities and verify permissions with owners. |
| synthetic-payments | ready | — | No findings in supplied inventory. | Proceed to rehearsal and provider-specific checks. |
| synthetic-undiscovered | unknown | owner | Evidence was not supplied. | Collect and verify owner. |
| synthetic-undiscovered | unknown | default_branch | Evidence was not supplied. | Collect and verify default_branch. |
| synthetic-undiscovered | unknown | branches | Evidence was not supplied. | Collect and verify branches. |
| synthetic-undiscovered | unknown | archived | Evidence was not supplied. | Collect and verify archived. |
| synthetic-undiscovered | unknown | uses_lfs | Evidence was not supplied. | Collect and verify uses_lfs. |
| synthetic-undiscovered | unknown | hooks | Evidence was not supplied. | Collect and verify hooks. |
| synthetic-undiscovered | unknown | pipeline_dependencies | Evidence was not supplied. | Collect and verify pipeline_dependencies. |
| synthetic-undiscovered | unknown | unmapped_identities | Evidence was not supplied. | Collect and verify unmapped_identities. |
