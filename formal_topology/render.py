"""Script-free offline HTML review of states, certificates and counterexamples."""
from html import escape
import json
from .model import parse_model


def render_html(data, report):
    model = parse_model(data)
    rows = []
    for identifier, labels in sorted(model.states.items()):
        reachable = identifier in report['reachable_states']
        rows.append('<tr><td>' + escape(identifier) + '</td><td>' + escape(', '.join(sorted(labels)) or 'none')
                    + '</td><td>' + ('reachable' if reachable else 'unreachable') + '</td><td>'
                    + ('yes' if identifier in report['reachable_deadlocks'] else 'no') + '</td></tr>')
    properties = []
    for result in report['property_results']:
        properties.append('<h3>' + escape(result['id']) + ' — ' + result['status'] + '</h3><p>'
                          + escape(result['kind']) + '</p><pre>'
                          + escape(json.dumps(result['evidence'], sort_keys=True, indent=2)) + '</pre>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>Computation topology review</title><style>'
            'body{font:16px system-ui,sans-serif;max-width:1050px;margin:32px auto;padding:0 20px;color:#172033}'
            'h1{font-size:30px}table{width:100%;border-collapse:collapse;table-layout:fixed}'
            'th,td{border:1px solid #cbd5e1;padding:10px;text-align:left;overflow-wrap:anywhere}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f9;padding:16px}'
            '</style></head><body><h1>Computation and formal verification topology</h1>'
            '<p>Finite-state model analysis with separately checked local certificates. No program execution.</p>'
            '<h2>' + report['status'] + '</h2><p>' + str(report['summary']['gap_count'])
            + ' obligation gaps. All nondeterministic paths; no fairness assumptions.</p>'
            '<h2>State topology</h2><table><thead><tr><th>State</th><th>Labels</th><th>Reachability</th><th>Deadlock</th>'
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'
            '<h2>Proofs and counterexamples</h2>' + ''.join(properties)
            + '<h2>Complete report and assumptions</h2><pre>'
            + escape(json.dumps(report, sort_keys=True, indent=2)) + '</pre></body></html>\n')
