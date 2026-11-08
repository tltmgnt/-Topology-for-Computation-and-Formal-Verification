"""Exercise the installed distribution outside the checkout with isolated imports."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def run(arguments, directory, expected=0):
    result = subprocess.run([sys.executable, '-I', '-m', 'formal_topology', *arguments],
                            cwd=directory, capture_output=True, text=True, check=False)
    if result.returncode != expected:
        raise AssertionError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        cases = [('baseline', 'model.json', 'requirements.json', 0),
                 ('unsafe', 'unsafe.json', 'requirements.json', 1),
                 ('livelock', 'livelock.json', 'requirements.json', 1),
                 ('outage', 'model.json', 'outage.json', 1),
                 ('missing', 'model.json', 'gaps.json', 1)]
        for label, model, requirements, expected in cases:
            path = Path(directory) / label
            run(['analyze', str(root / 'examples' / model), '--requirements',
                 str(root / 'examples' / requirements), '--output', str(path)], directory, expected)
            verification = run(['verify', str(path)], directory)
            if not verification['bundle_consistent']:
                raise AssertionError('bundle did not verify')
            proofs = run(['certificates', str(path / 'model.json'), '--requirements',
                          str(path / 'requirements.json'), '--report', str(path / 'report.json')], directory)
            if not proofs['certificates_valid']:
                raise AssertionError('proofs did not check')
        comparison = run(['compare', str(Path(directory) / 'baseline'), str(Path(directory) / 'outage')], directory)
        if comparison['obligations_changed'] or not comparison['property_changes']:
            raise AssertionError('outage comparison mismatch')
    print('Installed baseline, unsafe, livelock, outage, missingness, certificates and comparison passed')


if __name__ == '__main__':
    main()
