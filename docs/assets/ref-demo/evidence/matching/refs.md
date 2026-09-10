# Git ref verification

**Result: MATCH**

This compares supplied branch/tag snapshots; it does not certify a complete migration.

Source snapshot SHA-256: 15629ec9b0229c3172656bf3a72e461d25e7147f5a8ba037cd943fdc0de7425a

Destination snapshot SHA-256: 15629ec9b0229c3172656bf3a72e461d25e7147f5a8ba037cd943fdc0de7425a

| Comparison | Ref records |
| --- | ---: |
| matched | 5 |
| missing | 0 |
| unexpected | 0 |
| mismatched | 0 |

Annotated tags count as a tag-object record plus a peeled-target record.

## Differences

| Ref | Kind | Finding | Source object ID | Destination object ID |
| --- | --- | --- | --- | --- |
| None | — | All supplied records match. | — | — |

## Review actions

- Missing: investigate export/import scope and collection permissions.
- Unexpected: identify destination-only work before considering reconciliation.
- Mismatched: investigate new writes, rewritten history or changed tag objects.
- Do not overwrite either repository based only on this report.

Limits: snapshots do not verify default branch, complete object availability, LFS, submodules,
hidden refs, permissions, pull requests, work items, hooks or pipeline behavior.
Capture both sides during an agreed write freeze and retain collection provenance.
