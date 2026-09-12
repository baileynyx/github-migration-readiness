"""Validate and run the packaged product in a fresh directory outside checkout.

The ZIP is an executable input: run this only on a package you intend to trust.
Its adjacent SHA-256 and internal inventory detect corruption/inconsistent files;
neither proves authenticity. Source checkout paths and Python environment path
overrides are excluded from child commands so missing package files cannot be
silently supplied by the repository used to run this verifier.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import zipfile


def unpack(archive, destination):
    """Validate bounds, member paths, regular files and every inventory hash."""
    data = archive.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    checksum = archive.with_suffix('.zip.sha256').read_text(encoding='ascii')
    if checksum.strip() != f'{actual}  {archive.name}':
        raise ValueError('Archive checksum does not match its sidecar.')
    expected_root = archive.stem
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > 200 or sum(entry.file_size for entry in entries) > 20 * 1024 * 1024:
            raise ValueError('Package exceeds expected size limits.')
        if len(names) != len(set(names)):
            raise ValueError('Duplicate package members.')
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in entry.filename
                    or ':' in entry.filename or str(path) != entry.filename
                    or len(path.parts) < 2 or path.parts[0] != expected_root
                    or entry.is_dir() or (entry.external_attr >> 16) & 0o170000 != 0o100000):
                raise ValueError('Invalid package path or file type.')
        inventory = json.loads(package.read(f'{expected_root}/BUILD.json'))
        if (inventory.get('schema_version') != 1
                or not re.fullmatch(r'[0-9a-f]{40}', inventory.get('source_commit', ''))
                or expected_root != f"github-migration-readiness-{inventory.get('version')}"):
            raise ValueError('Invalid build identity.')
        files = inventory.get('files')
        if not isinstance(files, dict) or set(names) != {f'{expected_root}/{p}' for p in files} | {f'{expected_root}/BUILD.json'}:
            raise ValueError('Package contents do not match the build inventory.')
        for path, expected in files.items():
            if hashlib.sha256(package.read(f'{expected_root}/{path}')).hexdigest() != expected:
                raise ValueError(f'Packaged file checksum mismatch: {path}')
        # All members have been validated; extraction targets a new private root.
        package.extractall(destination)
    return destination / expected_root, inventory, actual


def check(archive, output):
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='migration-package-') as folder:
        root, inventory, checksum = unpack(archive, Path(folder))
        environment = {key: value for key, value in os.environ.items()
                       if key.upper() not in ('PYTHONPATH', 'PYTHONHOME', 'AZURE_DEVOPS_PAT')}
        observations = []

        def run(name, arguments, expected=0):
            result = subprocess.run([sys.executable, '-E', '-s', *arguments], cwd=root,
                                    env=environment, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, encoding='utf-8',
                                    timeout=120, check=False)
            if result.returncode != expected:
                raise ValueError(f'{name}: expected exit {expected}, got {result.returncode}: '
                                 f'{result.stderr[-2000:]}')
            observations.append({'command': name, 'exit_code': result.returncode})
            return result.stdout, result.stderr

        _, tests = run('packaged test suite', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        match = re.search(r'Ran (\d+) tests', tests)
        if not match or int(match[1]) != 63 or not re.search(r'^OK\s*$', tests, re.MULTILINE):
            raise ValueError('The package must contain and pass all 63 product tests.')
        counts, _ = run('six-repository assessment', ['readiness.py', 'examples/migration-assessment/inventory.json',
                        '--output-dir', 'reports/assessment', '--fail-on', 'never'])
        if json.loads(counts) != {'blocker': 1, 'unknown': 1, 'review': 3, 'ready': 1}:
            raise ValueError('Packaged assessment produced unexpected findings.')
        counts, _ = run('pre-migration classification', ['classify_repositories.py',
                        'examples/pre-migration/inventory.json', '--output-dir',
                        'reports/pre-migration', '--fail-on', 'never'])
        if json.loads(counts) != {'transformation_required': 2,
                                  'review_required': 1, 'standard': 1}:
            raise ValueError('Packaged pre-migration classification produced unexpected findings.')
        run('inventory blocking gate', ['readiness.py', 'examples/migration-assessment/inventory.json',
            '--output-dir', 'reports/assessment', '--fail-on', 'unready'], expected=1)
        result, _ = run('fixture collection', ['collect_azure_devops.py', '--fixture',
                        'examples/azure-devops/responses.json', '--output-dir', 'reports/collector'])
        if json.loads(result)['repositories'] != 2:
            raise ValueError('Expected two synthetic collected repositories.')
        result, _ = run('collected inventory assessment', ['readiness.py', 'reports/collector/inventory.json',
                        '--output-dir', 'reports/collector', '--fail-on', 'never'])
        if json.loads(result) != {'blocker': 1, 'unknown': 1, 'review': 0, 'ready': 0}:
            raise ValueError('Unexpected collected inventory assessment.')
        result, _ = run('ref difference gate', ['verify_refs.py', 'examples/ref-verification/source.refs',
                        'examples/ref-verification/destination.refs', '--output-dir', 'reports/refs'], expected=1)
        if json.loads(result)['counts'] != {'matched': 2, 'missing': 1, 'unexpected': 1, 'mismatched': 2}:
            raise ValueError('Unexpected packaged ref comparison.')
        result, _ = run('real Git rehearsal', ['rehearse_refs.py', '--output-dir', 'reports/rehearsal'])
        rehearsal = json.loads(result)
        if rehearsal['result'] != 'passed' or rehearsal['source_unchanged'] is not True:
            raise ValueError('Packaged Git rehearsal did not preserve source refs.')
        evidence = {'result': 'passed', 'version': inventory['version'],
                    'source_commit': inventory['source_commit'], 'archive_sha256': checksum,
                    'platform': sys.platform, 'python': sys.version.split()[0],
                    'packaged_tests_passed': 63, 'ran_outside_checkout': True,
                    'observations': observations, 'git_rehearsal': rehearsal}
    evidence['temporary_directory_removed'] = not root.parent.exists()
    (output / 'package-check.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(check(args.archive.resolve(), args.output_dir), indent=2))
        return 0
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.TimeoutExpired) as error:
        print(f'Package validation failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
