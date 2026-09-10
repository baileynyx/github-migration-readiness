"""Compare captured Git branch/tag advertisements without accessing repositories.

Input is raw `git ls-remote --heads --tags` output, including peeled tag records.
Exit 0 means the supplied nonempty ref sets match; 1 means differences; 2 means
invalid/inconclusive input or I/O failure. This is not full migration acceptance.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 10 * 1024 * 1024
RECORD = re.compile(r'([0-9a-f]{40}|[0-9a-f]{64})\t([^\t\r\n]+)')


class InvalidSnapshot(ValueError):
    """Evidence cannot support a reliable ref comparison."""


def valid_ref(name):
    """Validate fully qualified branch/tag names using Git's ref-name rules.

    Treat names as case-sensitive opaque identifiers, never normalize slashes,
    Unicode or case. The ^{} suffix is handled separately as tag metadata.
    """
    if not name.startswith(('refs/heads/', 'refs/tags/')):
        return False
    if name.endswith('.') or '..' in name or '@{' in name:
        return False
    if any(ord(c) <= 32 or ord(c) == 127 or c in '~^:?*[\\' for c in name):
        return False
    return all(part and not part.startswith('.') and not part.endswith('.lock')
               for part in name.split('/'))


def parse_snapshot(payload, label):
    """Reject malformed or ambiguous records rather than dropping evidence."""
    if len(payload) > MAX_BYTES:
        raise InvalidSnapshot(f'{label}: snapshot exceeds the 10 MiB limit.')
    try:
        text = payload.decode('utf-8-sig')
    except UnicodeError as error:
        raise InvalidSnapshot(f'{label}: snapshot must be UTF-8.') from error
    refs, widths = {}, set()
    for number, line in enumerate(text.split('\n'), 1):
        # Accept Windows line endings without modifying the ref name itself.
        if line.endswith('\r'):
            line = line[:-1]
        if not line:
            continue
        match = RECORD.fullmatch(line)
        if not match:
            raise InvalidSnapshot(f'{label}: line {number} must contain an object ID, tab and ref name.')
        oid, name = match.groups()
        peeled = name.endswith('^{}')
        base = name[:-3] if peeled else name
        if not valid_ref(base) or (peeled and not base.startswith('refs/tags/')):
            raise InvalidSnapshot(f'{label}: line {number} has an invalid or out-of-scope ref name.')
        if set(oid) == {'0'}:
            raise InvalidSnapshot(f'{label}: line {number} contains a null object ID.')
        if name in refs:
            raise InvalidSnapshot(f'{label}: duplicate ref records are not supported.')
        refs[name] = oid
        widths.add(len(oid))
    if len(widths) > 1:
        raise InvalidSnapshot(f'{label}: mixed Git object-ID formats are not supported.')
    for name in refs:
        if name.endswith('^{}') and name[:-3] not in refs:
            raise InvalidSnapshot(f'{label}: peeled tag record has no corresponding tag object record.')
    return refs


def compare(source_payload, destination_payload):
    """Compare both tag-object IDs and peeled targets, without hiding extras."""
    source = parse_snapshot(source_payload, 'source')
    destination = parse_snapshot(destination_payload, 'destination')
    if not source and not destination:
        raise InvalidSnapshot('Both snapshots are empty; confirm collection and scope before acceptance.')
    if source and destination and len(next(iter(source.values()))) != len(next(iter(destination.values()))):
        raise InvalidSnapshot('Source and destination use different Git object-ID formats.')
    counts = dict.fromkeys(('matched', 'missing', 'unexpected', 'mismatched'), 0)
    findings = []
    for name in sorted(source.keys() | destination.keys()):
        before, after = source.get(name), destination.get(name)
        if before is None:
            status = 'unexpected'
        elif after is None:
            status = 'missing'
        elif before != after:
            status = 'mismatched'
        else:
            status = 'matched'
        counts[status] += 1
        if status != 'matched':
            kind = 'peeled tag target' if name.endswith('^{}') else 'branch' if name.startswith('refs/heads/') else 'tag'
            findings.append({'ref': name, 'kind': kind, 'status': status,
                             'source_oid': before, 'destination_oid': after})
    return {'schema_version': 1, 'status': 'different' if findings else 'match',
            'scope': 'advertised refs/heads and refs/tags, including peeled tag targets',
            'source_snapshot_sha256': hashlib.sha256(source_payload).hexdigest(),
            'destination_snapshot_sha256': hashlib.sha256(destination_payload).hexdigest(),
            'source_records': len(source), 'destination_records': len(destination),
            'counts': counts, 'findings': findings}


def escape(value):
    """Keep snapshot-controlled names from becoming Markdown/HTML syntax."""
    text = html.escape(value)
    for character in ('|', '`', '[', ']', '*', '_', '\\'):
        text = text.replace(character, f'&#{ord(character)};')
    return text


def markdown(report):
    titles = {'match': 'MATCH', 'different': 'DIFFERENCES FOUND', 'invalid_input': 'INVALID OR INCONCLUSIVE INPUT'}
    lines = ['# Git ref verification', '', f'**Result: {titles[report["status"]]}**', '',
             'This compares supplied branch/tag snapshots; it does not certify a complete migration.', '']
    if report['status'] == 'invalid_input':
        return '\n'.join(lines + [escape(report['error']), ''])
    lines += [f'Source snapshot SHA-256: {report["source_snapshot_sha256"]}', '',
              f'Destination snapshot SHA-256: {report["destination_snapshot_sha256"]}', '',
              '| Comparison | Ref records |', '| --- | ---: |']
    lines += [f'| {status} | {count} |' for status, count in report['counts'].items()]
    lines += ['', 'Annotated tags count as a tag-object record plus a peeled-target record.', '',
              '## Differences', '', '| Ref | Kind | Finding | Source object ID | Destination object ID |',
              '| --- | --- | --- | --- | --- |']
    for finding in report['findings']:
        lines.append('| ' + ' | '.join(escape(str(finding[key] or 'absent')) for key in
                     ('ref', 'kind', 'status', 'source_oid', 'destination_oid')) + ' |')
    if not report['findings']:
        lines.append('| None | — | All supplied records match. | — | — |')
    lines += ['', '## Review actions', '',
              '- Missing: investigate export/import scope and collection permissions.',
              '- Unexpected: identify destination-only work before considering reconciliation.',
              '- Mismatched: investigate new writes, rewritten history or changed tag objects.',
              '- Do not overwrite either repository based only on this report.', '',
              'Limits: snapshots do not verify default branch, complete object availability, LFS, submodules,',
              'hidden refs, permissions, pull requests, work items, hooks or pipeline behavior.',
              'Capture both sides during an agreed write freeze and retain collection provenance.', '']
    return '\n'.join(lines)


def write_reports(directory, report):
    """Require a fresh directory so previous evidence is never overwritten."""
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'refs.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (directory / 'refs.md').write_text(markdown(report), encoding='utf-8')


def read_snapshot(path):
    with path.open('rb') as stream:
        # Parsing enforces the bound; read at most one byte beyond it.
        return stream.read(MAX_BYTES + 1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True, help='New report directory')
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.exit(2, 'Choose a new report directory; existing output is not overwritten.\n')
    try:
        if args.source.resolve() == args.destination.resolve():
            raise InvalidSnapshot('Source and destination must be separate snapshot files.')
        report = compare(read_snapshot(args.source), read_snapshot(args.destination))
        code = 1 if report['status'] == 'different' else 0
    except (OSError, InvalidSnapshot) as error:
        message = str(error) if isinstance(error, InvalidSnapshot) else 'Unable to read a snapshot.'
        report = {'schema_version': 1, 'status': 'invalid_input', 'error': message}
        code = 2
    try:
        write_reports(args.output_dir, report)
    except OSError:
        parser.exit(2, 'Unable to create both reports in a fresh output directory.\n')
    print(json.dumps({'status': report['status'], 'counts': report.get('counts'), 'exit_code': code}, sort_keys=True))
    return code


if __name__ == '__main__': sys.exit(main())
