"""Bounded strict JSON input and exclusively created replay-verifiable bundles."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
from .analysis import build_report, canonical
from .certificates import check_certificates
from .render import render_html

MAX_BYTES = 4 * 1024 * 1024
FILES = {'model.json', 'requirements.json', 'report.json', 'review.html', 'manifest.json'}


def read_bytes(path, limit=MAX_BYTES, no_symlink=False):
    flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)
    if no_symlink:
        flags |= getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError('bounded regular file required')
        value = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(value) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('input too large or changed during read')
        return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _constant(_value):
    raise ValueError('nonfinite JSON number')


def decode(raw):
    try:
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, RecursionError) as error:
        raise ValueError('invalid UTF8 or JSON nesting') from error
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise ValueError('JSON nesting limit exceeded')
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError('nonfinite JSON number')
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    return value


def read_json(path):
    return decode(read_bytes(path))


def bundle_contents(data, requirements):
    report = build_report(data, requirements)
    check_certificates(data, requirements, report['property_results'])
    files = {'model.json': canonical(data), 'requirements.json': canonical(requirements),
             'report.json': canonical(report), 'review.html': render_html(data, report).encode()}
    if any(len(value) > MAX_BYTES for value in files.values()):
        raise ValueError('output exceeds bundle limits')
    manifest = {'schema_version': 1, 'files': {name: {'sha256': hashlib.sha256(value).hexdigest(),
                                                  'bytes': len(value)} for name, value in sorted(files.items())}}
    files['manifest.json'] = canonical(manifest)
    return files, report


def create_bundle(destination, data, requirements):
    files, report = bundle_contents(data, requirements)
    path = Path(destination)
    # Exclusive directory creation prevents overwriting inputs or prior runs.
    path.mkdir(mode=0o700)
    try:
        for name, value in files.items():
            with (path / name).open('xb') as stream:
                stream.write(value)
    except (OSError, ValueError):
        shutil.rmtree(path)
        raise
    return report


def verify_bundle(destination):
    path = Path(destination)
    if path.is_symlink() or not path.is_dir() or {p.name for p in path.iterdir()} != FILES:
        raise ValueError('exact bundle directory required')
    actual = {}
    for name in sorted(FILES):
        item = path / name
        if item.is_symlink():
            raise ValueError('bundle symlinks forbidden')
        actual[name] = read_bytes(item, no_symlink=True)
    data, requirements = decode(actual['model.json']), decode(actual['requirements.json'])
    supplied = decode(actual['report.json'])
    if not isinstance(supplied, dict) or 'property_results' not in supplied:
        raise ValueError('report certificate inventory required')
    check_certificates(data, requirements, supplied['property_results'])
    expected, report = bundle_contents(data, requirements)
    if actual != expected:
        raise ValueError('bundle differs from recomputed analysis')
    return report



def compare_bundles(baseline, scenario):
    left, right = verify_bundle(baseline), verify_bundle(scenario)
    if left['model_sha256'] != right['model_sha256']:
        raise ValueError('comparison requires the same captured model')
    old_policy, new_policy = dict(left['requirements']), dict(right['requirements'])
    old_disabled = old_policy.pop('disabled_transitions')
    new_disabled = new_policy.pop('disabled_transitions')
    old_gaps = {(gap['code'], gap['subject']) for gap in left['gaps']}
    new_gaps = {(gap['code'], gap['subject']) for gap in right['gaps']}
    old_status = {item['id']: item['status'] for item in left['property_results']}
    new_status = {item['id']: item['status'] for item in right['property_results']}
    return {'schema_version': 1, 'model_sha256': left['model_sha256'],
            'baseline_requirements_sha256': left['requirements_sha256'],
            'scenario_requirements_sha256': right['requirements_sha256'],
            'obligations_changed': old_policy != new_policy,
            'newly_excluded_transitions': sorted(set(new_disabled) - set(old_disabled)),
            'restored_transitions': sorted(set(old_disabled) - set(new_disabled)),
            'property_changes': [{'id': key, 'baseline': old_status.get(key), 'scenario': new_status.get(key)}
                                 for key in sorted(set(old_status) | set(new_status))
                                 if old_status.get(key) != new_status.get(key)],
            'new_gaps': [{'code': code, 'subject': subject} for code, subject in sorted(new_gaps - old_gaps)],
            'resolved_gaps': [{'code': code, 'subject': subject} for code, subject in sorted(old_gaps - new_gaps)],
            'baseline_status': left['status'], 'scenario_status': right['status'],
            'execution_authorized': False,
            'limitation': 'Changing exclusions changes the assumed behavior space; passing a restricted scenario does not prove the full model'}
