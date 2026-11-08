"""Finite-state topology analysis with sound bounded-domain certificates."""
from collections import deque
import hashlib
import json
from .model import evaluate, outgoing, parse_model, parse_requirements

ENGINE_VERSION = '0.1.0'


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def traversal(graph, initial):
    parents, queue = {initial: None}, deque([initial])
    while queue:
        source = queue.popleft()
        for edge in graph[source]:
            if edge.target not in parents:
                parents[edge.target] = (source, edge.id)
                queue.append(edge.target)
    return parents


def path_to(parents, target):
    states, transitions = [target], []
    while parents[states[-1]] is not None:
        source, edge = parents[states[-1]]
        states.append(source)
        transitions.append(edge)
    return {'states': list(reversed(states)), 'transitions': list(reversed(transitions))}


def strongly_connected(graph, reachable):
    """Transparent bounded mutual reachability, rather than an external graph solver."""
    reach = {state: set(traversal(graph, state)) for state in reachable}
    remaining, groups = set(reachable), []
    while remaining:
        state = min(remaining)
        group = {other for other in remaining if other in reach[state] and state in reach[other]}
        groups.append(sorted(group))
        remaining -= group
    return groups


def inevitability(graph, model, predicate, reachable):
    ranks = {state: 0 for state in reachable if evaluate(predicate, model.states[state])}
    changed = True
    while changed:
        changed = False
        for state in sorted(reachable):
            if state not in ranks and graph[state] and all(edge.target in ranks for edge in graph[state]):
                ranks[state] = 1 + max(ranks[edge.target] for edge in graph[state])
                changed = True
    if model.initial in ranks:
        return 'PASS', {'ranks': dict(sorted(ranks.items()))}
    # A state outside the least fixed point has a nonwinning successor or is deadlocked.
    states, transitions, index = [model.initial], [], {model.initial: 0}
    while True:
        state = states[-1]
        candidate = next((edge for edge in graph[state] if edge.target not in ranks), None)
        target, edge_id = (candidate.target, candidate.id) if candidate else (state, None)
        transitions.append(edge_id)
        states.append(target)
        if target in index:
            start = index[target]
            return 'FAIL', {'prefix': {'states': states[:start + 1], 'transitions': transitions[:start]},
                            'cycle': {'states': states[start:], 'transitions': transitions[start:]}}
        index[target] = len(states) - 1


def property_result(prop, graph, model, parents):
    reachable, kind = sorted(parents), prop['kind']
    predicate = prop.get('predicate')
    if kind == 'inevitable':
        status, evidence = inevitability(graph, model, predicate, reachable)
    elif kind == 'reachable':
        target = next((state for state in reachable if evaluate(predicate, model.states[state])), None)
        status = 'PASS' if target is not None else 'FAIL'
        evidence = {'path': path_to(parents, target)} if target is not None else {'closed_set': reachable}
    else:
        if kind == 'deadlock_free':
            bad = next((state for state in reachable if not graph[state]), None)
        else:
            bad = next((state for state in reachable if not evaluate(predicate, model.states[state])), None)
        status = 'FAIL' if bad is not None else 'PASS'
        evidence = {'path': path_to(parents, bad)} if bad is not None else {'closed_set': reachable}
    return {'id': prop['id'], 'kind': kind, 'status': status, 'evidence': evidence}


def build_report(data, requirements):
    model = parse_model(data)
    policy = parse_requirements(requirements, model)
    graph = outgoing(model, policy)
    parents = traversal(graph, model.initial)
    reachable = sorted(parents)
    groups = strongly_connected(graph, reachable)
    results = [property_result(prop, graph, model, parents) for prop in policy['properties']]
    gaps = []
    for state in policy['required_states']:
        if state not in model.states:
            gaps.append({'code': 'MISSING_REQUIRED_STATE', 'subject': state})
        elif state not in parents:
            gaps.append({'code': 'UNREACHABLE_REQUIRED_STATE', 'subject': state})
    gaps.extend({'code': 'PROPERTY_VIOLATED', 'subject': item['id']} for item in results if item['status'] == 'FAIL')
    present = sum(state in model.states for state in policy['required_states'])
    required_reachable = sum(state in parents for state in policy['required_states'])
    return {'schema_version': 1, 'engine_version': ENGINE_VERSION,
            'model_sha256': fingerprint(data), 'requirements_sha256': fingerprint(requirements),
            'status': 'GAPS_FOUND' if gaps else 'OBLIGATIONS_HOLD', 'requirements': policy,
            'summary': {'states': len(model.states), 'transitions': len(model.transitions),
                        'reachable_states': len(parents), 'active_transitions': sum(map(len, graph.values())),
                        'properties': len(results), 'failed_properties': sum(item['status'] == 'FAIL' for item in results),
                        'gap_count': len(gaps)},
            'required_state_presence': present / len(policy['required_states']) if policy['required_states'] else None,
            'required_state_reachability': required_reachable / len(policy['required_states']) if policy['required_states'] else None,
            'reachable_states': reachable, 'unreachable_states': sorted(set(model.states) - set(parents)),
            'reachable_deadlocks': sorted(state for state in reachable if not graph[state]),
            'reachable_sccs': groups,
            'cyclic_sccs': [group for group in groups if len(group) > 1 or any(edge.target == group[0] for edge in graph[group[0]])],
            'property_results': results, 'gaps': gaps, 'execution_authorized': False,
            'semantics': {'state_space': 'explicit finite enumeration', 'path_domain': 'all nondeterministic executions',
                          'fairness': 'none', 'deadlocks': 'implicit infinite stuttering for inevitable properties'},
            'limitations': ['Checks the supplied model, not arbitrary source code or physical systems',
                            'State labels, completeness and excluded transitions are supplied assumptions',
                            'Certificates are checked by a separate local implementation, not an independent organization',
                            'No unbounded theorem proving, compiler validation, SMT solving or code execution']}
