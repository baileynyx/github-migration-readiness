# Azure DevOps collector: collect, assess, report

The read-only collector retrieves repository names, reported default branches and branch inventories from **one Azure DevOps Cloud project**. Its normalized JSON feeds the existing offline assessment engine. A separate collection record explains scope, provenance and unavailable branches.

The implementation is tested with synthetic responses. **No live organization has been queried or migrated as validation of this feature.**

## Run the offline demonstration

From the repository root, with Python 3.11 or later:

```shell
# Replay an exact sequence of synthetic API requests and responses. Fixture mode
# does not construct an HTTP client, read a PAT or wait through retry delays.
# Choose a new output directory each run; existing directories are refused.
python collect_azure_devops.py --fixture examples/azure-devops/responses.json --output-dir reports/azure-devops-demo

# Assess only the collected facts; missing evidence remains unknown. This sample
# deliberately contains a blocker, so report generation uses --fail-on never.
python readiness.py reports/azure-devops-demo/inventory.json --output-dir reports/azure-devops-demo --fail-on never
```

Expected collection result: `collected`, `synthetic_fixture`, 2 repositories, exit 0. Expected assessment summary:

```json
{"blocker": 1, "ready": 0, "review": 0, "unknown": 1}
```

The [response fixture](../examples/azure-devops/responses.json) includes an HTTP 429, its successful retry, and two branch pages with an opaque continuation token. The catalog repository has observed branches but six unknown fields. The legacy worker reports default branch `master` while the complete branch response contains only `main`, producing a blocker. These are fictional conditions, not a finding in a real estate.

Inspect the generated [inventory](../examples/azure-devops/inventory.json), [JSON report](../examples/azure-devops/readiness.json) and [Markdown report](../examples/azure-devops/readiness.md). Tests regenerate these artifacts and compare their content. The live run's `collection.json` also records its timestamp and scope; do not publish it or an inventory containing private organizational metadata.

## Collected facts and deliberate unknowns

| Assessment field | Source or treatment |
| --- | --- |
| `name` | Repository name returned by the selected project's repository-list request. |
| `default_branch` | Reported `defaultBranch`, with `refs/heads/` removed. Missing, empty or malformed values stay null. The target default branch still needs owner confirmation. |
| `branches` | Names from every successful branch-reference page, with `refs/heads/` removed; sorted, retaining case. A completed empty response yields `[]`. |
| `owner` | Null: project membership or a repository display name does not establish an accountable target owner. |
| `archived` | Null: Azure DevOps `isDisabled` is not treated as equivalent to the assessment's archived intent. |
| `uses_lfs` | Null: repository size, default branch and ref names do not establish LFS use. |
| `hooks`, `pipeline_dependencies`, `unmapped_identities` | Null: these endpoints do not provide the required discovery evidence. |

The collector's six uncollected fields mean an unedited collected inventory cannot be `ready`. Enrich a reviewed copy only after establishing the missing facts; retain the original collection and supporting evidence. Do not substitute empty arrays or false values merely to pass a gate.

## Optional live collection

Use an organization and project you are authorized to inspect. The token needs access to the selected project's repositories and the **Code (Read)** scope; permissions can limit which repositories and refs the service reveals. The implemented local prototype accepts a PAT through `AZURE_DEVOPS_PAT` or `--prompt-pat`. It does not accept a token as a command-line argument. Microsoft recommends moving ongoing integrations to Entra-based authentication; that flow is not implemented here. [PAT guidance](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops)

In PowerShell, prompt for the scope and let Python request the PAT without displaying it:

```powershell
# Scope values are ordinary project metadata. The PAT is entered only into
# Python's hidden terminal prompt, never pasted into a shell command.
$adoOrganization = Read-Host 'Azure DevOps organization name'
$adoProject = Read-Host 'Azure DevOps project name or ID'
$collectionFolder = Join-Path 'reports' ('azure-devops-' + [guid]::NewGuid().ToString('N'))
python collect_azure_devops.py --organization "$adoOrganization" --project "$adoProject" --prompt-pat --output-dir "$collectionFolder"
$collectionExit = $LASTEXITCODE

# Partial evidence is assessable, but its collection record must be reviewed.
# A fatal error stops this sequence before an old or incomplete inventory is used.
if ($collectionExit -notin 0, 1) { throw 'Collection failed; inspect the controlled error code.' }
python readiness.py (Join-Path $collectionFolder 'inventory.json') --output-dir "$collectionFolder" --fail-on unready
```

`--prompt-pat` requires a terminal. For an authorized noninteractive run, supply `AZURE_DEVOPS_PAT` through your existing secret-injection mechanism and omit that flag. The bundled GitHub workflow uses fixture mode only and requests no Azure DevOps credential.

Keep tokens out of fixtures, reports, Git and shell tracing. The client uses GET, normal HTTPS certificate validation and a fixed `dev.azure.com` host; it refuses redirects and ignores API-provided repository URLs. Diagnostics report controlled codes/statuses rather than raw response bodies or transport exceptions. This does not protect a token from a compromised host or externally enabled tracing.

## API behavior and failure handling

The repository-list API 7.1 does not document a pagination parameter. The collector includes hidden repositories visible to the credential and rejects an unexpected continuation header. It does not invent repository paging or claim organization-wide completeness. [Repository-list reference](https://learn.microsoft.com/en-us/rest/api/azure/devops/git/repositories/list?view=azure-devops-rest-7.1)

The refs request uses `filter=heads/`, a page size of 1,000 and the response's `x-ms-continuationtoken` for subsequent requests. Repeated tokens, duplicate refs, malformed envelopes and more than 100 pages abort collection. A new collection may be required if the source changes during paging; this is not an atomic snapshot or a ref/object-ID migration reconciliation. [Refs reference](https://learn.microsoft.com/en-us/rest/api/azure/devops/git/refs/list?view=azure-devops-rest-7.1)

HTTP 429 and 500/502/503/504 responses, plus transport errors, allow at most three attempts per request. Without a server delay, backoff is 1 then 2 seconds. `Retry-After` supports seconds and HTTP dates; a value over the 30-second wait budget stops the run instead of retrying early. On HTTP 200, its delay is honored before the next request without repeating the successful page. Requests time out after 10 seconds; responses are capped at 8 MiB and repository listings at 5,000 entries. [Azure DevOps throttling guidance](https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rate-limits?view=azure-devops)

| Collector exit | Meaning | Next action |
| --- | --- | --- |
| 0 | Selected repository/ref requests completed and output was written. | Review collection scope and assess; this is not migration readiness or proof of full access. |
| 1 | A discovered repository's refs returned 403 or 404; its entire branch list is null, including after a later-page failure. | Inspect `collection.json`, resolve access/deletion/source-change questions and recollect. Partial inventory is still assessable. |
| 2 | Authentication/discovery failure, exhausted retries, malformed data, invalid input or output failure. | Resolve the controlled error code and rerun into a new directory. Do not consume files left by an output-write failure. |

HTTP 401 always aborts. Repository discovery errors also abort because the collector cannot establish the selected set. A zero-repository listing is rejected rather than represented as ready. Collection errors occur before output creation; an output-write failure can leave incomplete files, so the exit code remains part of the contract.

Repository and branch access may be filtered without an HTTP error. Reconcile the visible set against an independently established scope before claiming discovery is complete. The collection record is separate from schema-version-1 inventory so diagnostics cannot be mistaken for assessment facts.

[Project overview](../README.md) · [Migration runbook](migration-runbook.md) · [Tests](../tests/test_collector.py)
