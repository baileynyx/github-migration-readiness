"""Unit/CLI checks plus a real Git rehearsal of intact and changed copies."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import rehearse_refs
import verify_refs

ROOT = Path(__file__).resolve().parents[1]


def capture(*records):
    return ''.join(f'{oid}\t{name}\n' for name, oid in records).encode()


class RefVerificationTests(unittest.TestCase):
    def test_committed_synthetic_reports_reproduce_from_captures(self):
        folder = ROOT / 'examples/ref-verification'
        result = verify_refs.compare((folder / 'source.refs').read_bytes(),
                                     (folder / 'destination.refs').read_bytes())
        self.assertEqual(result, json.loads((folder / 'refs.json').read_text()))
        self.assertEqual(verify_refs.markdown(result), (folder / 'refs.md').read_text())

    def test_matching_records_ignore_order_but_not_names(self):
        rows = [('refs/heads/main', 'a' * 40), ('refs/tags/light', 'b' * 40)]
        result = verify_refs.compare(capture(*rows), capture(*reversed(rows)))
        self.assertEqual(result['status'], 'match')
        self.assertEqual(result['counts']['matched'], 2)

    def test_missing_unexpected_and_mismatched_are_separate(self):
        source = capture(('refs/heads/main', 'a' * 40), ('refs/heads/old', 'b' * 40))
        target = capture(('refs/heads/main', 'b' * 40), ('refs/heads/new', 'c' * 40))
        result = verify_refs.compare(source, target)
        self.assertEqual(result['counts'], {'matched': 0, 'missing': 1, 'unexpected': 1, 'mismatched': 1})

    def test_tag_object_change_is_detected_when_peeled_commit_matches(self):
        source = capture(('refs/tags/v1', 'a' * 40), ('refs/tags/v1^{}', 'c' * 40))
        target = capture(('refs/tags/v1', 'b' * 40), ('refs/tags/v1^{}', 'c' * 40))
        result = verify_refs.compare(source, target)
        self.assertEqual(result['counts']['mismatched'], 1)
        self.assertEqual(result['findings'][0]['ref'], 'refs/tags/v1')

    def test_changed_and_missing_peeled_targets_are_detected(self):
        source = capture(('refs/tags/v1', 'a' * 40), ('refs/tags/v1^{}', 'b' * 40))
        for target, expected in ((capture(('refs/tags/v1', 'a' * 40)), 'missing'),
                                 (capture(('refs/tags/v1', 'a' * 40), ('refs/tags/v1^{}', 'c' * 40)), 'mismatched')):
            with self.subTest(expected=expected):
                result = verify_refs.compare(source, target)
                self.assertEqual(result['findings'][0]['kind'], 'peeled tag target')
                self.assertEqual(result['findings'][0]['status'], expected)

    def test_case_sensitive_names_are_not_collapsed(self):
        result = verify_refs.compare(capture(('refs/heads/Main', 'a' * 40)), capture(('refs/heads/main', 'a' * 40)))
        self.assertEqual(result['counts']['missing'], 1)
        self.assertEqual(result['counts']['unexpected'], 1)

    def test_one_empty_side_reports_all_missing_or_unexpected(self):
        one = capture(('refs/heads/main', 'a' * 40))
        self.assertEqual(verify_refs.compare(one, b'')['counts']['missing'], 1)
        self.assertEqual(verify_refs.compare(b'', one)['counts']['unexpected'], 1)

    def test_both_empty_is_inconclusive(self):
        with self.assertRaises(verify_refs.InvalidSnapshot): verify_refs.compare(b'', b'\n')

    def test_sha256_ids_supported_but_mixed_formats_rejected(self):
        value = capture(('refs/heads/main', 'a' * 64))
        self.assertEqual(verify_refs.compare(value, value)['status'], 'match')
        with self.assertRaises(verify_refs.InvalidSnapshot):
            verify_refs.compare(value, capture(('refs/heads/main', 'a' * 40)))
        with self.assertRaises(verify_refs.InvalidSnapshot):
            verify_refs.parse_snapshot(value + capture(('refs/heads/other', 'b' * 40)), 'test')

    def test_crlf_bom_and_no_final_newline_are_accepted(self):
        value = capture(('refs/heads/main', 'a' * 40))
        alternate = b'\xef\xbb\xbf' + value.replace(b'\n', b'\r\n')
        self.assertEqual(verify_refs.compare(value.rstrip(b'\n'), alternate)['status'], 'match')

    def test_duplicate_or_orphan_peeled_records_are_invalid(self):
        one = capture(('refs/heads/main', 'a' * 40))
        for value in (one + one, capture(('refs/tags/v1^{}', 'a' * 40)), capture(('refs/heads/main^{}', 'a' * 40))):
            with self.subTest(value=value), self.assertRaises(verify_refs.InvalidSnapshot):
                verify_refs.parse_snapshot(value, 'test')

    def test_malformed_and_out_of_scope_records_are_invalid(self):
        for value in (b'not an advertisement', b'\xff', capture(('HEAD', 'a' * 40)),
                      capture(('refs/pull/1/head', 'a' * 40)), capture(('refs/heads/main', '0' * 40)),
                      capture(('refs/heads/main', 'a' * 39)), capture(('refs/heads/main', 'A' * 40))):
            with self.subTest(value=value), self.assertRaises(verify_refs.InvalidSnapshot):
                verify_refs.parse_snapshot(value, 'test')

    def test_invalid_git_ref_names_are_rejected(self):
        for name in ('a b', 'a..b', '.hidden', 'foo.lock', 'a//b', 'a@{b', 'a\\b', 'a?', 'a[0]', 'a.', 'a~b', ''):
            with self.subTest(name=name):
                self.assertFalse(verify_refs.valid_ref('refs/heads/' + name))
        self.assertTrue(verify_refs.valid_ref('refs/heads/feature/éclair'))

    def test_report_escapes_markdown_and_html_in_valid_refs(self):
        name = 'refs/heads/<img>|`link`'
        result = verify_refs.compare(capture((name, 'a' * 40)), b'')
        report = verify_refs.markdown(result)
        self.assertNotIn('<img>', report)
        self.assertIn('&#124;', report)
        self.assertIn('&#96;', report)

    def test_oversized_snapshot_is_rejected(self):
        with self.assertRaises(verify_refs.InvalidSnapshot):
            verify_refs.parse_snapshot(b'x' * (verify_refs.MAX_BYTES + 1), 'test')

    def test_cli_codes_reports_and_refusal_to_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, destination = root / 'source.refs', root / 'destination.refs'
            source.write_bytes(capture(('refs/heads/main', 'a' * 40)))
            for index, (payload, code, status) in enumerate(((source.read_bytes(), 0, 'match'),
                    (capture(('refs/heads/main', 'b' * 40)), 1, 'different'), (b'bad', 2, 'invalid_input'))):
                destination.write_bytes(payload)
                output = root / str(index)
                args = [sys.executable, str(ROOT / 'verify_refs.py'), str(source), str(destination), '--output-dir', str(output)]
                result = subprocess.run(args, capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(json.loads((output / 'refs.json').read_text())['status'], status)
                before = (output / 'refs.md').read_bytes()
                self.assertEqual(subprocess.run(args, capture_output=True).returncode, 2)
                self.assertEqual((output / 'refs.md').read_bytes(), before)
                self.assertEqual(destination.read_bytes(), payload)

    def test_same_file_cannot_accidentally_validate_itself(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source.refs'
            source.write_bytes(capture(('refs/heads/main', 'a' * 40)))
            result = subprocess.run([sys.executable, str(ROOT / 'verify_refs.py'), str(source), str(source),
                                     '--output-dir', str(root / 'result')], capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_real_git_rehearsal_preserves_source_and_detects_tag_annotation_change(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'evidence'
            result = rehearse_refs.run_demo(output)
            self.assertEqual(result['result'], 'passed')
            self.assertTrue(result['source_unchanged'])
            broken = json.loads((output / 'broken/refs.json').read_text())
            self.assertEqual(broken['counts'], {'matched': 2, 'missing': 1, 'unexpected': 1, 'mismatched': 2})
            tag = next(x for x in broken['findings'] if x['ref'] == 'refs/tags/v1.0.0')
            self.assertEqual(tag['status'], 'mismatched')
            self.assertFalse(any(x['ref'].endswith('^{}') for x in broken['findings']))


if __name__ == '__main__': unittest.main()
