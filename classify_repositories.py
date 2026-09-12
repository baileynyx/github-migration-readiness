"""Classify repositories before migration scheduling.

This classifier consumes deliberately small, provider-neutral evidence. It does
not inspect repositories or prescribe universal limits. The supplied policy is
part of the evidence so reviewers can see exactly why a repository followed the
standard, review, or transformation path.
"""
import argparse
import html
import json
from pathlib import Path
import sys


POLICY_FIELDS = (
    'review_size_mb', 'transformation_size_mb', 'review_branch_count',
    'review_binary_mb', 'transformation_binary_mb',
)
REPOSITORY_FIELDS = {
    'source_kind': str,
    'size_mb': int,
    'branch_count': int,
    'binary_mb': int,
    'uses_lfs': bool,
    'history_rewrite_required': bool,
}
STATUSES = ('transformation_required', 'review_required', 'standard')


def validate(document):
    """Return validated policy and repositories without coercing evidence."""
    if not isinstance(document, dict) or type(document.get('schema_version')) is not int:
        raise ValueError('schema_version must be the integer 1')
    if document['schema_version'] != 1:
        raise ValueError('schema_version must be the integer 1')
    unexpected = set(document) - {'schema_version', 'policy', 'repositories'}
    if unexpected:
        raise ValueError(f'unsupported root fields: {sorted(unexpected)}')

    policy = document.get('policy')
    if not isinstance(policy, dict) or set(policy) != set(POLICY_FIELDS):
        raise ValueError(f'policy must contain exactly: {list(POLICY_FIELDS)}')
    for field in POLICY_FIELDS:
        if type(policy[field]) is not int or policy[field] < 0:
            raise ValueError(f'policy.{field} must be a nonnegative integer')
    if policy['review_size_mb'] >= policy['transformation_size_mb']:
        raise ValueError('review_size_mb must be lower than transformation_size_mb')
    if policy['review_binary_mb'] >= policy['transformation_binary_mb']:
        raise ValueError('review_binary_mb must be lower than transformation_binary_mb')

    repositories = document.get('repositories')
    if not isinstance(repositories, list) or not repositories:
        raise ValueError('repositories must be a nonempty list')
    names = set()
    for index, repository in enumerate(repositories):
        if not isinstance(repository, dict):
            raise ValueError(f'repositories[{index}] must be an object')
        name = repository.get('name')
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f'repositories[{index}].name must be a nonempty string')
        if name.casefold() in names:
            raise ValueError(f'duplicate repository: {name}')
        names.add(name.casefold())
        extra = set(repository) - (set(REPOSITORY_FIELDS) | {'name'})
        if extra:
            raise ValueError(f'{name}: unsupported fields: {sorted(extra)}')
        for field, expected in REPOSITORY_FIELDS.items():
            value = repository.get(field)
            # Null means the preflight did not establish the fact. It must
            # remain visible as review work rather than becoming a zero/false.
            if value is None:
                continue
            if type(value) is not expected:
                raise ValueError(f'{name}.{field} must be {expected.__name__} or null')
            if expected is int and value < 0:
                raise ValueError(f'{name}.{field} must be nonnegative')
        if repository.get('source_kind') not in (None, 'git', 'tfvc'):
            raise ValueError(f'{name}.source_kind must be git, tfvc, or null')
    return policy, repositories


def classify(document):
    """Apply the disclosed policy and retain every reason for the chosen path."""
    policy, repositories = validate(document)
    results = []
    for repository in sorted(repositories, key=lambda item: item['name'].casefold()):
        reasons = []

        def add(severity, field, message, action):
            reasons.append({'severity': severity, 'field': field,
                            'message': message, 'action': action})

        for field in REPOSITORY_FIELDS:
            if repository.get(field) is None:
                add('review', field, 'Evidence was not supplied.',
                    f'Collect and verify {field} before scheduling.')

        if repository.get('source_kind') == 'tfvc':
            add('transformation', 'source_kind', 'TFVC requires a conversion path.',
                'Plan and rehearse history transformation before the migration window.')
        if repository.get('history_rewrite_required') is True:
            add('transformation', 'history_rewrite_required',
                'The repository requires an intentional history rewrite.',
                'Define the rewrite mapping and reconciliation acceptance evidence.')

        for field, review_limit, transform_limit, label in (
            ('size_mb', policy['review_size_mb'], policy['transformation_size_mb'], 'Repository size'),
            ('binary_mb', policy['review_binary_mb'], policy['transformation_binary_mb'], 'Binary content'),
        ):
            value = repository.get(field)
            if value is not None and value >= transform_limit:
                add('transformation', field,
                    f'{label} is {value:,} MiB; policy transformation threshold is {transform_limit:,} MiB.',
                    'Rehearse a dedicated transformation path and allocate appropriate compute and network proximity.')
            elif value is not None and value >= review_limit:
                add('review', field,
                    f'{label} is {value:,} MiB; policy review threshold is {review_limit:,} MiB.',
                    'Review transfer method, timing and validation before scheduling.')

        branches = repository.get('branch_count')
        if branches is not None and branches >= policy['review_branch_count']:
            add('review', 'branch_count',
                f'Branch count is {branches:,}; policy review threshold is {policy["review_branch_count"]:,}.',
                'Confirm branch scope, owners and post-transfer ref reconciliation.')
        if repository.get('uses_lfs') is True:
            add('review', 'uses_lfs', 'Git LFS objects need a separate transfer and availability check.',
                'Inventory, transfer and verify LFS objects from a fresh clone.')

        severities = {reason['severity'] for reason in reasons}
        status = ('transformation_required' if 'transformation' in severities
                  else 'review_required' if 'review' in severities else 'standard')
        results.append({'name': repository['name'], 'status': status, 'reasons': reasons})
    summary = {status: sum(item['status'] == status for item in results) for status in STATUSES}
    return {'schema_version': 1, 'policy': policy, 'summary': summary,
            'repositories': results}


def markdown(report):
    """Render a review-safe report while escaping inventory-controlled text."""
    def cell(value):
        return html.escape(str(value)).replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')

    lines = [
        '# Pre-migration repository classification', '',
        'Classification reflects the supplied evidence and policy. It is a planning aid, not proof that a migration will succeed.', '',
        '| Repository | Path | Field | Reason | Next action |',
        '| --- | --- | --- | --- | --- |',
    ]
    for repository in report['repositories']:
        reasons = repository['reasons'] or [{
            'field': '—', 'message': 'No policy threshold was reached.',
            'action': 'Use the standard path, then complete normal rehearsal and acceptance checks.',
        }]
        for reason in reasons:
            values = (repository['name'], repository['status'], reason['field'],
                      reason['message'], reason['action'])
            lines.append('| ' + ' | '.join(cell(value) for value in values) + ' |')
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True,
                        help='New directory for classification.json and classification.md.')
    parser.add_argument('--fail-on', choices=('transformation', 'review', 'never'),
                        default='transformation')
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists():
            raise ValueError('Choose a new output directory.')
        report = classify(json.loads(args.inventory.read_text(encoding='utf-8')))
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / 'classification.json').write_text(
            json.dumps(report, indent=2) + '\n', encoding='utf-8')
        (args.output_dir / 'classification.md').write_text(markdown(report), encoding='utf-8')
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f'Classification failed: {error}', file=sys.stderr)
        return 2
    print(json.dumps(report['summary'], sort_keys=True))
    if args.fail_on == 'transformation':
        return int(report['summary']['transformation_required'] > 0)
    if args.fail_on == 'review':
        return int(any(report['summary'][status] for status in STATUSES[:2]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
