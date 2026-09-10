"""Build a repeatable source ZIP from an explicit committed file list.

Read Git objects, not checkout bytes: Windows line-ending conversion, untracked
files and local edits must not change the payload for a given commit. ZIP_STORED,
fixed timestamps, sorted paths and fixed permissions avoid host-specific archive
metadata or compression-library differences. The checksum establishes integrity,
not signer identity; this builder does not attest or publish a release.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import zipfile


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            stdin=subprocess.DEVNULL, timeout=60, check=False)
    if result.returncode:
        raise ValueError('Cannot read committed release inputs: ' + result.stderr.decode('utf-8', errors='replace')[-500:])
    return result.stdout


def package_bytes(version, commit, files):
    """Create one top-level folder and a per-file inventory inside the ZIP."""
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('VERSION must contain a stable major.minor.patch version.')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Expected a full Git SHA-1 commit ID.')
    root = f'github-migration-readiness-{version}'
    inventory = {'schema_version': 1, 'version': version, 'source_commit': commit,
                 'files': {path: sha256(data) for path, data in sorted(files.items())}}
    payload = dict(files)
    payload['BUILD.json'] = (json.dumps(inventory, indent=2, sort_keys=True) + '\n').encode('utf-8')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        for path, data in sorted(payload.items()):
            candidate = PurePosixPath(path)
            if (candidate.is_absolute() or '..' in candidate.parts or '\\' in path
                    or ':' in path or str(candidate) != path or path == '.'):
                raise ValueError(f'Unsafe release path: {path}')
            entry = zipfile.ZipInfo(f'{root}/{path}', date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data)
    return root, output.getvalue()


def build(repo, output):
    if output.exists():
        raise ValueError('Choose a new package output directory.')
    commit = git(repo, 'rev-parse', '--verify', 'HEAD^{commit}').decode('ascii').strip()
    version = git(repo, 'show', f'{commit}:VERSION').decode('utf-8').strip()
    manifest = git(repo, 'show', f'{commit}:RELEASE_FILES.txt').decode('utf-8').splitlines()
    paths = [line for line in manifest if line and not line.startswith('#')]
    if not paths or len(paths) != len(set(paths)) or 'BUILD.json' in paths:
        raise ValueError('Release manifest is empty, duplicated or reserves BUILD.json.')
    # Only ordinary Git blobs may enter the package, never symlinks/submodules.
    entries = {}
    for entry in git(repo, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if entry:
            info, path = entry.split(b'\t', 1)
            entries[path.decode('utf-8')] = info.split()[0]
    files = {}
    for path in paths:
        if entries.get(path) not in (b'100644', b'100755'):
            raise ValueError(f'Release file is missing or not a regular file: {path}')
        files[path] = git(repo, 'show', f'{commit}:{path}')
    name, data = package_bytes(version, commit, files)
    output.mkdir(parents=True, exist_ok=False)
    archive = output / f'{name}.zip'
    archive.write_bytes(data)
    archive.with_suffix('.zip.sha256').write_text(f'{sha256(data)}  {archive.name}\n', encoding='ascii')
    return {'archive': archive.name, 'sha256': sha256(data), 'source_commit': commit,
            'version': version, 'files': len(files) + 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('dist'))
    args = parser.parse_args()
    try:
        print(json.dumps(build(Path(__file__).resolve().parent, args.output_dir), sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f'Package build failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
