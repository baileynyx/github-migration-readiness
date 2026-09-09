"""Keep the published walkthrough reproducible and its gate claims accurate.

These tests execute the public CLI with the committed fictional inventory. They
guard against stale report artifacts and a demonstration that silently stops
covering one of the four outcomes; they do not represent a live migration.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'migration-assessment'


class SampleAssessmentTests(unittest.TestCase):
    def run_cli(self, output_dir, fail_on):
        """Use an isolated output directory so checks cannot alter checked-in evidence."""
        return subprocess.run(
            [sys.executable, str(ROOT / 'readiness.py'), str(SAMPLE / 'inventory.json'),
             '--output-dir', str(output_dir), '--fail-on', fail_on],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )

    def test_sample_outcomes_and_unknown_evidence(self):
        """Require the promised scenario outcomes and all five discovery gaps."""
        with tempfile.TemporaryDirectory() as output:
            result = self.run_cli(output, 'never')
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((Path(output) / 'readiness.json').read_text(encoding='utf-8'))
        self.assertEqual(report['summary'], {'blocker': 1, 'unknown': 1, 'review': 3, 'ready': 1})
        repos = {repo['name']: repo for repo in report['repositories']}
        self.assertEqual({name: repo['status'] for name, repo in repos.items()}, {
            'synthetic-catalog-api': 'ready',
            'synthetic-legacy-orders': 'blocker',
            'synthetic-media-assets': 'review',
            'synthetic-release-tools': 'review',
            'synthetic-audit-archive': 'review',
            'synthetic-undiscovered-worker': 'unknown',
        })
        self.assertEqual(
            {finding['field'] for finding in repos['synthetic-undiscovered-worker']['findings']},
            {'branches', 'uses_lfs', 'hooks', 'pipeline_dependencies', 'unmapped_identities'},
        )

    def test_committed_reports_reproduce_from_cli(self):
        """Detect documentation drift using actual CLI output, including field resolutions.

        Read as text to tolerate Git's line-ending conversion on Windows while
        preserving exact report content, ordering and whitespace comparisons.
        """
        with tempfile.TemporaryDirectory() as output:
            result = self.run_cli(output, 'never')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {'blocker': 1, 'ready': 1, 'review': 3, 'unknown': 1})
            for filename in ('readiness.json', 'readiness.md'):
                with self.subTest(filename=filename):
                    self.assertEqual(
                        (Path(output) / filename).read_text(encoding='utf-8'),
                        (SAMPLE / filename).read_text(encoding='utf-8'),
                    )

    def test_findings_fail_both_gates_and_still_write_reports(self):
        """An expected gate failure must retain the report needed for remediation."""
        for fail_on in ('blocker', 'unready'):
            with self.subTest(fail_on=fail_on), tempfile.TemporaryDirectory() as output:
                result = self.run_cli(output, fail_on)
                self.assertEqual(result.returncode, 1, result.stderr)
                for filename in ('readiness.json', 'readiness.md'):
                    self.assertTrue((Path(output) / filename).is_file())


if __name__ == '__main__':
    unittest.main()
