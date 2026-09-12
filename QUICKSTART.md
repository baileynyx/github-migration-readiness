# Run the packaged migration tool

Requires Python 3.11 or later and Git on PATH. Package CI uses Python 3.12 on
Windows and Linux. The five command-line tools use only the Python standard
library; optional visual regeneration requires the separate Pillow dependency.

Download the versioned ZIP and its matching `.zip.sha256` file from the release
assets. During release preparation, the same files are available in CI artifacts;
an artifact is a candidate, not a published release.

## Check the download

In PowerShell, from the directory containing the downloaded files:

```powershell
$archive = 'github-migration-readiness-1.0.0.zip'
$expected = (Get-Content "$archive.sha256" -Raw).Trim().Split(' ')[0]
$actual = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw 'Download checksum mismatch.' }
Expand-Archive $archive -DestinationPath .
cd github-migration-readiness-1.0.0
```

In Bash on Linux, from the download directory:

```bash
sha256sum --check github-migration-readiness-1.0.0.zip.sha256
unzip github-migration-readiness-1.0.0.zip
cd github-migration-readiness-1.0.0
```

The checksum detects changed bytes; it is not a signature or proof of authorship.
Use a fresh extraction directory. `BUILD.json` records the source commit, version
and individual file hashes. The ZIP filename is versioned; the commit identifies
the exact candidate or published build.

## Try the synthetic examples

Run these commands from the extracted folder in PowerShell or Bash:

```shell
python readiness.py examples/migration-assessment/inventory.json --output-dir reports/assessment --fail-on never
python classify_repositories.py examples/pre-migration/inventory.json --output-dir reports/pre-migration --fail-on never
python collect_azure_devops.py --fixture examples/azure-devops/responses.json --output-dir reports/collector
python readiness.py reports/collector/inventory.json --output-dir reports/collector --fail-on never
python rehearse_refs.py --output-dir reports/ref-rehearsal
python -m unittest discover -s tests -v
```

Expected: the six-repository assessment reports 1 blocker, 1 unknown, 3 review and
1 ready; pre-migration classification reports 1 standard, 1 review and 2
transformation paths; fixture collection produces 2 repositories whose assessment
has 1 blocker and 1 unknown. The Git rehearsal verifies 5 intact ref records, then detects 1
missing, 1 unexpected and 2 changed records in the altered copy. The product suite
contains 50 tests. Collection and rehearsal require new output directories.

Inspect the Markdown and JSON files under `reports`. These examples use no
credentials or provider requests. See [README.md](README.md) for the tool's scope
and [the runbook](docs/migration-runbook.md) for checks beyond ref equality.

## Interpret an expected failure

```shell
python verify_refs.py examples/ref-verification/source.refs examples/ref-verification/destination.refs --output-dir reports/ref-differences
```

This intentionally returns **1** while writing its report: the supplied refs
differ. Inspect `$LASTEXITCODE` immediately in PowerShell or `$?` in Bash.
Comparator exit 0 means matching supplied refs; 2 means invalid input or an I/O
error. A matching comparison does not certify a complete migration.
