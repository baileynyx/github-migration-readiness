"""Read visible Azure DevOps Cloud Git metadata into the assessment contract.

Only repository discovery and branch references are collected. Unknown facts
remain null. Credentials and raw HTTP diagnostics are never written to output.
Use --fixture for an entirely offline run through the same collection logic.
"""
import argparse
import base64
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import getpass
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import readiness


API_VERSION = '7.1'
MAX_BODY = 8 * 1024 * 1024
MAX_PAGES = 100
MAX_REPOSITORIES = 5000
MAX_WAIT = 30
RETRYABLE = {429, 500, 502, 503, 504}


class CollectionError(Exception):
    """Carry only a controlled error code and optional HTTP status, never a body."""
    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so an authenticated request cannot move to another URL."""
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def validate_scope(organization, project):
    """Accept an organization slug and one project name/ID, never a base URL."""
    if not isinstance(organization, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,49}', organization):
        raise CollectionError('invalid_organization')
    if not isinstance(project, str) or not project.strip() or project in ('.', '..'):
        raise CollectionError('invalid_project')
    if len(project) > 200 or any(ord(c) < 32 or c in '/\\' for c in project):
        raise CollectionError('invalid_project')


class LiveTransport:
    """Issue GET requests only, over verified HTTPS to a fixed Azure DevOps host."""
    def __init__(self, organization, project, token):
        validate_scope(organization, project)
        if not token or any(c.isspace() for c in token):
            raise CollectionError('missing_or_invalid_pat')
        encoded = base64.b64encode((':' + token).encode()).decode('ascii')
        self._authorization = 'Basic ' + encoded
        self._base = 'https://dev.azure.com/' + organization + '/' + urllib.parse.quote(project, safe='') + '/_apis/git/'
        self._opener = urllib.request.build_opener(NoRedirect())

    def get(self, resource, query):
        # Resource paths come from this module, not API-supplied URLs. Verify
        # them here as well so future callers cannot redirect the authorization.
        if not re.fullmatch(r'repositories(?:/[0-9a-f-]{36}/refs)?', resource):
            raise CollectionError('invalid_resource')
        url = self._base + resource + '?' + urllib.parse.urlencode(query)
        request = urllib.request.Request(url, method='GET', headers={
            'Authorization': self._authorization, 'Accept': 'application/json',
            'User-Agent': 'migration-readiness-collector/1',
        })
        try:
            with self._opener.open(request, timeout=10) as response:
                body = response.read(MAX_BODY + 1)
                if len(body) > MAX_BODY:
                    raise CollectionError('response_too_large')
                return response.status, dict(response.headers), body
        except urllib.error.HTTPError as error:
            # Do not read or echo service error bodies, which may include
            # request details, URLs or credentials reflected by an intermediary.
            status, headers = error.code, dict(error.headers)
            error.close()
            return status, headers, b''
        except (OSError, urllib.error.URLError):
            raise CollectionError('transport_error') from None


class FixtureTransport:
    """Replay ordered, synthetic HTTP responses without constructing a client."""
    def __init__(self, fixture):
        self.responses = fixture['responses']
        self.index = 0

    def get(self, resource, query):
        if self.index >= len(self.responses):
            raise CollectionError('fixture_exhausted')
        item = self.responses[self.index]
        self.index += 1
        if item['request'] != {'resource': resource, 'query': query}:
            raise CollectionError('fixture_request_mismatch')
        return item['status'], item.get('headers', {}), json.dumps(item.get('body', {})).encode()


class Client:
    """Bound retries and pacing separately from normalization and evidence."""
    def __init__(self, transport, sleep=time.sleep, now=None):
        self.transport, self.sleep = transport, sleep
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.pending_delay = 0

    def retry_delay(self, headers, fallback):
        value = headers.get('retry-after')
        if value is None:
            return fallback
        try:
            delay = float(value)
        except (ValueError, TypeError):
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None:
                    raise ValueError()
                delay = max(0, (date - self.now()).total_seconds())
            except (ValueError, TypeError, OverflowError):
                raise CollectionError('invalid_retry_after') from None
        # Never shorten a server's requested wait and retry early. A wait above
        # the local budget aborts the run; the operator can collect again later.
        if not 0 <= delay <= MAX_WAIT:
            raise CollectionError('retry_after_exceeds_budget')
        return delay

    def get(self, resource, parameters=None):
        query = {'api-version': API_VERSION, **(parameters or {})}
        for attempt in range(3):
            if self.pending_delay:
                self.sleep(self.pending_delay)
                self.pending_delay = 0
            try:
                status, raw_headers, body = self.transport.get(resource, query)
            except CollectionError as error:
                if error.code != 'transport_error' or attempt == 2:
                    raise
                self.pending_delay = 2 ** attempt
                continue
            headers = {key.lower(): value for key, value in raw_headers.items()}
            if status in RETRYABLE:
                if attempt == 2:
                    raise CollectionError('retry_exhausted', status)
                self.pending_delay = self.retry_delay(headers, 2 ** attempt)
                continue
            if status != 200:
                raise CollectionError('http_error', status)
            # Azure DevOps can ask clients to pause even on HTTP 200. Apply
            # that pause before the next request; do not repeat a successful GET.
            self.pending_delay = self.retry_delay(headers, 0)
            try:
                document = json.loads(body)
            except (ValueError, UnicodeError):
                raise CollectionError('invalid_json') from None
            if not isinstance(document, dict) or not isinstance(document.get('value'), list):
                raise CollectionError('invalid_response_shape')
            count = document.get('count')
            if type(count) is not int or count != len(document['value']):
                raise CollectionError('invalid_response_count')
            return document['value'], headers
        raise CollectionError('retry_exhausted')


def collect_branches(client, repository_id):
    """Publish branches only after every page succeeds; discard partial lists."""
    branches, tokens = set(), set()
    parameters = {'filter': 'heads/', '$top': '1000'}
    for _ in range(MAX_PAGES):
        refs, headers = client.get(f'repositories/{repository_id}/refs', parameters)
        for ref in refs:
            name = ref.get('name') if isinstance(ref, dict) else None
            if not isinstance(name, str) or not name.startswith('refs/heads/') or not name[11:].strip():
                raise CollectionError('invalid_branch_ref')
            if name[11:] in branches:
                raise CollectionError('duplicate_branch_ref')
            branches.add(name[11:])
        token = headers.get('x-ms-continuationtoken')
        if not token:
            return sorted(branches)
        if not isinstance(token, str) or token in tokens:
            raise CollectionError('repeated_continuation_token')
        tokens.add(token)
        parameters = {**parameters, 'continuationToken': token}
    raise CollectionError('page_limit_exceeded')


def collect(client, organization, project):
    """Normalize visible repositories; attach provenance outside schema version 1."""
    validate_scope(organization, project)
    repositories, headers = client.get('repositories', {'includeHidden': 'true'})
    # API 7.1 does not document repository-list pagination. Refuse unexpected
    # continuation rather than silently represent a partial listing as complete.
    if headers.get('x-ms-continuationtoken'):
        raise CollectionError('unsupported_repository_continuation')
    if not repositories or len(repositories) > MAX_REPOSITORIES:
        raise CollectionError('empty_or_oversized_repository_listing')
    inventory, evidence, ids = [], [], set()
    for source in repositories:
        if not isinstance(source, dict):
            raise CollectionError('invalid_repository')
        try:
            repository_id = str(uuid.UUID(source['id']))
        except (ValueError, KeyError, TypeError, AttributeError):
            raise CollectionError('invalid_repository_id') from None
        name = source.get('name')
        if not isinstance(name, str) or not name.strip() or repository_id in ids:
            raise CollectionError('invalid_or_duplicate_repository')
        ids.add(repository_id)
        item = {'name': name, **{field: None for field in readiness.FIELDS}}
        default = source.get('defaultBranch')
        if isinstance(default, str) and default.startswith('refs/heads/') and default[11:].strip():
            item['default_branch'] = default[11:]
        details = {'name': name, 'repository_id': repository_id,
                   'default_branch': 'observed' if item['default_branch'] else 'unknown',
                   'branches': 'observed'}
        try:
            item['branches'] = collect_branches(client, repository_id)
        except CollectionError as error:
            # Authentication failure aborts everything. Only a repository-level
            # forbidden/not-found response becomes partial evidence, including
            # when it occurs on a later page. Never retain a partial branch list.
            if error.code != 'http_error' or error.status not in (403, 404):
                raise
            details.update(branches='unknown', reason='refs_unavailable', http_status=error.status)
        inventory.append(item)
        evidence.append(details)
    data = {'schema_version': 1, 'repositories': sorted(inventory, key=lambda item: item['name'].casefold())}
    try:
        readiness.validate(data)
    except ValueError:
        raise CollectionError('invalid_normalized_inventory') from None
    partial = any(item['branches'] == 'unknown' for item in evidence)
    metadata = {'schema_version': 1, 'organization': organization, 'project': project,
                'api_version': API_VERSION, 'collected_at': datetime.now(timezone.utc).isoformat(),
                'status': 'partial' if partial else 'collected',
                'scope': 'repositories and branch refs visible to this credential in one project',
                'limitations': ['not an atomic snapshot or proof of complete project visibility',
                                'owner, archived, uses_lfs, hooks, pipeline_dependencies and unmapped_identities remain unknown'],
                'repositories': sorted(evidence, key=lambda item: item['name'].casefold())}
    return data, metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--organization')
    parser.add_argument('--project')
    parser.add_argument('--prompt-pat', action='store_true', help='Read a PAT with a hidden interactive prompt.')
    parser.add_argument('--fixture', type=Path, help='Replay synthetic HTTP responses without network or credentials.')
    parser.add_argument('--output-dir', type=Path, required=True, help='New directory; existing output is never overwritten.')
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists():
            raise CollectionError('output_directory_exists')
        if args.fixture:
            if args.organization or args.project or args.prompt_pat:
                raise CollectionError('fixture_and_live_options_are_mutually_exclusive')
            fixture = json.loads(args.fixture.read_text(encoding='utf-8'))
            organization, project = fixture['organization'], fixture['project']
            transport = FixtureTransport(fixture)
            # Fixture pacing is recorded by tests; a replay performs no sleeps.
            client = Client(transport, sleep=lambda delay: None)
        else:
            organization, project = args.organization, args.project
            validate_scope(organization, project)
            if args.prompt_pat and not sys.stdin.isatty():
                raise CollectionError('pat_prompt_requires_terminal')
            token = getpass.getpass('Azure DevOps PAT (Code: Read): ') if args.prompt_pat else os.environ.get('AZURE_DEVOPS_PAT', '')
            client = Client(LiveTransport(organization, project, token))
        data, metadata = collect(client, organization, project)
        if args.fixture and transport.index != len(transport.responses):
            raise CollectionError('unused_fixture_responses')
        metadata['mode'] = 'synthetic_fixture' if args.fixture else 'live_read_only'
        # Complete collection and schema validation before creating output. A
        # fresh directory prevents an older successful inventory being mistaken
        # for this run after an authentication or discovery failure.
        args.output_dir.mkdir(parents=True, exist_ok=False)
        for filename, value in [('inventory.json', data), ('collection.json', metadata)]:
            (args.output_dir / filename).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'collection': metadata['status'], 'repositories': len(data['repositories']),
                          'mode': metadata['mode']}, sort_keys=True))
        return 1 if metadata['status'] == 'partial' else 0
    except CollectionError as error:
        status = f' (HTTP {error.status})' if error.status is not None else ''
        print(f'Collection failed: {error.code}{status}.', file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, EOFError):
        # Never print raw exception text: fixtures, paths and service responses
        # can include sensitive data. Exit codes and controlled codes are enough.
        print('Collection failed: invalid_input_or_output.', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
