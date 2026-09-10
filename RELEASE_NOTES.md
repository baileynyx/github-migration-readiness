# Version 1.0.0 — release candidate

This version is being prepared for the first published release. This document
does not claim that a GitHub Release or tag already exists.

## Included

- Offline readiness assessment with actionable JSON and Markdown reports.
- Read-only Azure DevOps Cloud collection with a credential-free fixture mode.
- Comparison of branch/tag captures, including annotated-tag objects and peeled targets.
- A real-Git rehearsal using disposable local repositories.
- Synthetic inventories, captured evidence, visual/text walkthroughs and 50 product tests.
- [Package quickstart](QUICKSTART.md), exact source commit and file hashes in `BUILD.json`.

The versioned ZIP requires Python 3.11+ and Git; its core tools need no Python
packages. Release preparation checks the extracted ZIP on Windows/PowerShell and
Linux/Bash using Python 3.12. The optional visual renderer uses Pillow and is not
part of the package runtime checks.

## Behavioral contract and limits

This release does not migrate repositories or change provider configuration.
Live Azure DevOps collection remains unvalidated. Ref equality covers only the
supplied branch/tag captures, not LFS, permissions, default branch, object
availability or platform metadata. Inventory fields with missing evidence remain
unknown. Output and exit-code details are documented in the quickstart and README.

The `.zip.sha256` sidecar provides integrity checking, not signed provenance.
For a published release, use its attached ZIP and matching checksum rather than
GitHub's automatically generated source archives, which have a different layout.
