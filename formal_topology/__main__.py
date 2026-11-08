"""CLI for finite-state analysis, certificate checking and full bundle replay."""
import argparse
import json
import sys
from .analysis import fingerprint
from .certificates import check_certificates
from .io import compare_bundles, create_bundle, read_json, verify_bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    analyze = commands.add_parser('analyze', help='Check obligations and create a new review bundle')
    analyze.add_argument('model')
    analyze.add_argument('--requirements', required=True)
    analyze.add_argument('--output', required=True)
    verify = commands.add_parser('verify', help='Check proofs and recompute every captured bundle file')
    verify.add_argument('bundle')
    proofs = commands.add_parser('certificates', help='Check report proofs without running the analyzer')
    proofs.add_argument('model')
    proofs.add_argument('--requirements', required=True)
    proofs.add_argument('--report', required=True)
    compare = commands.add_parser('compare', help='Compare verified scenarios of one captured model')
    compare.add_argument('baseline')
    compare.add_argument('scenario')
    args = parser.parse_args(argv)
    try:
        if args.command == 'analyze':
            report = create_bundle(args.output, read_json(args.model), read_json(args.requirements))
            result = {'bundle_created': True, 'status': report['status'], 'summary': report['summary']}
            code = 1 if report['gaps'] else 0
        elif args.command == 'compare':
            result = compare_bundles(args.baseline, args.scenario)
            code = 0
        elif args.command == 'verify':
            report = verify_bundle(args.bundle)
            result = {'bundle_consistent': True, 'status': report['status'], 'summary': report['summary'],
                      'execution_authorized': False}
            code = 0
        else:
            data, requirements, report = read_json(args.model), read_json(args.requirements), read_json(args.report)
            if (not isinstance(report, dict) or report.get('model_sha256') != fingerprint(data)
                    or report.get('requirements_sha256') != fingerprint(requirements)):
                raise ValueError('report is not bound to these inputs')
            result = check_certificates(data, requirements, report.get('property_results'))
            result['scope'] = 'property verdict certificates only; report summary and missing-state gaps not checked'
            code = 0
    except (ValueError, OSError) as error:
        print(json.dumps({'error': str(error), 'execution_authorized': False}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
