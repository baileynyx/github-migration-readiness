"""Demonstrate ref verification with disposable, local-only Git repositories.

The source contains two branches, a lightweight tag and an annotated tag. The
matching copy is checked first, then only the disposable destination is changed.
No existing repository, remote URL, credentials or network transport is used.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import verify_refs


def git(root, *arguments, input_text=None):
    """Isolate Git configuration and permit only local file transport.

    Removing inherited GIT_* settings prevents a caller's worktree, object store
    or injected config from redirecting this disposable experiment elsewhere.
    Stable author metadata makes fixture object IDs reproducible.
    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_TERMINAL_PROMPT='0', GIT_AUTHOR_NAME='Ref Verification Demo',
                       GIT_AUTHOR_EMAIL='demo@example.invalid', GIT_COMMITTER_NAME='Ref Verification Demo',
                       GIT_COMMITTER_EMAIL='demo@example.invalid',
                       GIT_AUTHOR_DATE='2000-01-01T00:00:00+0000',
                       GIT_COMMITTER_DATE='2000-01-01T00:00:00+0000')
    command = ['git', '-c', 'protocol.allow=never', '-c', 'protocol.file.allow=always',
               '-c', 'commit.gpgSign=false', '-c', 'tag.gpgSign=false', '-C', str(root), *arguments]
    result = subprocess.run(command, input=input_text, capture_output=True, text=True,
                            encoding='utf-8', env=environment, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError(f'Local Git {arguments[0]} failed (exit {result.returncode}).')
    return result.stdout.strip()


def snapshot(repository):
    """Capture the actual advertisement, including annotated-tag peeled refs."""
    output = git(repository.parent, 'ls-remote', '--heads', '--tags', str(repository))
    return (output + '\n' if output else '').encode('utf-8')


def run_demo(output):
    if output.exists():
        raise ValueError('Choose a new rehearsal output directory.')
    observations = []
    with tempfile.TemporaryDirectory(prefix='git-ref-rehearsal-') as folder:
        root = Path(folder)
        source, destination = root / 'source.git', root / 'destination.git'
        git(root, 'init', '--bare', '--initial-branch=main', '--object-format=sha1', str(source))
        blob = git(source, 'hash-object', '-w', '--stdin', input_text='Synthetic ref verification fixture.\n')
        tree = git(source, 'mktree', input_text=f'100644 blob {blob}\tREADME.md\n')
        first = git(source, 'commit-tree', tree, '-m', 'Synthetic initial commit')
        second = git(source, 'commit-tree', tree, '-p', first, '-m', 'Synthetic second commit')
        git(source, 'update-ref', 'refs/heads/main', second)
        git(source, 'update-ref', 'refs/heads/feature', first)
        git(source, 'tag', 'lightweight', first)
        git(source, 'tag', '-a', 'v1.0.0', '-m', 'Synthetic release annotation', first)
        git(root, 'clone', '--bare', '--no-hardlinks', str(source), str(destination))
        source_bytes = snapshot(source)
        output.mkdir(parents=True, exist_ok=False)
        source_path = output / 'source.refs'
        source_path.write_bytes(source_bytes)

        for name, expected, counts in (
            ('matching', 0, {'matched': 5, 'missing': 0, 'unexpected': 0, 'mismatched': 0}),
            ('broken', 1, {'matched': 2, 'missing': 1, 'unexpected': 1, 'mismatched': 2}),
        ):
            if name == 'broken':
                git(destination, 'update-ref', '-d', 'refs/heads/feature')
                git(destination, 'update-ref', 'refs/heads/destination-only', second)
                git(destination, 'update-ref', 'refs/heads/main', first)
                # Same peeled commit, different annotation: matching commit IDs
                # alone must not hide the change to the annotated tag object.
                git(destination, 'tag', '-f', '-a', 'v1.0.0', '-m', 'Changed annotation, same target', first)
            capture = output / f'{name}.refs'
            capture.write_bytes(snapshot(destination))
            report_dir = output / name
            result = subprocess.run([sys.executable, str(Path(__file__).with_name('verify_refs.py')),
                                     str(source_path), str(capture), '--output-dir', str(report_dir)],
                                    capture_output=True, text=True, timeout=30, check=False)
            if result.returncode != expected:
                raise RuntimeError(f'{name}: expected comparator exit {expected}, got {result.returncode}.')
            report = json.loads((report_dir / 'refs.json').read_text())
            if report['counts'] != counts:
                raise RuntimeError(f'{name}: findings did not match the deliberately constructed scenario.')
            observations.append({'scenario': name, 'exit_code': result.returncode, 'counts': report['counts']})
        if snapshot(source) != source_bytes:
            raise RuntimeError('Source refs changed during the comparison rehearsal.')
    evidence = {'result': 'passed', 'scope': 'disposable local Git repositories only',
                'observed_at': datetime.now(timezone.utc).isoformat(), 'source_unchanged': True,
                'observations': observations}
    (output / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run_demo(args.output_dir), indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'Ref rehearsal failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__': sys.exit(main())
