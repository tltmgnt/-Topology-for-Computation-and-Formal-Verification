"""Semantic, certificate, integrity and installed-workflow acceptance tests."""
import ast
import contextlib
import copy
import hashlib
import io
import itertools
from pathlib import Path
import tempfile
import unittest
from formal_topology import build_report, check_certificates, compare_bundles, create_bundle, parse_model, parse_requirements, verify_bundle
from formal_topology.analysis import canonical
from formal_topology.io import MAX_BYTES, decode, read_json
from formal_topology.__main__ import main

ROOT = Path(__file__).resolve().parents[1]


def sample():
    return read_json(ROOT / 'examples/model.json'), read_json(ROOT / 'examples/requirements.json')


def indexed(report):
    return {item['id']: item for item in report['property_results']}


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.model, self.policy = sample()

    def test_reference_model_topology_and_certificates(self):
        report = build_report(self.model, self.policy)
        self.assertEqual(report['status'], 'OBLIGATIONS_HOLD')
        self.assertEqual(report['reachable_states'], ['done', 'idle', 'reviewed'])
        self.assertEqual(report['unreachable_states'], ['orphan'])
        self.assertEqual(report['cyclic_sccs'], [['done']])
        self.assertEqual(report['reachable_deadlocks'], [])
        self.assertTrue(check_certificates(self.model, self.policy, report['property_results'])['certificates_valid'])
        self.assertFalse(report['execution_authorized'])

    def test_unsafe_branch_has_replayable_counterexamples(self):
        model = read_json(ROOT / 'examples/unsafe.json')
        report = build_report(model, self.policy)
        results = indexed(report)
        self.assertEqual(results['safe']['status'], 'FAIL')
        self.assertEqual(results['safe']['evidence']['path']['states'], ['idle', 'orphan'])
        self.assertEqual(results['completion-possible']['status'], 'PASS')
        self.assertEqual(results['completion-inevitable']['status'], 'FAIL')
        self.assertEqual(results['no-deadlock']['status'], 'FAIL')
        cycle = results['completion-inevitable']['evidence']['cycle']
        self.assertEqual(cycle, {'states': ['orphan', 'orphan'], 'transitions': [None]})
        self.assertTrue(check_certificates(model, self.policy, report['property_results'])['certificates_valid'])

    def test_livelock_differs_from_deadlock(self):
        model = read_json(ROOT / 'examples/livelock.json')
        report = build_report(model, self.policy)
        self.assertEqual(report['reachable_deadlocks'], [])
        self.assertEqual(indexed(report)['no-deadlock']['status'], 'PASS')
        failure = indexed(report)['completion-inevitable']
        self.assertEqual(failure['status'], 'FAIL')
        self.assertTrue(all(edge is not None for edge in failure['evidence']['cycle']['transitions']))
        check_certificates(model, self.policy, report['property_results'])

    def test_outage_is_an_explicit_assumption(self):
        policy = read_json(ROOT / 'examples/outage.json')
        report = build_report(self.model, policy)
        self.assertEqual(report['requirements']['disabled_transitions'], ['finish'])
        self.assertEqual(report['reachable_deadlocks'], ['reviewed'])
        self.assertIn({'code': 'UNREACHABLE_REQUIRED_STATE', 'subject': 'done'}, report['gaps'])
        check_certificates(self.model, policy, report['property_results'])

    def test_missing_is_distinct_from_unreachable(self):
        report = build_report(self.model, read_json(ROOT / 'examples/gaps.json'))
        self.assertEqual(report['gaps'], [{'code': 'MISSING_REQUIRED_STATE', 'subject': 'missing'},
                                         {'code': 'UNREACHABLE_REQUIRED_STATE', 'subject': 'orphan'}])
        self.assertAlmostEqual(report['required_state_presence'], 2 / 3)
        self.assertAlmostEqual(report['required_state_reachability'], 1 / 3)
        self.assertTrue(all(item['status'] == 'PASS' for item in report['property_results']))

    def test_initial_target_makes_eventuality_true_even_if_later_lost(self):
        self.model['states'][0]['labels'].append('done')
        self.model['transitions'].append({'id': 'bad', 'source': 'idle', 'target': 'orphan'})
        result = build_report(self.model, self.policy)
        self.assertEqual(indexed(result)['completion-inevitable']['status'], 'PASS')
        check_certificates(self.model, self.policy, result['property_results'])

    def test_deadlock_target_satisfies_eventuality_not_deadlock_freedom(self):
        self.model['transitions'] = [item for item in self.model['transitions'] if item['id'] != 'hold']
        result = build_report(self.model, self.policy)
        self.assertEqual(indexed(result)['completion-inevitable']['status'], 'PASS')
        self.assertEqual(indexed(result)['no-deadlock']['status'], 'FAIL')
        check_certificates(self.model, self.policy, result['property_results'])

    def test_boolean_predicate_composition(self):
        self.policy['properties'] = [{'id': 'logic', 'kind': 'invariant', 'predicate': {'all': [
            {'atom': 'safe'}, {'any': [{'not': {'atom': 'done'}}, {'atom': 'approved'}]}]}}]
        report = build_report(self.model, self.policy)
        self.assertEqual(report['status'], 'OBLIGATIONS_HOLD')
        check_certificates(self.model, self.policy, report['property_results'])

    def test_all_three_state_graphs_against_bounded_trace_oracle(self):
        # 512 directed graphs x 8 target labelings. The oracle enumerates bounded
        # paths, rather than using the analyzer's reachability or fixed-point code.
        states = ['a', 'b', 'c']
        possible = list(itertools.product(states, repeat=2))
        for graph_mask in range(1 << len(possible)):
            transitions = [{'id': str(i), 'source': a, 'target': b}
                           for i, (a, b) in enumerate(possible) if graph_mask & (1 << i)]
            successors = {s: [e['target'] for e in transitions if e['source'] == s] for s in states}
            for labels_mask in range(8):
                target = {s for i, s in enumerate(states) if labels_mask & (1 << i)}
                model = {'schema_version': 1, 'initial': 'a', 'propositions': ['p'],
                         'states': [{'id': s, 'labels': ['p'] if s in target else []} for s in states],
                         'transitions': transitions}
                policy = {'schema_version': 1, 'required_states': [], 'disabled_transitions': [],
                          'properties': [{'id': kind, 'kind': kind, 'predicate': {'atom': 'p'}}
                                         for kind in ('invariant', 'reachable', 'inevitable')]
                          + [{'id': 'deadlock_free', 'kind': 'deadlock_free'}]}
                frontier, reached = {'a'}, {'a'}
                avoiding = {'a'} - target
                for _ in range(len(states)):
                    frontier = {t for s in frontier for t in successors[s]}
                    reached |= frontier
                    avoiding = {t for s in avoiding for t in (successors[s] or [s]) if t not in target}
                expected = {'invariant': reached <= target, 'reachable': bool(reached & target),
                            'inevitable': not avoiding, 'deadlock_free': all(successors[s] for s in reached)}
                report = build_report(model, policy)
                actual = {r['id']: r['status'] == 'PASS' for r in report['property_results']}
                self.assertEqual(actual, expected, (graph_mask, labels_mask))
                check_certificates(model, policy, report['property_results'])


