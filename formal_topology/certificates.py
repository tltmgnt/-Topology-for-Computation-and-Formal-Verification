"""Small evidence checker independent of analysis traversal and fixed-point routines.

Trusted base: parsing, predicate evaluation, Python runtime, and this checker.
"""
from .model import evaluate, fields, outgoing, parse_model, parse_requirements


def checked_path(value, model, graph, allow_stutter=False):
    fields(value, {'states', 'transitions'})
    states, transitions = value['states'], value['transitions']
    if (not isinstance(states, list) or not 1 <= len(states) <= 2 * len(model.states) + 2
            or not isinstance(transitions, list) or len(transitions) != len(states) - 1
            or any(not isinstance(state, str) or state not in model.states for state in states)):
        raise ValueError('invalid bounded path certificate')
    for source, target, transition in zip(states, states[1:], transitions):
        if transition is None and allow_stutter and source == target and not graph[source]:
            continue
        if not isinstance(transition, str) or not any(edge.id == transition and edge.target == target for edge in graph[source]):
            raise ValueError('path uses nonexistent or excluded transition')
    return states


def checked_closed_set(value, model, graph):
    if (not isinstance(value, list) or not 1 <= len(value) <= len(model.states)
            or any(not isinstance(state, str) or state not in model.states for state in value)
            or len(set(value)) != len(value) or model.initial not in value):
        raise ValueError('invalid closed-set certificate')
    selected = set(value)
    if any(edge.target not in selected for state in selected for edge in graph[state]):
        raise ValueError('certificate set is not transition closed')
    return selected


def check_one(result, prop, model, graph):
    fields(result, {'id', 'kind', 'status', 'evidence'})
    if result['id'] != prop['id'] or result['kind'] != prop['kind'] or not isinstance(result['status'], str) or result['status'] not in {'PASS', 'FAIL'}:
        raise ValueError('certificate property binding mismatch')
    evidence, kind, status = result['evidence'], prop['kind'], result['status']
    predicate = prop.get('predicate')
    if kind == 'inevitable' and status == 'PASS':
        fields(evidence, {'ranks'})
        ranks = evidence['ranks']
        if not isinstance(ranks, dict) or model.initial not in ranks or set(ranks) - set(model.states):
            raise ValueError('invalid ranking domain')
        if any(isinstance(rank, bool) or not isinstance(rank, int) or not 0 <= rank <= len(model.states)
               for rank in ranks.values()):
            raise ValueError('bounded nonnegative integer ranks required')
        for state, rank in ranks.items():
            target = evaluate(predicate, model.states[state])
            if (rank == 0) != target:
                raise ValueError('rank zero must match target predicate')
            if not target and (not graph[state] or any(edge.target not in ranks or ranks[edge.target] >= rank for edge in graph[state])):
                raise ValueError('rank must decrease on every outgoing transition')
    elif kind == 'inevitable':
        fields(evidence, {'prefix', 'cycle'})
        prefix = checked_path(evidence['prefix'], model, graph)
        cycle = checked_path(evidence['cycle'], model, graph, allow_stutter=True)
        if prefix[0] != model.initial or prefix[-1] != cycle[0] or len(cycle) < 2 or cycle[0] != cycle[-1]:
            raise ValueError('lasso must begin at initial state and close its cycle')
        if any(evaluate(predicate, model.states[state]) for state in prefix + cycle):
            raise ValueError('inevitability counterexample reaches target')
    elif (kind == 'reachable' and status == 'PASS') or (kind != 'reachable' and status == 'FAIL'):
        fields(evidence, {'path'})
        states = checked_path(evidence['path'], model, graph)
        if states[0] != model.initial:
            raise ValueError('witness must begin at initial state')
        if kind == 'reachable':
            valid = evaluate(predicate, model.states[states[-1]])
        elif kind == 'invariant':
            valid = not evaluate(predicate, model.states[states[-1]])
        else:
            valid = not graph[states[-1]]
        if not valid:
            raise ValueError('witness endpoint does not establish verdict')
    else:
        fields(evidence, {'closed_set'})
        states = checked_closed_set(evidence['closed_set'], model, graph)
        if kind == 'reachable':
            valid = all(not evaluate(predicate, model.states[state]) for state in states)
        elif kind == 'invariant':
            valid = all(evaluate(predicate, model.states[state]) for state in states)
        else:
            valid = all(graph[state] for state in states)
        if not valid:
            raise ValueError('closed set does not establish verdict')


def check_certificates(data, requirements, results):
    """Validate every PASS/FAIL proof without rerunning the analyzer."""
    model = parse_model(data)
    policy = parse_requirements(requirements, model)
    graph = outgoing(model, policy)
    if not isinstance(results, list) or len(results) != len(policy['properties']):
        raise ValueError('one certificate per property required')
    indexed = {}
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get('id'), str) or result['id'] in indexed:
            raise ValueError('duplicate or malformed property certificate')
        indexed[result['id']] = result
    if set(indexed) != {prop['id'] for prop in policy['properties']}:
        raise ValueError('certificate inventory mismatch')
    for prop in policy['properties']:
        check_one(indexed[prop['id']], prop, model, graph)
    return {'certificates_valid': True, 'checked_properties': len(results),
            'failed_properties': sum(result['status'] == 'FAIL' for result in results),
            'execution_authorized': False}
