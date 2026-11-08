"""Scoped synthetic domain adapter; no external execution."""
from formal_topology import build_report
DATA={'schema_version': 1, 'initial': 'idle', 'propositions': ['safe', 'done', 'approved'], 'states': [{'id': 'idle', 'labels': ['safe']}, {'id': 'reviewed', 'labels': ['safe', 'approved']}, {'id': 'done', 'labels': ['safe', 'approved', 'done']}, {'id': 'orphan', 'labels': []}], 'transitions': [{'id': 'review', 'source': 'idle', 'target': 'reviewed'}, {'id': 'finish', 'source': 'reviewed', 'target': 'done'}, {'id': 'hold', 'source': 'done', 'target': 'done'}]}
REQUIREMENTS={'schema_version': 1, 'required_states': ['idle', 'reviewed', 'done'], 'disabled_transitions': [], 'properties': [{'id': 'safe', 'kind': 'invariant', 'predicate': {'atom': 'safe'}}, {'id': 'completion-possible', 'kind': 'reachable', 'predicate': {'atom': 'done'}}, {'id': 'completion-inevitable', 'kind': 'inevitable', 'predicate': {'atom': 'done'}}, {'id': 'no-deadlock', 'kind': 'deadlock_free'}]}

def check():
    report=build_report(DATA,REQUIREMENTS)
    passed=report['status']=='OBLIGATIONS_HOLD' and not report['gaps']
    from formal_topology import check_certificates
    certificate=check_certificates(DATA,REQUIREMENTS,report['property_results'])
    passed=passed and certificate['certificates_valid']
    return {'domain':'formal','statement':'The bundled fictional domain fixture satisfies its explicitly supplied software obligations.',
            'passed':passed,'configuration':{'input':DATA,'requirements':REQUIREMENTS},
            'observed':{'status':report['status'],'summary':report['summary']},
            'scope':'Declared offline model checks only; no clinical validity, geographic completeness, real-program correctness or action authority'}
