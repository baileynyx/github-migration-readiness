# Pre-migration repository classification

Classification reflects the supplied evidence and policy. It is a planning aid, not proof that a migration will succeed.

| Repository | Path | Field | Reason | Next action |
| --- | --- | --- | --- | --- |
| synthetic-catalog-api | standard | — | No policy threshold was reached. | Use the standard path, then complete normal rehearsal and acceptance checks. |
| synthetic-legacy-tfvc | transformation_required | source_kind | TFVC requires a conversion path. | Plan and rehearse history transformation before the migration window. |
| synthetic-legacy-tfvc | transformation_required | history_rewrite_required | The repository requires an intentional history rewrite. | Define the rewrite mapping and reconciliation acceptance evidence. |
| synthetic-legacy-tfvc | transformation_required | binary_mb | Binary content is 240 MiB; policy review threshold is 100 MiB. | Review transfer method, timing and validation before scheduling. |
| synthetic-media-history | transformation_required | size_mb | Repository size is 6,840 MiB; policy transformation threshold is 5,120 MiB. | Rehearse a dedicated transformation path and allocate appropriate compute and network proximity. |
| synthetic-media-history | transformation_required | binary_mb | Binary content is 1,780 MiB; policy transformation threshold is 1,024 MiB. | Rehearse a dedicated transformation path and allocate appropriate compute and network proximity. |
| synthetic-media-history | transformation_required | branch_count | Branch count is 82; policy review threshold is 50. | Confirm branch scope, owners and post-transfer ref reconciliation. |
| synthetic-media-history | transformation_required | uses_lfs | Git LFS objects need a separate transfer and availability check. | Inventory, transfer and verify LFS objects from a fresh clone. |
| synthetic-undiscovered-worker | review_required | size_mb | Evidence was not supplied. | Collect and verify size_mb before scheduling. |
| synthetic-undiscovered-worker | review_required | branch_count | Evidence was not supplied. | Collect and verify branch_count before scheduling. |
| synthetic-undiscovered-worker | review_required | binary_mb | Evidence was not supplied. | Collect and verify binary_mb before scheduling. |
| synthetic-undiscovered-worker | review_required | uses_lfs | Evidence was not supplied. | Collect and verify uses_lfs before scheduling. |
| synthetic-undiscovered-worker | review_required | history_rewrite_required | Evidence was not supplied. | Collect and verify history_rewrite_required before scheduling. |
