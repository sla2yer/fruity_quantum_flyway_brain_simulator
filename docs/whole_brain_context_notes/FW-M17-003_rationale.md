# FW-M17-003 Rationale

## Design choices

This ticket adds one library-owned execution layer,
`flywire_wave.whole_brain_context_query`, and keeps the first version local,
deterministic, and packaging-first.

The core decisions were:

- reuse the existing Milestone 17 session plan as the canonical query input
  instead of introducing a second ad hoc graph-request schema
- execute against the local synapse registry plus best-effort local node
  metadata surfaces, with explicit fallback from packaged neuron registry to raw
  Codex-style classification and cell-type files when available
- reduce context with a path-preserving greedy budget rather than exporting the
  whole neighborhood and hoping later UI layers can clean it up
- keep active-versus-context truthfulness in the payload itself through stable
  node and edge role ids, not through later client-side styling heuristics

The implementation intentionally treats the session metadata and the richer
view payload differently:

- `representative_context` inside `whole_brain_context_session.v1` stays limited
  to unique biological roots so it remains contract-valid and hash-stable
- `context_view_payload.json` now carries the richer `query_execution` payload,
  including overview, focused-subgraph, and pathway-highlight sections

That split preserves the earlier contract while still giving later dashboard
and showcase work enough structured graph state to render without re-reading
raw CSV inputs.

## Query and reduction strategy

The query engine stays deliberately boring:

- deterministic hop-bounded upstream, downstream, and mixed traversal from the
  active subset
- explicit reduction controls normalized from the selected reduction profile and
  optional overrides
- stable edge ranking policies based on synapse count or accumulated weight
- optional neuropil and cell-class filters applied before context selection
- pathway extraction built from best ranked local paths, with optional targeted
  endpoints for review-focused use cases

Context selection is greedy but path-preserving. A candidate context node only
lands in the payload if its best path back to the active subset fits both the
context-node budget and the edge budget. That keeps the reduced graph readable
and connected instead of selecting isolated high-score nodes that later views
cannot explain.

The first downstream-module behavior is intentionally conservative. Module
records are emitted as collapsed metadata summaries for downstream context roots
when the plan requests them, but they do not attempt to invent new biological
targets or a stronger simulator-side decoder story.

## Testing strategy

The regression coverage for this ticket focuses on deterministic local behavior.

The new tests verify:

- upstream ranking and reduction keep the selected context roots stable and
  exclude lower-priority hop-2 spillover
- downstream queries honor explicit neuropil filters and node budgets
- pathway-review queries build deterministic targeted highlight extracts and a
  focused subgraph
- clear failures appear for missing synapse inputs, missing metadata needed for
  cell-class filtering, and unreachable targeted pathway requests
- resolved Milestone 17 plans and packaged payloads embed the executed query
  result instead of the old anchor-only placeholder context

Existing whole-brain context contract and planning tests were also rerun so the
new execution layer stays compatible with the earlier Milestone 17 contract and
planner work.

## Simplifications

The first query engine is intentionally narrow.

Current simplifications:

- no live FlyWire queries, graph database, caching tier, or backend service
- no attempt to solve global whole-brain graph layout or final UI rendering
- best-effort metadata enrichment for context-only nodes when richer registry
  inputs are absent
- downstream modules are summary records without dedicated module-edge records
  in the contract-owned representative metadata

These are deliberate tradeoffs. The milestone needed one inspectable local
query layer more than it needed a maximal graph platform.

## Future expansion

Likely follow-on work can extend this foundation by:

- adding richer preset-owned reduction overrides on top of the normalized plan
- promoting more metadata filters and ranking policies into contract-owned
  reduction-profile normalization
- attaching dedicated module-edge payloads once the downstream-module contract
  surface becomes richer
- adding specialized payload summaries for dashboard cards, hover captions, and
  showcase handoff explanations without changing the core local query API
