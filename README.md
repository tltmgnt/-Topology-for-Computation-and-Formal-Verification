# Topology for Computation and Formal Verification

A dependency-free **explicit finite-state model checker** with topology diagnostics,
proof and counterexample certificates, a separate certificate checker, and
reproducible offline review bundles.

Import a fully enumerated transition system, declare Boolean state properties,
check its reachable behavior, inspect witnesses or counterexamples, and replay the
complete study. Results concern the supplied finite model. They do not prove
arbitrary programs correct or establish that a model accurately represents reality.

## Install and complete a study

Requires Python 3.10 or later.

```sh
python -m pip install .
mkdir -p runs
formal-topology analyze examples/model.json --requirements examples/requirements.json --output runs/reference
formal-topology certificates runs/reference/model.json --requirements runs/reference/requirements.json --report runs/reference/report.json
formal-topology verify runs/reference
```

Open `runs/reference/review.html` for a self-contained, script-free report. Each
output directory must be new; parent directories must exist. Without installation,
use `python -m formal_topology` from the repository root.

```sh
python -m unittest discover -s tests -v
python tests/check_installed.py
```

The second command requires a normal package installation. It uses isolated imports
outside the checkout, so source files cannot conceal an incomplete distribution.

## Four supported property kinds

| Kind | Meaning from the initial state | Evidence |
|---|---|---|
| `invariant` | Predicate holds in every reachable state, equivalent to AG p | Closed reachable set or a violating witness path |
| `reachable` | Some execution reaches a predicate state, equivalent to EF p | Witness path or a closed set excluding the target |
| `inevitable` | Every execution eventually reaches a predicate state, equivalent to AF p | Decreasing finite ranks or a target-avoiding lasso |
| `deadlock_free` | No reachable state lacks an active outgoing transition | Closed set with successors or a deadlock witness |

These are four fixed property templates with Boolean predicates, not a general CTL
parser. Temporal operators cannot be nested. All nondeterministic executions count;
there are **no fairness assumptions**. For AF checks, a deadlock stutters forever.
A deadlocked target satisfies AF at that state, but still violates deadlock freedom.
See [semantics and proof rules](docs/SEMANTICS.md) for precise boundaries.

## Synthetic failure and gap studies

The baseline model is `idle → reviewed → done`, with a self-loop at done and an
unreachable orphan. It satisfies all four example properties. Other examples test:

- `unsafe.json`: a bypass reaches the unsafe orphan and deadlocks. Safety,
  inevitability and deadlock freedom fail; completion remains possible.
- `livelock.json`: a retry returns to idle. Safety and deadlock freedom hold,
  completion remains possible, but completion is not inevitable without fairness.
- `outage.json`: excludes the finish transition as an explicit scenario assumption.
- `gaps.json`: requires an unreachable state and an absent state separately.

```sh
formal-topology analyze examples/unsafe.json --requirements examples/requirements.json --output runs/unsafe
# Expected exit 1; a complete bundle with counterexamples is still created.
formal-topology verify runs/unsafe
# Expected exit 0; the counterexamples are valid and the bundle still reports GAPS_FOUND.
formal-topology analyze examples/model.json --requirements examples/outage.json --output runs/outage
# Expected exit 1.
formal-topology compare runs/reference runs/outage
```

Comparison checks both bundles, requires the same captured model, and reports new
and resolved gaps, property-verdict changes, obligation changes and transition
exclusions. Removing behavior is an assumption change, not proof that the unrestricted
system was repaired.

## Model and requirement contracts

Model example:

```json
{
  "schema_version": 1,
  "initial": "start",
  "propositions": ["safe", "done"],
  "states": [
    {"id":"start", "labels":["safe"]},
    {"id":"finish", "labels":["safe", "done"]}
  ],
  "transitions": [
    {"id":"advance", "source":"start", "target":"finish"},
    {"id":"stay", "source":"finish", "target":"finish"}
  ]
}
```

Requirement example:

```json
{
  "schema_version": 1,
  "required_states": ["finish"],
  "disabled_transitions": [],
  "properties": [
    {"id":"safety", "kind":"invariant", "predicate":{"atom":"safe"}},
    {"id":"completion", "kind":"inevitable", "predicate":{"atom":"done"}}
  ]
}
```

Predicates are data-only Boolean trees: `atom`, `not`, `all`, `any`. All atoms must
be declared. A declared atom omitted from a state's explicit label list is false,
not unknown. The tool cannot detect omitted real-world behavior. Required state IDs
absent from the model are reported as missing; present but unreachable required
states are a separate gap. Unknown transition endpoints or excluded IDs are invalid
configuration rather than silently repaired.

## What the certificates establish

The analyzer emits evidence with every property verdict. `certificates.py` checks
it without importing or calling the analyzer's graph traversal or fixed-point
routines. It validates transition witnesses, closed-set induction, strictly decreasing
rankings, and target-avoiding cycles or deadlock stutters.

