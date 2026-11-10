# Topology compatibility and curriculum v2 — -Topology-for-Computation-and-Formal-Verification

Version 2 adapts the explicit-molecular-graph teaching pattern to this repository's actual role. This is documentation and a learning/decision framework; it introduces no mathematical engine, runtime dependency or operational permission.

## Repository decision

| Question | Repository-specific answer |
| --- | --- |
| Architectural role | specialized verification tool |
| Minimum useful mathematics | Directed finite-state graphs and temporal property checking |
| Relationships to preserve | Initial state, nondeterministic transitions, predicates and counterexample paths |
| Concrete operation / capstone | Build a target-avoiding cycle: show reachable can pass while inevitable fails; inspect the separate certificate checker |
| Necessity and scope boundary | No fairness is added implicitly; certificates concern the supplied finite model, not arbitrary real programs |

The decision is a source-based recommendation, not measured proof that a new specialty improves this repository. Start with the existing implementation and compare any proposed abstraction against a simpler alternative.

## Six-criterion compatibility scorecard

Complete one scorecard per proposed candidate and per concrete operation. Leave unmeasured entries unknown. Scores are human judgments from 0 (no fit) to 5 (strong evidenced fit); unknown is not zero. Do not sum an incomplete card. A total out of 30 is a heuristic, not adoption approval, and feasibility or necessity can veto a high total.

| Criterion | Score | Required evidence |
| --- | --- | --- |
| Structural compatibility | Not yet scored | Map the repository objects and the relationships above without losing direction, labels, units or missingness. |
| Transformation support | Not yet scored | Demonstrate the capstone operation on accepted and rejected inputs. |
| Invariant preservation | Not yet scored | State the property preserved and supply a counterexample or perturbation. |
| Computational feasibility | Not yet scored | Measure size, time and memory on bounded fixtures; record limits. |
| Integration compatibility | Not yet scored | Verify existing schemas, APIs and neighboring contracts remain compatible. |
| Mathematical necessity | Not yet scored | Compare with directed finite-state graphs and temporal property checking and explain the additional capability, if any. |

## Curriculum

Prerequisites: basic programming, sets, functions and graph vocabulary. Work in six competency-gated sessions, approximately 60–90 minutes each; empirical evaluation is a separate research activity.

| Session | Learning objective | Exercise | Completion evidence |
| --- | --- | --- | --- |
| 1. Model | Identify initial state, nondeterministic transitions, predicates and counterexample paths. | Draw a minimal valid example and one excluded relationship. | Annotated object/relation inventory with explicit assumptions. |
| 2. Contract | Distinguish schema validity from substantive correctness. | Trace validation and propose malformed, missing and boundary inputs. | Input-to-rejection table grounded in current source. |
| 3. Operation | Explain directed finite-state graphs and temporal property checking. | Build a target-avoiding cycle: show reachable can pass while inevitable fails; inspect the separate certificate checker. | Hand trace compared with existing software, or a clearly labeled specification when no runtime exists. |
| 4. Preservation | State what a transformation must preserve. | Rename identifiers, reorder records, then alter one meaningful relation; predict each effect under the actual contract. | Separate invariant, expected change and unsupported transformation. |
| 5. Comparison | Justify mathematical necessity and cost. | Complete the six-criterion card for the existing approach and one proposed alternative; record unknowns honestly. | Evidence-backed recommendation with baseline and explicit veto conditions. |
| 6. Reproduction | Communicate the bounded result. | Reproduce the capstone using existing offline fixtures and record software version, inputs, outputs and limitations. | Reviewable notebook or report distinguishing computation, replay, independent evaluation and authorization. |

## Source-linked reading laboratory

The table is a guided selection of source lines, not an assertion that the whole repository is covered. Line numbers refer to the inspected source blob `0720f971f1ce370e9d6184f44975527cc0e3ac4f` in [formal_topology/analysis.py](../../formal_topology/analysis.py). Recheck anchors after source changes.