class CertificateTests(unittest.TestCase):
    def setUp(self):
        self.model, self.policy = sample()
        self.report = build_report(self.model, self.policy)

    def test_forged_ranking_rejected(self):
        result = indexed(self.report)['completion-inevitable']
        result['evidence']['ranks']['idle'] = 0
        with self.assertRaises(ValueError):
            check_certificates(self.model, self.policy, self.report['property_results'])

    def test_boolean_rank_is_not_an_integer_certificate(self):
        indexed(self.report)['completion-inevitable']['evidence']['ranks']['idle'] = True
        with self.assertRaises(ValueError):
            check_certificates(self.model, self.policy, self.report['property_results'])

    def test_nonclosed_invariant_certificate_rejected(self):
        indexed(self.report)['safe']['evidence']['closed_set'] = ['idle']
        with self.assertRaises(ValueError):
            check_certificates(self.model, self.policy, self.report['property_results'])

    def test_forged_path_transition_rejected(self):
        indexed(self.report)['completion-possible']['evidence']['path']['transitions'][0] = 'invented'
        with self.assertRaises(ValueError):
            check_certificates(self.model, self.policy, self.report['property_results'])

    def test_excluded_transition_cannot_be_witness(self):
        policy = {**self.policy, 'disabled_transitions': ['finish']}
        with self.assertRaises(ValueError):
            check_certificates(self.model, policy, self.report['property_results'])

    def test_false_failure_certificate_rejected(self):
        result = indexed(self.report)['safe']
        result['status'] = 'FAIL'
        result['evidence'] = {'path': {'states': ['idle'], 'transitions': []}}
        with self.assertRaises(ValueError):
            check_certificates(self.model, self.policy, self.report['property_results'])

    def test_stutter_not_allowed_at_a_state_with_successors(self):
        result = indexed(self.report)['completion-inevitable']
        result.update(status='FAIL', evidence={'prefix': {'states': ['idle'], 'transitions': []},
                                              'cycle': {'states': ['idle', 'idle'], 'transitions': [None]}})
        with self.assertRaises(ValueError):
            check_certificates(self.model, self.policy, self.report['property_results'])

    def test_lasso_reaching_target_is_not_a_counterexample(self):
        result = indexed(self.report)['completion-inevitable']
        result.update(status='FAIL', evidence={'prefix': {'states': ['idle', 'reviewed', 'done'],
                                                         'transitions': ['review', 'finish']},
                                              'cycle': {'states': ['done', 'done'], 'transitions': ['hold']}})
        with self.assertRaises(ValueError):
            check_certificates(self.model, self.policy, self.report['property_results'])

    def test_wrong_inventory_and_malformed_status_rejected(self):
        for results in (self.report['property_results'][:-1], [self.report['property_results'][0]] * 4):
            with self.assertRaises(ValueError):
                check_certificates(self.model, self.policy, results)
        self.report['property_results'][0]['status'] = []
        with self.assertRaises(ValueError):
            check_certificates(self.model, self.policy, self.report['property_results'])


