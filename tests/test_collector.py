"""Exercise API boundaries with synthetic replies; no live account is accessed."""
import base64
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

import collect_azure_devops as collector
import readiness


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples' / 'azure-devops' / 'responses.json'
REPO_ID = '11111111-1111-4111-8111-111111111111'


def reply(values=(), status=200, headers=None):
    """Build an API-shaped collection envelope; error bodies are irrelevant."""
    return status, headers or {}, json.dumps({'count': len(values), 'value': list(values)}).encode()


def repository(**overrides):
    return {'id': REPO_ID, 'name': 'synthetic-api', 'defaultBranch': 'refs/heads/main', **overrides}


class ScriptedTransport:
    """Record requests and replay responses/errors without any network stack."""
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, resource, query):
        self.calls.append((resource, dict(query)))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class CollectorTests(unittest.TestCase):
    def client(self, *responses):
        transport = ScriptedTransport(*responses)
        delays = []
        return collector.Client(transport, sleep=delays.append), transport, delays

    def test_complete_pages_preserve_branch_names_and_opaque_token(self):
        client, transport, _ = self.client(reply([repository()]),
            reply([{'name': 'refs/heads/main'}], headers={'X-MS-ContinuationToken': 'next/+='}),
            reply([{'name': 'refs/heads/Release/One'}]))
        data, metadata = collector.collect(client, 'synthetic-org', 'project')
        self.assertEqual(data['repositories'][0]['branches'], ['Release/One', 'main'])
        self.assertEqual(transport.calls[-1][1]['continuationToken'], 'next/+=')
        self.assertEqual(metadata['status'], 'collected')

    def test_later_page_permission_failure_discards_partial_branches(self):
        for status in (403, 404):
            with self.subTest(status=status):
                client, _, _ = self.client(reply([repository()]),
                    reply([{'name': 'refs/heads/feature'}], headers={'x-ms-continuationtoken': 'next'}),
                    reply(status=status))
                data, metadata = collector.collect(client, 'synthetic-org', 'project')
                self.assertIsNone(data['repositories'][0]['branches'])
                self.assertEqual(metadata['status'], 'partial')
                self.assertEqual(metadata['repositories'][0]['http_status'], status)
                # A partial branch list must not falsely declare the default missing.
                self.assertEqual(readiness.assess(data)['summary']['blocker'], 0)

    def test_uncollected_facts_and_missing_default_are_unknown(self):
        for default in (None, '', 'main', 123):
            with self.subTest(default=default):
                client, _, _ = self.client(reply([repository(defaultBranch=default, isDisabled=False,
                                                           owner='not-an-accountable-owner', size=0)]), reply())
                data, _ = collector.collect(client, 'synthetic-org', 'project')
                item = data['repositories'][0]
                self.assertEqual(item['branches'], [])
                for field in collector.readiness.FIELDS:
                    if field != 'branches':
                        self.assertIsNone(item[field], field)

    def test_complete_empty_branches_can_block_a_claimed_default(self):
        client, _, _ = self.client(reply([repository()]), reply())
        data, _ = collector.collect(client, 'synthetic-org', 'project')
        self.assertEqual(readiness.assess(data)['summary']['blocker'], 1)

    def test_discovery_permission_failure_and_branch_auth_failure_abort(self):
        for responses in ([reply(status=401)], [reply(status=403)], [reply(status=404)],
                          [reply([repository()]), reply(status=401)]):
            with self.subTest(responses=responses):
                client, transport, _ = self.client(*responses)
                with self.assertRaises(collector.CollectionError):
                    collector.collect(client, 'synthetic-org', 'project')
                self.assertEqual(len(transport.calls), len(responses))

    def test_malformed_and_duplicate_evidence_is_rejected(self):
        cases = [
            [reply()],
            [reply([repository(id='bad')])],
            [reply([repository(), repository()]), reply()],
            [reply([repository()], headers={'x-ms-continuationtoken': 'unsupported'})],
            [reply([repository()]), reply([{'name': 'refs/tags/v1'}])],
            [reply([repository()]), reply([{'name': 'refs/heads/main'}, {'name': 'refs/heads/main'}])],
            [(200, {}, b'{broken')],
            [(200, {}, b'{"value": []}')],
            [(200, {}, b'{"count": 2, "value": []}')],
            [(200, {}, b'[]')],
        ]
        for responses in cases:
            with self.subTest(responses=responses):
                client, _, _ = self.client(*responses)
                with self.assertRaises(collector.CollectionError):
                    collector.collect(client, 'synthetic-org', 'project')

    def test_repeated_token_and_page_limit_abort(self):
        for limit, token, code in [(100, 'same', 'repeated_continuation_token'),
                                   (1, 'different', 'page_limit_exceeded')]:
            with self.subTest(code=code), patch.object(collector, 'MAX_PAGES', limit):
                client, _, _ = self.client(reply(headers={'x-ms-continuationtoken': token}),
                                           reply(headers={'x-ms-continuationtoken': token}))
                with self.assertRaisesRegex(collector.CollectionError, code):
                    collector.collect_branches(client, REPO_ID)

    def test_throttling_and_server_errors_retry_with_bounded_backoff(self):
        for status in (429, 500, 502, 503, 504):
            with self.subTest(status=status):
                client, transport, delays = self.client(reply(status=status, headers={'Retry-After': '3'}),
                                                       reply(status=status), reply())
                client.get('repositories')
                self.assertEqual(delays, [3, 2])
                self.assertEqual(len(transport.calls), 3)
                self.assertTrue(all(call == transport.calls[0] for call in transport.calls))

    def test_retry_exhaustion_and_network_errors_stop_after_three_attempts(self):
        for response in (reply(status=503), collector.CollectionError('transport_error')):
            with self.subTest(response=response):
                client, transport, delays = self.client(response, response, response)
                with self.assertRaises(collector.CollectionError):
                    client.get('repositories')
                self.assertEqual(len(transport.calls), 3)
                self.assertEqual(delays, [1, 2])

    def test_success_retry_after_paces_next_request_without_repeating_page(self):
        client, transport, delays = self.client(reply(headers={'Retry-After': '4'}), reply())
        client.get('repositories')
        self.assertEqual(delays, [])
        client.get(f'repositories/{REPO_ID}/refs')
        self.assertEqual(delays, [4])
        self.assertNotEqual(transport.calls[0][0], transport.calls[1][0])

    def test_retry_after_dates_and_budget(self):
        client, _, delays = self.client(reply(status=429, headers={'Retry-After': '31'}))
        client.now = lambda: datetime(2026, 9, 10, tzinfo=timezone.utc)
        self.assertEqual(client.retry_delay({'retry-after': 'Thu, 10 Sep 2026 00:00:05 GMT'}, 1), 5)
        for value in ('nonsense', '-1', 'nan', 'inf'):
            with self.subTest(value=value), self.assertRaises(collector.CollectionError):
                client.retry_delay({'retry-after': value}, 1)
        with self.assertRaisesRegex(collector.CollectionError, 'exceeds_budget'):
            client.get('repositories')
        self.assertEqual(delays, [])

    def test_live_transport_uses_get_fixed_host_and_encoded_segments(self):
        class Response:
            status, headers = 200, {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, maximum): return b'{"count": 0, "value": []}'
        transport = collector.LiveTransport('synthetic-org', 'Project One', 'synthetic-test-token')
        with patch.object(transport._opener, 'open', return_value=Response()) as request:
            transport.get(f'repositories/{REPO_ID}/refs', {'continuationToken': 'opaque/+='})
        sent = request.call_args.args[0]
        self.assertEqual(sent.get_method(), 'GET')
        self.assertEqual(urllib.parse.urlsplit(sent.full_url).netloc, 'dev.azure.com')
        self.assertIn('/Project%20One/', sent.full_url)
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(sent.full_url).query),
                         {'continuationToken': ['opaque/+=']})
        self.assertEqual(sent.get_header('Authorization'),
                         'Basic ' + base64.b64encode(b':synthetic-test-token').decode())
        self.assertEqual(request.call_args.kwargs['timeout'], 10)
        self.assertIsNone(collector.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.invalid'))
        with self.assertRaises(collector.CollectionError):
            transport.get('https://evil.invalid', {})

    def test_transport_does_not_expose_error_bodies_or_network_exceptions(self):
        transport = collector.LiveTransport('synthetic-org', 'project', 'synthetic-secret')
        for failure in (urllib.error.URLError('synthetic-secret'),
                        urllib.error.HTTPError('https://dev.azure.com', 401, 'synthetic-secret', {},
                                               io.BytesIO(b'synthetic-secret'))):
            with self.subTest(failure=type(failure).__name__), patch.object(transport._opener, 'open', side_effect=failure):
                client = collector.Client(transport, sleep=lambda delay: None)
                with self.assertRaises(collector.CollectionError) as result:
                    client.get('repositories')
                self.assertNotIn('synthetic-secret', str(result.exception))

    def test_unsafe_scope_and_missing_token_are_rejected(self):
        for organization, project, token in [('https://evil.invalid', 'p', 't'),
                                             ('org', '..', 't'), ('org', 'x/y', 't'),
                                             ('org', 'p', ''), ('org', 'p', 'bad\ntoken')]:
            with self.subTest(organization=organization, project=project):
                with self.assertRaises(collector.CollectionError):
                    collector.LiveTransport(organization, project, token)

    def test_offline_cli_collect_assess_report_and_committed_example(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'collection'
            # A sentinel environment credential must be ignored in fixture mode.
            with patch.dict('os.environ', {'AZURE_DEVOPS_PAT': 'synthetic-secret'}):
                result = subprocess.run([sys.executable, str(ROOT / 'collect_azure_devops.py'),
                    '--fixture', str(FIXTURE), '--output-dir', str(output)],
                    capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('synthetic-secret', result.stdout + result.stderr)
            inventory = (output / 'inventory.json').read_text(encoding='utf-8')
            self.assertEqual(inventory, (FIXTURE.parent / 'inventory.json').read_text(encoding='utf-8'))
            report = readiness.assess(json.loads(inventory))
            self.assertEqual(report['summary'], {'blocker': 1, 'unknown': 1, 'review': 0, 'ready': 0})
            self.assertEqual(readiness.main([str(output / 'inventory.json'), '--output-dir', str(output),
                                             '--fail-on', 'never']), 0)
            for name in ('readiness.json', 'readiness.md'):
                self.assertEqual((output / name).read_text(encoding='utf-8'),
                                 (FIXTURE.parent / name).read_text(encoding='utf-8'))

    def test_cli_partial_evidence_returns_one_and_fatal_error_writes_nothing(self):
        for status, expected in [(403, 1), (401, 2)]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temp:
                transport = ScriptedTransport(reply([repository()]), reply(status=status))
                output = Path(temp) / 'collection'
                with patch.object(collector, 'LiveTransport', return_value=transport), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    code = collector.main(['--organization', 'synthetic-org', '--project', 'p', '--output-dir', str(output)])
                self.assertEqual(code, expected)
                self.assertEqual(output.exists(), expected == 1)
                if expected == 1:
                    self.assertIsNone(json.loads((output / 'inventory.json').read_text())['repositories'][0]['branches'])

    def test_cli_refuses_existing_output_and_invalid_fixture_without_network(self):
        with tempfile.TemporaryDirectory() as temp:
            existing = Path(temp) / 'inventory.json'
            existing.write_text('preserve me')
            with patch.object(collector, 'LiveTransport') as live, redirect_stderr(io.StringIO()):
                self.assertEqual(collector.main(['--fixture', str(FIXTURE), '--output-dir', temp]), 2)
                self.assertEqual(collector.main(['--fixture', str(FIXTURE), '--organization', 'org',
                                                 '--output-dir', str(Path(temp) / 'new')]), 2)
            live.assert_not_called()
            self.assertEqual(existing.read_text(), 'preserve me')


if __name__ == '__main__':
    unittest.main()