| Line | Statement | Learning check |
| --- | --- | --- |
| [10](../../formal_topology/analysis.py#L10) | `def canonical(value):` | State the input/output contract and trace one normal and one failing case. |
| [11](../../formal_topology/analysis.py#L11) | `return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()` | Predict the returned value and distinguish a computed result from authorization. |
| [14](../../formal_topology/analysis.py#L14) | `def fingerprint(value):` | State the input/output contract and trace one normal and one failing case. |
| [15](../../formal_topology/analysis.py#L15) | `return hashlib.sha256(canonical(value)).hexdigest()` | Explain the exact bytes bound by the digest and why hashing does not authenticate the source. |
| [18](../../formal_topology/analysis.py#L18) | `def traversal(graph, initial):` | State the input/output contract and trace one normal and one failing case. |
| [26](../../formal_topology/analysis.py#L26) | `return parents` | Trace discovery order and state the reachability or shortest-path invariant. |
| [29](../../formal_topology/analysis.py#L29) | `def path_to(parents, target):` | State the input/output contract and trace one normal and one failing case. |
| [35](../../formal_topology/analysis.py#L35) | `return {'states': list(reversed(states)), 'transitions': list(reversed(transitions))}` | Predict the returned value and distinguish a computed result from authorization. |
| [38](../../formal_topology/analysis.py#L38) | `def strongly_connected(graph, reachable):` | State the input/output contract and trace one normal and one failing case. |
| [47](../../formal_topology/analysis.py#L47) | `return groups` | Predict the returned value and distinguish a computed result from authorization. |
| [50](../../formal_topology/analysis.py#L50) | `def inevitability(graph, model, predicate, reachable):` | State the input/output contract and trace one normal and one failing case. |
| [60](../../formal_topology/analysis.py#L60) | `return 'PASS', {'ranks': dict(sorted(ranks.items()))}` | Predict the returned value and distinguish a computed result from authorization. |
| [71](../../formal_topology/analysis.py#L71) | `return 'FAIL', {'prefix': {'states': states[:start + 1], 'transitions': transitions[:start]},` | Predict the returned value and distinguish a computed result from authorization. |
| [76](../../formal_topology/analysis.py#L76) | `def property_result(prop, graph, model, parents):` | State the input/output contract and trace one normal and one failing case. |
| [92](../../formal_topology/analysis.py#L92) | `return {'id': prop['id'], 'kind': kind, 'status': status, 'evidence': evidence}` | Predict the returned value and distinguish a computed result from authorization. |
| [95](../../formal_topology/analysis.py#L95) | `def build_report(data, requirements):` | State the input/output contract and trace one normal and one failing case. |
| [112](../../formal_topology/analysis.py#L112) | `return {'schema_version': 1, 'engine_version': ENGINE_VERSION,` | Separate type, shape and value checks; test a missing field and an invalid value. |
## Assessment and verification

A learner must explain the model, trace the capstone, identify a counterexample and state the scope boundary. Assess these four competencies equally; a numerical score cannot compensate for an unsupported scientific or operational claim.

Relevant existing checks:

- [tests/test_formal.py](../../tests/test_formal.py)
- [tests/test_researchos.py](../../tests/test_researchos.py)

Follow [README](../../README.md) for environment and installed-package instructions. Read scripts before execution; source-reading exercises do not authorize provider calls, model downloads, live orders, hardware actions or messages. Synthetic fixtures establish software behavior only. This documentation change does not report those exercises as already executed.

## Interoperability and adoption gate

Retain explicit domain contracts. Shared assurance records should refer to domain evidence and its assumptions rather than relabeling graph reachability, homology, statistical calibration and epistemic acceptance as interchangeable quantities. The canonical ResearchOs controller remains owned by ResearchOs; this curriculum does not create another controller fork.

Adopt additional mathematics only after a versioned experiment demonstrates a useful operation, the scorecard has evidence, the simpler baseline is inadequate and existing conformance checks remain satisfied. No fairness is added implicitly; certificates concern the supplied finite model, not arbitrary real programs.
