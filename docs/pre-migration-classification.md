# Classify repositories before scheduling migration

Use the pre-migration classifier to separate routine transfers from repositories
that need review or a dedicated transformation path. This is the assessment I
would put in front of a migration calendar so large repositories, binary-heavy
history, TFVC conversion and branch complexity are visible before cutover work
begins.

The example policy is deliberately editable and travels with the input and
output. Its thresholds are demonstration values, not vendor limits or universal
recommendations. Agree values with the migration owners, platform limits,
network path and available compute before classifying real repositories.

```shell
python classify_repositories.py examples/pre-migration/inventory.json --output-dir reports/pre-migration --fail-on never
```

The synthetic example produces one standard repository, one review and two that
require transformation. Inspect `classification.md` for the human review or
`classification.json` for automation.

## Evidence contract

| Field | Meaning |
| --- | --- |
| `source_kind` | `git`, `tfvc`, or null when not established |
| `size_mb` | Measured repository size in MiB |
| `branch_count` | Count of in-scope branches |
| `binary_mb` | Measured binary content in MiB |
| `uses_lfs` | Whether Git LFS usage was established |
| `history_rewrite_required` | Whether an intentional rewrite is already known to be required |

Missing facts become `review_required`; zero and false must be supplied
explicitly. TFVC and intentional history rewrites require transformation.
Repository and binary sizes can require review or transformation, while branch
count and LFS usage require review under the supplied policy.

This tool does not scan repositories, estimate duration or select a migration
utility. It classifies measurements supplied by an authorized discovery process.
Follow classification with rehearsal, Git-ref reconciliation, LFS verification,
platform metadata checks and the operational acceptance work in the
[migration runbook](migration-runbook.md).
