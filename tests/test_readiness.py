"""Exercise the evidence boundaries that can cause false readiness decisions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import readiness


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.repo = json.loads(Path('examples/inventory.json').read_text())['repositories'][0]

    def report(self, repo=None):
        return readiness.assess({'schema_version': 1, 'repositories': [repo or self.repo]})

    def test_explicit_clean_inventory(self):
        self.assertEqual(self.report()['repositories'][0]['status'], 'ready')

    def test_missing_evidence_is_unknown(self):
        report = self.report({'name': 'unknown'})['repositories'][0]
        self.assertEqual(report['status'], 'unknown')
        self.assertEqual(len(report['findings']), len(readiness.FIELDS))

    def test_absent_default_ref_blocks(self):
        self.repo['branches'] = ['develop']
        self.assertEqual(self.report()['repositories'][0]['status'], 'blocker')

    def test_identity_mapping_blocks(self):
        self.repo['unmapped_identities'] = ['contractor']
        self.assertEqual(self.report()['repositories'][0]['status'], 'blocker')

    def test_false_string_is_rejected(self):
        self.repo['archived'] = 'false'
        with self.assertRaises(ValueError): self.report()

    def test_typo_is_rejected(self):
        self.repo['uses_lsf'] = False
        with self.assertRaises(ValueError): self.report()

    def test_empty_inventory_is_not_ready(self):
        with self.assertRaises(ValueError): readiness.assess({'schema_version': 1, 'repositories': []})

    def test_case_insensitive_duplicates_rejected(self):
        second = dict(self.repo, name=self.repo['name'].upper())
        with self.assertRaises(ValueError): readiness.assess({'schema_version': 1, 'repositories': [self.repo, second]})

    def test_review_is_not_ready(self):
        for field, value in [('archived', True), ('uses_lfs', True), ('hooks', ['hook']), ('pipeline_dependencies', ['feed'])]:
            with self.subTest(field=field):
                self.assertEqual(self.report(dict(self.repo, **{field: value}))['repositories'][0]['status'], 'review')

    def test_deterministic_sorting(self):
        repos = [self.repo, dict(self.repo, name='another')]
        self.assertEqual(readiness.assess({'schema_version': 1, 'repositories': repos}), readiness.assess({'schema_version': 1, 'repositories': list(reversed(repos))}))

    def test_markdown_escapes_input(self):
        text = readiness.markdown(self.report(dict(self.repo, name='<script>|\nrepo')))
        self.assertNotIn('<script>', text)
        self.assertIn('&#124;', text)

    def test_cli_exit_and_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory = Path(temp) / 'inventory.json'
            inventory.write_text(json.dumps({'schema_version': 1, 'repositories': [{'name': 'unknown'}]}))
            self.assertEqual(readiness.main([str(inventory), '--output-dir', temp, '--fail-on', 'unready']), 1)
            self.assertTrue((Path(temp) / 'readiness.md').is_file())
            inventory.write_text('{broken')
            self.assertEqual(readiness.main([str(inventory), '--output-dir', temp]), 2)


if __name__ == '__main__': unittest.main()
