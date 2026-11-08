"""Exact contracts for bounded, explicitly enumerated finite-state models."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

MAX_STATES = 256
MAX_TRANSITIONS = 2048
MAX_PROPERTIES = 32
MAX_WORK = 5000000


def fields(value, required):
    if not isinstance(value, dict) or set(value) != set(required):
        raise ValueError('exact contract fields required')


def name(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > 160:
        raise ValueError('trimmed identifier of 1 to 160 characters required')
    return value


def version(value):
    if isinstance(value, bool) or not isinstance(value, int) or value != 1:
        raise ValueError('schema version 1 required')


def names(values, maximum):
    if not isinstance(values, list) or len(values) > maximum:
        raise ValueError('bounded identifier array required')
    result = [name(value) for value in values]
    if len(set(result)) != len(result):
        raise ValueError('duplicate identifier')
    return sorted(result)


@dataclass(frozen=True)
class Transition:
    id: str
    source: str
    target: str


@dataclass(frozen=True)
class Model:
    initial: str
    propositions: frozenset
    states: Mapping[str, frozenset]
    transitions: Mapping[str, Transition]


def parse_model(data):
    fields(data, {'schema_version', 'initial', 'propositions', 'states', 'transitions'})
    version(data['schema_version'])
    propositions = frozenset(names(data['propositions'], 64))
    states, transitions = {}, {}
    if not isinstance(data['states'], list) or not 1 <= len(data['states']) <= MAX_STATES:
        raise ValueError('between 1 and 256 states required')
    for state in data['states']:
        fields(state, {'id', 'labels'})
        identifier = name(state['id'])
        labels = frozenset(names(state['labels'], 64))
        if identifier in states or not labels <= propositions:
            raise ValueError('duplicate state or undeclared proposition')
        states[identifier] = labels
    initial = name(data['initial'])
    if initial not in states:
        raise ValueError('initial state must exist')
    if not isinstance(data['transitions'], list) or len(data['transitions']) > MAX_TRANSITIONS:
        raise ValueError('transition limit exceeded')
    for transition in data['transitions']:
        fields(transition, {'id', 'source', 'target'})
        item = Transition(*(name(transition[key]) for key in ('id', 'source', 'target')))
        if item.id in transitions or item.source not in states or item.target not in states:
            raise ValueError('duplicate transition or dangling endpoint')
        transitions[item.id] = item
    return Model(initial, propositions, MappingProxyType(states), MappingProxyType(transitions))


def validate_predicate(value, propositions):
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if count > 128 or depth > 16 or not isinstance(item, dict) or len(item) != 1:
            raise ValueError('bounded Boolean predicate required')
        operator, operand = next(iter(item.items()))
        if operator == 'atom':
            if name(operand) not in propositions:
                raise ValueError('predicate references undeclared proposition')
        elif operator == 'not':
            pending.append((operand, depth + 1))
        elif operator in {'all', 'any'}:
            if not isinstance(operand, list) or not 1 <= len(operand) <= 16:
                raise ValueError('nonempty bounded predicate operands required')
            pending.extend((child, depth + 1) for child in operand)
        else:
            raise ValueError('unsupported predicate operator')


def evaluate(predicate, labels):
    """Evaluate validated Boolean data only; no code or expressions are executed."""
    operator, operand = next(iter(predicate.items()))
    if operator == 'atom':
        return operand in labels
    if operator == 'not':
        return not evaluate(operand, labels)
    if operator == 'all':
        return all(evaluate(child, labels) for child in operand)
    return any(evaluate(child, labels) for child in operand)


def parse_requirements(data, model):
    fields(data, {'schema_version', 'required_states', 'properties', 'disabled_transitions'})
    version(data['schema_version'])
    required = names(data['required_states'], MAX_STATES)
    disabled = names(data['disabled_transitions'], MAX_TRANSITIONS)
    if set(disabled) - set(model.transitions):
        raise ValueError('unknown disabled transition')
    if not isinstance(data['properties'], list) or len(data['properties']) > MAX_PROPERTIES:
        raise ValueError('property limit exceeded')
    properties, seen = [], set()
    for prop in data['properties']:
        if not isinstance(prop, dict):
            raise ValueError('property object required')
        kind = prop.get('kind')
        if not isinstance(kind, str):
            raise ValueError('property kind must be a string')
        fields(prop, {'id', 'kind'} if kind == 'deadlock_free' else {'id', 'kind', 'predicate'})
        identifier = name(prop['id'])
        if identifier in seen or kind not in {'invariant', 'reachable', 'inevitable', 'deadlock_free'}:
            raise ValueError('duplicate property or unsupported property kind')
        seen.add(identifier)
        if kind != 'deadlock_free':
            validate_predicate(prop['predicate'], model.propositions)
        properties.append(dict(prop))
    if not required and not properties:
        raise ValueError('at least one explicit obligation required')
    work = len(model.states) * (len(model.states) + len(model.transitions)) * (len(properties) + 1)
    if work > MAX_WORK:
        raise ValueError('analysis work budget exceeded')
    return {'schema_version': 1, 'required_states': required, 'disabled_transitions': disabled,
            'properties': sorted(properties, key=lambda item: item['id'])}


def outgoing(model, policy):
    graph = {state: [] for state in sorted(model.states)}
    for item in sorted(model.transitions.values(), key=lambda edge: edge.id):
        if item.id not in policy['disabled_transitions']:
            graph[item.source].append(item)
    return graph