class InputTests(unittest.TestCase):
    def setUp(self):
        self.model, self.policy = sample()

    def test_exact_model_fields_and_bindings(self):
        cases = [{**self.model, 'schema_version': True}, {**self.model, 'unknown': 1},
                 {**self.model, 'initial': 'missing'}, {**self.model, 'states': []}]
        duplicate = copy.deepcopy(self.model)
        duplicate['states'].append(duplicate['states'][0])
        cases.append(duplicate)
        dangling = copy.deepcopy(self.model)
        dangling['transitions'][0]['target'] = 'missing'
        cases.append(dangling)
        labels = copy.deepcopy(self.model)
        labels['states'][0]['labels'] = ['unknown']
        cases.append(labels)
        for value in cases:
            with self.assertRaises(ValueError):
                parse_model(value)

    def test_invalid_requirements_and_predicates(self):
        model = parse_model(self.model)
        for change in ({'disabled_transitions': ['missing']}, {'required_states': [], 'properties': []},
                       {'schema_version': 2}, {'required_states': ['idle', 'idle']}):
            with self.assertRaises(ValueError):
                parse_requirements({**self.policy, **change}, model)
        for predicate in ({'atom': 'unknown'}, {'all': []}, {'code': 'eval()'}, {'not': 'bad'},
                          {'atom': 'safe', 'not': {'atom': 'done'}}):
            policy = {**self.policy, 'properties': [{'id': 'bad', 'kind': 'invariant', 'predicate': predicate}]}
            with self.assertRaises(ValueError):
                parse_requirements(policy, model)

    def test_json_duplicates_nonfinite_and_depth_rejected(self):
        for value in (b'{"x":1,"x":1}', b'{"x":NaN}', b'{"x":1e999}', b'\xff',
                      ('[' * 70 + '0' + ']' * 70).encode()):
            with self.assertRaises(ValueError):
                decode(value)

    def test_state_and_work_limits(self):
        data = {**self.model, 'states': [{'id': str(i), 'labels': []} for i in range(257)]}
        with self.assertRaises(ValueError):
            parse_model(data)
        states = [{'id': str(i), 'labels': []} for i in range(256)]
        data = {'schema_version': 1, 'initial': '0', 'propositions': ['p'], 'states': states,
                'transitions': [{'id': str(i), 'source': str(i % 256), 'target': str((i + 1) % 256)} for i in range(2048)]}
        policy = {'schema_version': 1, 'required_states': [], 'disabled_transitions': [],
                  'properties': [{'id': str(i), 'kind': 'invariant', 'predicate': {'atom': 'p'}} for i in range(32)]}
        with self.assertRaises(ValueError):
            build_report(data, policy)

    def test_supported_python_syntax(self):
        for path in (ROOT / 'formal_topology').glob('*.py'):
            ast.parse(path.read_text(), filename=str(path), feature_version=(3, 10))


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.model, self.policy = sample()
        self.temp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'run'

    def test_create_verify_and_preserve_existing(self):
        report = create_bundle(self.path, self.model, self.policy)
        self.assertEqual(report, verify_bundle(self.path))
        with self.assertRaises(FileExistsError):
            create_bundle(self.path, self.model, self.policy)
        self.assertEqual(report, verify_bundle(self.path))

    def test_each_file_edit_is_rejected(self):
        create_bundle(self.path, self.model, self.policy)
        for path in self.path.iterdir():
            original = path.read_bytes()
            path.write_bytes(original + b' ')
            with self.assertRaises(ValueError):
                verify_bundle(self.path)
            path.write_bytes(original)

    def test_forged_report_with_rewritten_hash_fails(self):
        create_bundle(self.path, self.model, self.policy)
        report = read_json(self.path / 'report.json')
        report['status'] = 'FAKE'
        content = canonical(report)
        (self.path / 'report.json').write_bytes(content)
        manifest = read_json(self.path / 'manifest.json')
        manifest['files']['report.json'] = {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
        (self.path / 'manifest.json').write_bytes(canonical(manifest))
        with self.assertRaises(ValueError):
            verify_bundle(self.path)

    def test_extra_file_and_symlink_rejected(self):
        create_bundle(self.path, self.model, self.policy)
        extra = self.path / 'extra'
        extra.write_text('x')
        with self.assertRaises(ValueError):
            verify_bundle(self.path)
        extra.unlink()
        source = self.path / 'report.json'
        target = Path(self.temp.name) / 'external'
        target.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            verify_bundle(self.path)

    def test_failed_obligations_can_have_valid_certificates(self):
        report = create_bundle(self.path, read_json(ROOT / 'examples/unsafe.json'), self.policy)
        self.assertEqual(report['status'], 'GAPS_FOUND')
        self.assertEqual(verify_bundle(self.path)['status'], 'GAPS_FOUND')

    def test_html_escapes_model_ids(self):
        self.model['states'].append({'id': '<script>alert(1)</script>', 'labels': []})
        create_bundle(self.path, self.model, self.policy)
        html = (self.path / 'review.html').read_text()
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_cli_analysis_replay_and_certificate_scope(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['analyze', str(ROOT / 'examples/model.json'), '--requirements',
                                   str(ROOT / 'examples/requirements.json'), '--output', str(self.path)]), 0)
            self.assertEqual(main(['verify', str(self.path)]), 0)
            self.assertEqual(main(['certificates', str(self.path / 'model.json'), '--requirements',
                                   str(self.path / 'requirements.json'), '--report', str(self.path / 'report.json')]), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['verify', str(Path(self.temp.name) / 'absent')]), 2)

    def test_cli_gap_exit_and_bound_report_inputs(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['analyze', str(ROOT / 'examples/unsafe.json'), '--requirements',
                                   str(ROOT / 'examples/requirements.json'), '--output', str(self.path)]), 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['certificates', str(ROOT / 'examples/model.json'), '--requirements',
                                   str(self.path / 'requirements.json'), '--report', str(self.path / 'report.json')]), 2)

    def test_verified_scenario_comparison_preserves_assumptions(self):
        create_bundle(self.path, self.model, self.policy)
        other = Path(self.temp.name) / 'outage'
        create_bundle(other, self.model, read_json(ROOT / 'examples/outage.json'))
        result = compare_bundles(self.path, other)
        self.assertFalse(result['obligations_changed'])
        self.assertEqual(result['newly_excluded_transitions'], ['finish'])
        self.assertTrue(result['new_gaps'])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['compare', str(self.path), str(other)]), 0)
        changed = Path(self.temp.name) / 'other-model'
        create_bundle(changed, read_json(ROOT / 'examples/unsafe.json'), self.policy)
        with self.assertRaises(ValueError):
            compare_bundles(self.path, changed)

    def test_oversize_file_is_rejected(self):
        path = Path(self.temp.name) / 'large'
        with path.open('wb') as stream:
            stream.truncate(MAX_BYTES + 1)
        with self.assertRaises(ValueError):
            read_json(path)


if __name__ == '__main__':
    unittest.main()
