"""Assess a normalized migration inventory without contacting source providers.

The schema deliberately preserves the difference between empty and missing data:
an explicit empty list means the collector observed no dependencies; an omitted
or null value means nobody has established that fact yet. This is an assessment,
not a migration engine or a substitute for a complete provider export.
"""
import argparse
import json
from pathlib import Path
import sys

FIELDS = {
    'owner': str, 'default_branch': str, 'branches': list, 'archived': bool,
    'uses_lfs': bool, 'hooks': list, 'pipeline_dependencies': list,
    'unmapped_identities': list,
}


def validate(data):
    """Reject malformed evidence rather than silently converting it to a pass."""
    if not isinstance(data, dict) or data.get('schema_version') != 1 or type(data.get('schema_version')) is not int:
        raise ValueError('schema_version must be the integer 1')
    repos = data.get('repositories')
    if not isinstance(repos, list) or not repos:
        raise ValueError('repositories must be a nonempty list')
    names = set()
    for index, repo in enumerate(repos):
        if not isinstance(repo, dict):
            raise ValueError(f'repositories[{index}] must be an object')
        name = repo.get('name')
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f'repositories[{index}].name must be a nonempty string')
        if name.casefold() in names:
            raise ValueError(f'duplicate repository: {name}')
        names.add(name.casefold())
        unexpected = set(repo) - (set(FIELDS) | {'name'})
        if unexpected:
            raise ValueError(f'{name}: unsupported fields: {sorted(unexpected)}')
        for field, expected in FIELDS.items():
            value = repo.get(field)
            if value is None:
                continue
            if type(value) is not expected:
                raise ValueError(f'{name}.{field} must be {expected.__name__} or null')
            if expected is list and any(not isinstance(item, str) or not item.strip() for item in value):
                raise ValueError(f'{name}.{field} must contain nonempty strings')
    return repos


def assess(data):
    """Produce stable output; unknown facts and review items cannot be ready."""
    results = []
    for repo in sorted(validate(data), key=lambda value: value['name'].casefold()):
        findings = []

        def add(severity, field, message, action):
            findings.append(dict(severity=severity, field=field, message=message, action=action))

        for field in FIELDS:
            if repo.get(field) is None:
                add('unknown', field, 'Evidence was not supplied.', f'Collect and verify {field}.')
        for field in ('owner', 'default_branch'):
            if isinstance(repo.get(field), str) and not repo[field].strip():
                add('blocker', field, 'Required value is empty.', f'Assign a valid {field}.')
        branch = repo.get('default_branch')
        branches = repo.get('branches')
        if branches is not None and branch and branch not in branches:
            add('blocker', 'branches', 'Default branch is absent from the ref inventory.', 'Reconcile the default branch and exported refs.')
        if repo.get('archived') is True:
            add('review', 'archived', 'Repository is archived.', 'Confirm inclusion and preserve read-only intent at cutover.')
        if repo.get('uses_lfs') is True:
            add('review', 'uses_lfs', 'Git LFS objects require separate verification.', 'Transfer LFS objects and verify availability from a fresh clone.')
        for field, message, action in (
            ('hooks', 'Service hooks require target reconfiguration.', 'Recreate and test hooks with target credentials.'),
            ('pipeline_dependencies', 'External pipeline dependencies exist.', 'Map pipelines, agents, service connections, secrets and artifact feeds.'),
            ('unmapped_identities', 'Identity mappings are unresolved.', 'Resolve target identities and verify permissions with owners.'),
        ):
            if repo.get(field):
                add('blocker' if field == 'unmapped_identities' else 'review', field, message, action)
        severities = {finding['severity'] for finding in findings}
        status = next((state for state in ('blocker', 'unknown', 'review') if state in severities), 'ready')
        results.append({'name': repo['name'], 'status': status, 'findings': findings})
    return {'schema_version': 1, 'summary': {state: sum(r['status'] == state for r in results) for state in ('blocker', 'unknown', 'review', 'ready')}, 'repositories': results}


def markdown(report):
    """Escape inventory-controlled HTML and table delimiters in review reports."""
    import html
    def cell(value):
        return html.escape(str(value)).replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')
    lines = ['# Migration readiness assessment', '', 'Readiness describes the supplied inventory; it does not certify migration completeness.', '', '| Repository | Status | Field | Finding | Resolution |', '| --- | --- | --- | --- | --- |']
    for repo in report['repositories']:
        for finding in repo['findings'] or [{'field': '—', 'message': 'No findings in supplied inventory.', 'action': 'Proceed to rehearsal and provider-specific checks.'}]:
            lines.append('| ' + ' | '.join(cell(v) for v in (repo['name'], repo['status'], finding['field'], finding['message'], finding['action'])) + ' |')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('reports'))
    parser.add_argument('--fail-on', choices=('blocker', 'unready', 'never'), default='blocker')
    args = parser.parse_args(argv)
    try:
        report = assess(json.loads(args.inventory.read_text(encoding='utf-8')))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / 'readiness.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        (args.output_dir / 'readiness.md').write_text(markdown(report), encoding='utf-8')
    except (OSError, ValueError) as error:
        print(f'Assessment failed: {error}', file=sys.stderr)
        return 2
    print(json.dumps(report['summary'], sort_keys=True))
    return int(args.fail_on == 'blocker' and report['summary']['blocker'] > 0 or args.fail_on == 'unready' and any(r['status'] != 'ready' for r in report['repositories']))


if __name__ == '__main__':
    sys.exit(main())
