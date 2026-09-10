# Ref verification demo: text version

This 30-second presentation visualizes an actual run against disposable synthetic Git repositories. It is not a screen recording or measured migration duration.

1. Intact copy: 5 matched records; comparator exit 0.
2. Changed copy: 4 differences; comparator exit 1.
3. The annotated tag object changed while its peeled target stayed identical. The visual abbreviates IDs to 12 characters; full IDs are retained below.
4. Source refs remained unchanged. Matching refs alone does not certify a migration.

[Intact report](evidence/matching/refs.md) · [Execution evidence](evidence/evidence.json)

# Git ref verification

**Result: DIFFERENCES FOUND**

This compares supplied branch/tag snapshots; it does not certify a complete migration.

Source snapshot SHA-256: 15629ec9b0229c3172656bf3a72e461d25e7147f5a8ba037cd943fdc0de7425a

Destination snapshot SHA-256: ed46af7b85341e621746147c821017f7aa2a609392967fa98e8994195cc9e8df

| Comparison | Ref records |
| --- | ---: |
| matched | 2 |
| mismatched | 2 |
| missing | 1 |
| unexpected | 1 |

Annotated tags count as a tag-object record plus a peeled-target record.

## Differences

| Ref | Kind | Finding | Source object ID | Destination object ID |
| --- | --- | --- | --- | --- |
| refs/heads/destination-only | branch | unexpected | absent | 4935be07ae9ef40ad0fefe84a1913bf0185b5658 |
| refs/heads/feature | branch | missing | ab4fdf8b1507bb869546fc04e93305d8a0b3d674 | absent |
| refs/heads/main | branch | mismatched | 4935be07ae9ef40ad0fefe84a1913bf0185b5658 | ab4fdf8b1507bb869546fc04e93305d8a0b3d674 |
| refs/tags/v1.0.0 | tag | mismatched | 0a4ec19869007bc074f6602190df1c7ae4fb2e6b | e24202c3148751f1bc8bbece4f1e476a9bc4fe30 |

## Review actions

- Missing: investigate export/import scope and collection permissions.
- Unexpected: identify destination-only work before considering reconciliation.
- Mismatched: investigate new writes, rewritten history or changed tag objects.
- Do not overwrite either repository based only on this report.

Limits: snapshots do not verify default branch, complete object availability, LFS, submodules,
hidden refs, permissions, pull requests, work items, hooks or pipeline behavior.
Capture both sides during an agreed write freeze and retain collection provenance.
