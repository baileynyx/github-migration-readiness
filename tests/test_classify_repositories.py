"""Test the policy boundaries used to schedule migration paths."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import classify_repositories as classifier


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            'review_size_mb': 2048,
            'transformation_size_mb': 5120,
            'review_branch_count': 50,
            'review_binary_mb': 100,
            'transformation_binary_mb': 1024,
        }
        self.repository = {
            'name': 'synthetic-service', 'source_kind': 'git', 'size_mb': 400,
            'branch_count': 8, 'binary_mb': 0, 'uses_lfs': False,
            'history_rewrite_required': False,
        }

    def document(self, repository=None, policy=None):
        return {'schema_version': 1, 'policy': policy or self.policy,
                'repositories': [repository or self.repository]}

    def result(self, repository=None):
        return classifier.classify(self.document(repository))['repositories'][0]

    def test_standard_repository(self):
        self.assertEqual(self.result()['status'], 'standard')

    def test_tfvc_requires_transformation(self):
        self.assertEqual(self.result(dict(self.repository, source_kind='tfvc'))['status'], 'transformation_required')

    def test_size_thresholds_are_inclusive(self):
        self.assertEqual(self.result(dict(self.repository, size_mb=2048))['status'], 'review_required')
        self.assertEqual(self.result(dict(self.repository, size_mb=5120))['status'], 'transformation_required')

    def test_binary_thresholds_are_inclusive(self):
        self.assertEqual(self.result(dict(self.repository, binary_mb=100))['status'], 'review_required')
        self.assertEqual(self.result(dict(self.repository, binary_mb=1024))['status'], 'transformation_required')

    def test_branch_complexity_requires_review(self):
        self.assertEqual(self.result(dict(self.repository, branch_count=50))['status'], 'review_required')

    def test_lfs_requires_review(self):
        self.assertEqual(self.result(dict(self.repository, uses_lfs=True))['status'], 'review_required')

    def test_unknown_is_never_standard(self):
        result = self.result({'name': 'unknown'})
        self.assertEqual(result['status'], 'review_required')
        self.assertEqual(len(result['reasons']), len(classifier.REPOSITORY_FIELDS))

    def test_bad_types_and_unknown_fields_are_rejected(self):
        for changed in (dict(self.repository, size_mb=True), dict(self.repository, surprise='value')):
            with self.subTest(repository=changed):
                with self.assertRaises(ValueError):
                    classifier.classify(self.document(changed))

    def test_invalid_policy_order_is_rejected(self):
        policy = copy.deepcopy(self.policy)
        policy['review_size_mb'] = policy['transformation_size_mb']
        with self.assertRaises(ValueError):
            classifier.classify(self.document(policy=policy))

    def test_names_are_unique_ignoring_case(self):
        second = dict(self.repository, name=self.repository['name'].upper())
        document = self.document()
        document['repositories'].append(second)
        with self.assertRaises(ValueError):
            classifier.classify(document)

    def test_markdown_escapes_inventory_text(self):
        result = classifier.classify(self.document(dict(self.repository, name='<b>|repo')))
        rendered = classifier.markdown(result)
        self.assertNotIn('<b>', rendered)
        self.assertIn('&#124;', rendered)

    def test_cli_writes_both_reports_and_exposes_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory = root / 'inventory.json'
            inventory.write_text(json.dumps(self.document(dict(self.repository, source_kind='tfvc'))), encoding='utf-8')
            output = root / 'reports'
            self.assertEqual(classifier.main([str(inventory), '--output-dir', str(output)]), 1)
            self.assertTrue((output / 'classification.json').is_file())
            self.assertTrue((output / 'classification.md').is_file())
            self.assertEqual(classifier.main([str(inventory), '--output-dir', str(output)]), 2)

    def test_committed_sample_reports_reproduce(self):
        inventory = json.loads(Path('examples/pre-migration/inventory.json').read_text(encoding='utf-8'))
        report = classifier.classify(inventory)
        self.assertEqual(report['summary'], {
            'transformation_required': 2, 'review_required': 1, 'standard': 1,
        })
        expected_json = json.loads(Path('examples/pre-migration/classification.json').read_text(encoding='utf-8'))
        expected_markdown = Path('examples/pre-migration/classification.md').read_text(encoding='utf-8')
        self.assertEqual(report, expected_json)
        self.assertEqual(classifier.markdown(report), expected_markdown)


if __name__ == '__main__':
    unittest.main()