This is a separate local implementation, not external independent certification,
a proof assistant, or a mechanically verified checker. Parsing, Boolean evaluation,
transition interpretation, checker code and the Python runtime remain trusted.
A model author controls labels and the declared behavior universe.

`certificates` validates property verdict evidence only; it does not trust or verify
the report's overall status, summary or missing-state gap inventory. Its output
states this narrower scope. `verify` additionally recomputes all report metadata,
HTML and hashes. A valid FAIL certificate establishes a counterexample, so successful
certificate checking does not mean the properties passed.

## Bundle and exit codes

Each bundle has exactly `model.json`, `requirements.json`, `report.json`,
`review.html`, and `manifest.json`. Inputs are captured canonically. Reports include
source fingerprints, explicit assumptions, reachable/unreachable states, SCCs,
cycles, deadlocks, requirement coverage, property results and gap codes. Verification
checks supplied certificates and reconstructs every file, detecting report edits even
when its manifest hash has been rewritten.

| Command | Exit 0 | Exit 1 | Exit 2 |
|---|---|---|---|
| `analyze` | Obligations hold in supplied model | Gaps found; bundle created | Invalid input, resource limit or I/O failure |
| `certificates` | Property verdict evidence checks, including FAIL verdicts | Not used | Missing, invalid or incorrectly bound evidence |
| `verify` | Bundle consistent, including valid failing studies | Not used | Edited, incomplete, invalid or incompatible bundle |
| `compare` | Verified comparison completed | Not used | Invalid bundles or different captured models |

## Validation and CI

Tests cover safety violations, nondeterministic livelock, deadlock stuttering,
missingness, input limits, forged rankings, invalid witnesses, altered manifests,
Python syntax compatibility and complete command-line workflows. An exhaustive test
checks all 512 directed three-state graphs under all eight target labelings against
a bounded-trace oracle and validates every generated certificate: 4096 models and
16,384 property verdicts. This is a substantial finite regression set, not a proof
that the implementation is bug-free or a benchmark against external tools.

CI runs on Python 3.10, 3.12 and 3.13, exercises installed-package workflows, and
publishes a seven-day `synthetic-formal-review` artifact. Download and extract it,
open `review.html`, and run `formal-topology verify` on the directory. Only synthetic
examples are uploaded; keep proprietary real models private.

## Scope and limits

Inputs are bounded to 256 states, 2048 transitions, 32 properties and a declared
analysis-work budget. The model is explicit and finite; checking is exhaustive
within that supplied state universe, not bounded exploration of an unbounded
program. No source-code extraction, SAT/SMT solver, theorem prover, fairness engine,
probabilistic/timed verification, distributed runtime or consequential execution is
implemented. `execution_authorized` is always false.

Hashes prove consistency, not source authenticity. Replacing inputs and regenerating
a complete bundle produces another consistent study. Reports contain model details;
protect them when confidential. Future engine versions may require replay with the
original software version. See [contracts and semantics](docs/SEMANTICS.md).

## License

Apache License 2.0. The repository's original license is retained.

## ResearchOS / TECT concept integration

The [ResearchOS / Topological Epistemic Control Theory technical concept paper](docs/researchos/TECT_WHITE_PAPER.md) proposes an epistemic control and assurance infrastructure for AI-generated knowledge. Read the [repository integration status](docs/researchos/INTEGRATION.md) and [machine-readable scope](docs/researchos/integration.json) for the boundary between the concept and implemented capabilities. Performance targets are research objectives, not achieved results. This documentation addition does not implement the complete ResearchOS architecture or change operational authority.

## ResearchOS / TECT assurance layer

This repository includes the shared v0.1 research controller, a scoped executable domain pilot, replayable evidence/decision bundles, adversarial regression probes, and explicit unassured outcomes. See [the workflow](docs/RESEARCHOS.md), [versioned semantics](docs/TECT_SPEC.md), and [research-program traceability](docs/TECT_RESEARCH_PLAN.md). Existing domain results retain their documented limits. No claim state authorizes external or clinical execution.

## Portfolio implementation boundary

See [current implementation and shared-core integration](docs/portfolio/INTEGRATION.md) and [machine-readable status](docs/portfolio/STATUS.json). Independent empirical reproduction and real-provider acceptance remain separate from software checks.

**∞**

## Topology compatibility and curriculum

See the [repository-specific v2 curriculum](docs/portfolio/TOPOLOGY_CURRICULUM_V2.md) for topology choices, worked explanations, a graded laboratory and adoption boundaries. Run the offline answer key from this repository root:\n\n```sh\npython curriculum/lab.py --verify\n```\n\n[Expected answers](curriculum/expected.json) · [Recorded local validation](curriculum/VALIDATION.json). The guide states any existing dependency needed for the lab.
