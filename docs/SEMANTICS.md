# Semantics and certificate rules

## Formal domain

A model is M = (S, R, s0, AP, L), with finite states S, directed transition relation
R represented by identified edges, one initial state s0, declared propositions AP,
and explicit state labeling L. Parallel edges and self-loops are permitted.
Unknown state references are rejected. Scenario exclusions remove specified edges
from R and are recorded as assumptions; they do not modify captured model data.

Property predicates are Boolean trees over AP. `atom` tests label membership,
`not` negates one child, and nonempty `all`/`any` arrays combine children. There is
no expression language, eval, command execution or embedded program syntax.
Predicates may nest at most 16 levels, with at most 128 nodes and 16 operands per
Boolean array. Unknown operators and propositions fail validation.

For temporal checks, terminal states stutter indefinitely, giving every execution
an infinite interpretation. The raw graph remains available for explicit deadlock
checks. There are no fairness restrictions: a possible infinite retry cycle is a
valid counterexample even if an exit transition is also available.

The supported AG, EF and AF interpretations follow standard CTL terminology; see
the [NuSMV CTL reference](https://nusmv.fbk.eu/userman/v11/html/nusmv_25.html).
This project does not implement NuSMV, its input language or its complete temporal
logic. Only the four documented templates are accepted.

## Analysis

Breadth-first traversal computes reachable states and witness predecessors.
Strongly connected components are computed through mutual reachability over the
reachable subgraph. This bounded implementation favors straightforward inspection
over large-scale symbolic performance. Components with more than one state or a
self-loop are cyclic; a cycle by itself is not a failed property.

An invariant holds iff every reachable state's predicate is true. Reachability holds
iff at least one reachable state's predicate is true. Deadlock freedom holds iff every
reachable state has an active outgoing edge in the raw scenario graph.

Inevitability uses a least fixed point. Predicate states enter with rank 0. A
non-target state enters when it has at least one outgoing edge and every successor
already has a rank, with rank 1 + maximum successor rank. The property holds when
the initial state enters this set. Deadlocked non-target states never enter.

AF p means p holds now or at some future point on every path; it does not mean p
remains true thereafter or is reached repeatedly. In particular, if p is initially
true, AF p holds even if later behavior can avoid p forever. Use the exact property
meaning rather than treating every PASS as a general progress or stability claim.

If inevitability fails, the analyzer follows nonwinning successors until a state
repeats or a deadlock stutters. The result is a finite prefix and closed cycle, all
avoiding the target. `null` transition IDs encode implicit deadlock self-stuttering
only; they never represent a real transition or hide an excluded edge.

## Separate certificate checker

The checker does not invoke analyzer traversal, SCC or fixed-point routines. It
shares only input contracts, Boolean interpretation and active-edge semantics.
Its rules are:

1. Path evidence begins at s0, names model states and uses exact active directed
   transition IDs connecting consecutive states. Witnesses are bounded in length.
2. Invariant PASS: a finite set contains s0, is transition closed, and every member
   satisfies p. Invariant FAIL: a valid path reaches a state violating p.
3. Reachable PASS: a valid path reaches p. Reachable FAIL: a transition-closed set
   containing s0 has no p state.
4. Deadlock-free PASS: a transition-closed set containing s0 has at least one raw
   outgoing edge per member. FAIL: a valid path reaches a raw deadlock.
5. Inevitable PASS: ranks include s0. Every rank is a bounded nonnegative integer.
   Rank 0 is assigned exactly to predicate states within the certificate. Each
   non-target ranked state has successors and every outgoing successor is ranked
   strictly lower. Target states need no successor-rank constraint because the
   eventuality has already occurred.
6. Inevitable FAIL: a valid prefix reaches a nonempty closed cycle; every state in
   both prefix and cycle violates p. A null edge is valid only for a deadlocked
   state's self-stutter.

Closed sets may conservatively include unreachable states. Rankings need not include
states reached only after the target. These certificates remain sound for their
respective initial-state properties; they are not required to be uniquely minimal.
Full bundle verification requires the analyzer's deterministic canonical output.

The checker validates one certificate for every declared property, with exact IDs,
kinds, verdicts and evidence shapes. It does not authenticate signatures or identities.
It is not itself verified in a proof assistant. The regression suite and exhaustive
three-state oracle checks provide software evidence, not a universal correctness proof.

## Input and resource contracts

Both input roots require exact field sets and integer schema version 1. Model fields
are `schema_version`, `initial`, `propositions`, `states`, `transitions`. Each state
contains `id`, `labels`; each transition contains `id`, `source`, `target`. State IDs
and transition IDs are unique within their own namespaces. Proposition declarations
and label arrays have at most 64 unique trimmed names.

Requirements contain exactly `schema_version`, `required_states`, `properties`,
`disabled_transitions`. Required states may be absent, yielding visible gaps.
Excluded transitions must exist. Properties contain `id`, `kind`, `predicate`,
except deadlock freedom, which has only `id` and `kind`. Property IDs are unique.
At least one required state or property is necessary to avoid vacuous acceptance.
IDs contain 1–160 trimmed characters.

Limits: 256 states, 2048 transitions, 32 properties. Estimated work is
`states * (states + transitions) * (properties + 1)` and must not exceed 5,000,000.
This is a deterministic preflight bound, not a runtime or memory guarantee.
Predicate and JSON limits apply separately.

Files are regular UTF8 JSON, optionally with a UTF8 BOM, and at most 4 MiB each.
Duplicate keys, nonfinite numbers and JSON nesting over 64 levels are rejected.
Metadata is compared before/after bounded reads. These are input-integrity controls,
not protection against a privileged filesystem adversary.

## Gaps and completion

`MISSING_REQUIRED_STATE` means absent from S. `UNREACHABLE_REQUIRED_STATE` means
present in S but unreachable from s0 under active edges. `PROPERTY_VIOLATED` means
a named property failed with checked counterevidence. Requirement presence and
reachability fractions use all required IDs as their denominator, and are null
when no required state inventory was declared.

`OBLIGATIONS_HOLD` means all explicitly declared obligations hold within the supplied
finite model and scenario. Unrequired unreachable states do not force a gap.
Undeclared program behavior and model completeness cannot be inferred.

`certificates_valid` means PASS/FAIL evidence establishes its declared verdicts.
It may coexist with failed properties and missing-state gaps. The certificate CLI
binds the report to the supplied inputs by fingerprints and checks property evidence
only; it does not validate the overall report status or gap summary. Full `verify`
checks supplied certificates and then reconstructs every bundle file.

## Bundles and comparisons

Bundles contain exactly model.json, requirements.json, report.json, review.html and
manifest.json. Outputs use canonical sorted-key compact JSON plus final newline;
raw whitespace and object-key order are not retained. Arrays and numeric encodings
remain part of the input fingerprint. No timestamp or random generator affects a
report. HTML escapes supplied names and uses no scripts or external resources.

Each output file is at most 4 MiB. Exclusive destination creation preserves prior
outputs. Handled write failures remove only the new directory; abrupt interruption
can leave a partial directory that verification rejects. Parent directories must
exist. Bundle directories and files cannot be symlinks. Concurrent hostile edits
are not a supported operating model.

Verification detects edited proofs, report metadata, HTML, inputs or manifests by
rechecking and recomputation. It is not a signature: replacing all inputs and
regenerating a study produces a different consistent bundle. Use external trusted
fingerprints or signatures when authenticity is required. Engine/schema versions
are recorded; replay across future output-changing versions is not promised.

Comparison requires two verified bundles of the same captured model. It separates
changed obligations from changed exclusions and displays verdict/gap deltas. A
restricted model's PASS must never be reported as proof of the unrestricted model.
No action, deployment or repository setting is changed by analysis.
