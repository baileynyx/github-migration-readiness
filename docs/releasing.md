# Prepare and publish a versioned package

## Prepare

The repository currently prepares version 1.0.0. A passing package CI artifact is
a release candidate, not a published GitHub Release. Start with
[QUICKSTART.md](../QUICKSTART.md) to try the downloaded package.

From a committed checkout, run:

```shell
python build_release.py --output-dir dist
python check_package.py dist/github-migration-readiness-1.0.0.zip --output-dir reports/package-check
```

The builder reads `HEAD`, `VERSION` and `RELEASE_FILES.txt` from Git objects.
Uncommitted edits and untracked files are deliberately excluded. Commit intended
release inputs first. Outputs are refused if their directory already exists.
These two maintainer scripts run from the source checkout and are not in the
consumer ZIP.

The archive uses a sorted explicit file list, stored entries, fixed timestamps
and permissions. Windows checkout conversion cannot change the packaged bytes.
`BUILD.json` records the commit, version and each payload file's SHA-256; the
adjacent checksum covers the full ZIP. Identical committed inputs should produce
identical bytes. Neither checksum is an attestation.

CI builds the ZIP twice on each platform and compares hashes. It then verifies
the archive checksum, member paths and file inventory; extracts into a fresh
temporary directory outside the checkout; runs the 50 packaged product tests;
and checks assessments, fixture collection, expected blocking exits and the
actual Git rehearsal. Python path overrides are removed. No live collection is
performed. Each platform uploads its ZIP, checksum and `package-check.json`, with
14-day retention. The evidence includes the actual source commit and ZIP hash.

## Publish after review

1. Merge the preparation PR and verify both package jobs on the resulting `main`
   commit. Use these artifacts, since PR artifacts identify a temporary PR merge
   commit rather than the final commit on `main`.
2. Confirm both platform evidence files identify that same commit and ZIP hash.
   Choose one tested ZIP/checksum pair. Keep the matching package-check evidence.
3. Review the release notes, replacing the candidate status with the actual
   publication status in the release description. Create tag `v1.0.0` at the exact
   verified commit; do not silently tag a newer untested commit.
4. Create a draft GitHub Release for that tag and attach the tested ZIP, matching
   checksum and platform validation evidence. Review the draft before publication.
5. Publish, check the public asset downloads and update the README with their real
   links. Do not overwrite assets or move the tag to repair a published version;
   prepare a new version instead.

No release/tag publication is triggered by this PR or by pushing to `main`.
Future versions should update `VERSION`, the quickstart filenames, CI package
paths and release notes together, and review `RELEASE_FILES.txt` for new files.
